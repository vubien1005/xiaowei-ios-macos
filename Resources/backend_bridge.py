#!/usr/bin/env python3
"""
macOS Native Backend Service for Xiaowei iOS.
Full support for:
- macOS usbmuxd + Lockdown + tidevice + CoreDevice (iOS 12 through iOS 18+)
- WebDriverAgent (WDA) persistent session, MJPEG 9100 streaming, W3C smooth touch/swipe/scroll
- Full keyboard (ASCII + Unicode/Vietnamese), Clipboard/Pasteboard sync, Home/AppSwitcher/Back/Volume/Lock
- App Manager (list, launch, stop, install IPA, uninstall)
- File Manager via Apple File Conduit (AFC: browse, pull/export, push photo/video, delete)
- Screenshot to Mac & Macro Action playback
- Local SQLite storage & static web asset server on 127.0.0.1:19881
"""

import base64
import hashlib
import http.client
import io
import json
import os
import plistlib
import queue
import select
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

warnings.filterwarnings("ignore")

_BUNDLED_SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site-packages")
if os.path.isdir(_BUNDLED_SITE) and _BUNDLED_SITE not in sys.path:
    sys.path.insert(0, _BUNDLED_SITE)

try:
    import tidevice
except Exception:
    tidevice = None

APP_SUPPORT = os.path.expanduser("~/Library/Application Support/com.xiaowei.iphone")
CACHE_DIR = os.path.expanduser("~/Library/Caches/com.xiaowei.iphone")
LOG_DIR = os.path.expanduser("~/Library/Logs/com.xiaowei.iphone")
for _d in (APP_SUPPORT, CACHE_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

CONFIG_PATH = os.path.join(APP_SUPPORT, "rust_config.json")
USBMUXD_SOCKET = "/var/run/usbmuxd"

IPHONE_MODELS = {
    "iPhone8,1": "iPhone 6s",
    "iPhone8,2": "iPhone 6s Plus",
    "iPhone9,1": "iPhone 7",
    "iPhone9,2": "iPhone 7 Plus",
    "iPhone9,3": "iPhone 7",
    "iPhone9,4": "iPhone 7 Plus",
    "iPhone10,1": "iPhone 8",
    "iPhone10,2": "iPhone 8 Plus",
    "iPhone10,3": "iPhone X",
    "iPhone10,4": "iPhone 8",
    "iPhone10,5": "iPhone 8 Plus",
    "iPhone10,6": "iPhone X",
    "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max",
    "iPhone11,6": "iPhone XS Max",
    "iPhone11,8": "iPhone XR",
    "iPhone12,1": "iPhone 11",
    "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE 2",
    "iPhone13,1": "iPhone 12 mini",
    "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro",
    "iPhone13,4": "iPhone 12 Pro Max",
    "iPhone14,2": "iPhone 13 Pro",
    "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 mini",
    "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE 3",
    "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus",
    "iPhone16,1": "iPhone 15 Pro",
    "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,2": "iPhone 16 Pro Max",
    "iPhone17,3": "iPhone 16",
    "iPhone17,4": "iPhone 16 Plus",
}

HOME_BUTTON_MODELS = {
    "iPhone 6s", "iPhone 6s Plus", "iPhone 7", "iPhone 7 Plus",
    "iPhone 8", "iPhone 8 Plus", "iPhone SE 2", "iPhone SE 3",
}

# Android KeyCode -> (normal_char, shifted_char)
ANDROID_KEYMAP = {
    7: ("0", ")"), 8: ("1", "!"), 9: ("2", "@"), 10: ("3", "#"), 11: ("4", "$"),
    12: ("5", "%"), 13: ("6", "^"), 14: ("7", "&"), 15: ("8", "*"), 16: ("9", "("),
    55: (",", "<"), 56: (".", ">"), 61: ("\t", "\t"), 62: (" ", " "),
    68: ("`", "~"), 69: ("-", "_"), 70: ("=", "+"), 71: ("[", "{"), 72: ("]", "}"),
    73: ("\\", "|"), 74: (";", ":"), 75: ("'", '"'), 76: ("/", "?"), 77: ("@", "@"),
}
for _idx, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    ANDROID_KEYMAP[29 + _idx] = (_ch, _ch.upper())


def normalize_mac_path(p):
    if not p:
        return ""
    return str(p).replace("\\", "/")


def get_mac_clipboard():
    try:
        return subprocess.check_output(["/usr/bin/pbpaste"], timeout=2).decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Minimal RFC 6455 WebSocket Server
# ---------------------------------------------------------------------------

class WebSocketHub:
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, message_handler, binary_handler=None):
        self.clients = set()
        self.lock = threading.Lock()
        self._send_lock = threading.Lock()
        self.port = 0
        self.message_handler = message_handler
        self.binary_handler = binary_handler
        self._on_client_connected = None

    def set_on_connect(self, fn):
        self._on_client_connected = fn

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        srv.bind(("127.0.0.1", 0))
        srv.listen(32)
        self.port = srv.getsockname()[1]
        threading.Thread(target=self._accept_loop, args=(srv,), daemon=True).start()
        return self.port

    def _accept_loop(self, srv):
        while True:
            try:
                conn, _ = srv.accept()
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                time.sleep(0.1)

    def _handle_client(self, conn):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                chunk = conn.recv(4096)
                if not chunk:
                    conn.close()
                    return
                req += chunk
            headers = {}
            for line in req.decode("utf-8", errors="ignore").split("\r\n")[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            ws_key = headers.get("sec-websocket-key", "")
            if not ws_key:
                conn.close()
                return
            accept_val = base64.b64encode(
                hashlib.sha1((ws_key + self.GUID).encode("ascii")).digest()
            ).decode("ascii")
            resp = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
            )
            conn.sendall(resp.encode("ascii"))
            with self.lock:
                self.clients.add(conn)
            if self._on_client_connected:
                threading.Thread(target=self._on_client_connected, args=(conn,), daemon=True).start()
            self._read_frames(conn)
        except Exception:
            pass
        finally:
            with self.lock:
                self.clients.discard(conn)
            try:
                conn.close()
            except Exception:
                pass

    def _recv_exact(self, conn, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise EOFError()
            buf.extend(chunk)
        return bytes(buf)

    def _read_frames(self, conn):
        msg_buf = bytearray()
        msg_opcode = 1
        while True:
            hdr = self._recv_exact(conn, 2)
            fin = (hdr[0] & 0x80) != 0
            opcode = hdr[0] & 0x0F
            masked = (hdr[1] & 0x80) != 0
            length = hdr[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(conn, 2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(conn, 8))[0]
            mask_key = self._recv_exact(conn, 4) if masked else None
            payload = bytearray(self._recv_exact(conn, length))
            if mask_key:
                for i in range(length):
                    payload[i] ^= mask_key[i & 3]
            if opcode == 0x8:
                break
            if opcode == 0x9:
                self._send_frame(conn, 0xA, bytes(payload))
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                msg_opcode = opcode
                msg_buf = payload
            elif opcode == 0x0:
                msg_buf.extend(payload)
            if fin:
                data = bytes(msg_buf)
                msg_buf = bytearray()
                if msg_opcode == 0x1:
                    try:
                        self.message_handler(data.decode("utf-8", errors="ignore"))
                    except Exception:
                        pass
                elif msg_opcode == 0x2 and data:
                    try:
                        if data[:1] == b"{":
                            self.message_handler(data.decode("utf-8", errors="ignore"))
                        elif self.binary_handler:
                            self.binary_handler(data)
                    except Exception:
                        pass

    def _encode_frame(self, opcode, payload_bytes):
        n = len(payload_bytes)
        header = bytearray([0x80 | opcode])
        if n < 126:
            header.append(n)
        elif n < 65536:
            header.append(126)
            header.extend(struct.pack(">H", n))
        else:
            header.append(127)
            header.extend(struct.pack(">Q", n))
        return bytes(header) + payload_bytes

    def _send_frame(self, conn, opcode, payload_bytes):
        raw = self._encode_frame(opcode, payload_bytes)
        with self._send_lock:
            conn.sendall(raw)

    def send_text_to(self, conn, text):
        try:
            self._send_frame(conn, 0x1, text.encode("utf-8"))
        except Exception:
            with self.lock:
                self.clients.discard(conn)

    def broadcast_text(self, text):
        frame = self._encode_frame(0x1, text.encode("utf-8"))
        dead = []
        with self.lock:
            targets = list(self.clients)
        for c in targets:
            try:
                with self._send_lock:
                    c.sendall(frame)
            except Exception:
                dead.append(c)
        if dead:
            with self.lock:
                for c in dead:
                    self.clients.discard(c)


# ---------------------------------------------------------------------------
# macOS Native usbmuxd & WebDriverAgent Bridge
# ---------------------------------------------------------------------------

class UsbmuxClient:
    @staticmethod
    def _send_plist(sock, tag, payload):
        body = plistlib.dumps(payload, fmt=plistlib.FMT_XML)
        header = struct.pack("<IIII", 16 + len(body), 1, 8, tag)
        sock.sendall(header + body)

    @staticmethod
    def _recv_plist(sock):
        hdr = b""
        while len(hdr) < 16:
            chunk = sock.recv(16 - len(hdr))
            if not chunk:
                raise EOFError()
            hdr += chunk
        total_len, _ver, _msg_type, _tag = struct.unpack("<IIII", hdr)
        body_len = total_len - 16
        body = b""
        while len(body) < body_len:
            chunk = sock.recv(body_len - len(body))
            if not chunk:
                raise EOFError()
            body += chunk
        return plistlib.loads(body)

    @classmethod
    def list_devices(cls):
        if not os.path.exists(USBMUXD_SOCKET):
            return []
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        try:
            sock.connect(USBMUXD_SOCKET)
            cls._send_plist(
                sock,
                1,
                {
                    "MessageType": "ListDevices",
                    "ClientVersionString": "XiaoweiMacOS",
                    "ProgName": "XiaoweiMacOS",
                    "kLibUSBMuxVersion": 3,
                },
            )
            resp = cls._recv_plist(sock)
            out = []
            for entry in resp.get("DeviceList", []):
                props = entry.get("Properties", {})
                conn_type = props.get("ConnectionType", "USB")
                serial = props.get("SerialNumber", "")
                dev_id = entry.get("DeviceID", props.get("DeviceID"))
                if serial and dev_id is not None:
                    out.append(
                        {
                            "serial": serial,
                            "device_id": dev_id,
                            "connection_type": conn_type,
                            "product_id": props.get("ProductID", 0),
                        }
                    )
            return out
        except Exception:
            return []
        finally:
            sock.close()

    @classmethod
    def connect_device_port(cls, device_id, port, timeout=3.0):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(USBMUXD_SOCKET)
        net_port = socket.htons(port)
        cls._send_plist(
            sock,
            2,
            {
                "MessageType": "Connect",
                "ClientVersionString": "XiaoweiMacOS",
                "ProgName": "XiaoweiMacOS",
                "DeviceID": int(device_id),
                "PortNumber": int(net_port),
            },
        )
        resp = cls._recv_plist(sock)
        if resp.get("Number", -1) != 0:
            sock.close()
            raise ConnectionRefusedError(f"usbmuxd connect error {resp.get('Number')} on port {port}")
        return sock


class UsbmuxHTTPConnection(http.client.HTTPConnection):
    def __init__(self, device_id, port, timeout=4.0):
        super().__init__("127.0.0.1", port, timeout=timeout)
        self._device_id = device_id
        self._target_port = port

    def connect(self):
        self.sock = UsbmuxClient.connect_device_port(self._device_id, self._target_port, timeout=self.timeout)


def generate_placeholder_jpeg(title, subtitle):
    cache_key = hashlib.md5(f"{title}|{subtitle}".encode("utf-8")).hexdigest()
    jpg_path = os.path.join(CACHE_DIR, f"placeholder_{cache_key}.jpg")
    if os.path.exists(jpg_path):
        with open(jpg_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    ppm_path = os.path.join(CACHE_DIR, f"placeholder_{cache_key}.ppm")
    w, h = 270, 585
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    pixels = bytearray(w * h * 3)
    for y in range(h):
        r = 18 + (y * 16) // h
        g = 24 + (y * 28) // h
        b = 38 + (y * 52) // h
        pixels[y * w * 3 : (y + 1) * w * 3] = bytes([r, g, b]) * w
    bx0, by0, bx1, by1 = w // 2 - 36, h // 2 - 64, w // 2 + 36, h // 2 + 64
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            if x in (bx0, bx0 + 1, bx1 - 2, bx1 - 1) or y in (by0, by0 + 1, by1 - 2, by1 - 1):
                idx = (y * w + x) * 3
                pixels[idx : idx + 3] = b"\x2b\x84\xdd"
    with open(ppm_path, "wb") as f:
        f.write(header + pixels)
    subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", ppm_path, "--out", jpg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        os.remove(ppm_path)
    except Exception:
        pass
    if os.path.exists(jpg_path):
        with open(jpg_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    return ""


class IOSDeviceSession:
    """Manages one connected iOS device, persistent WDA session, serialized action worker, AFC & app control."""

    def __init__(self, serial, device_id, name="iPhone", model="iPhone", os_version="16.0", hub=None, emit_event=None):
        self.serial = serial
        self.device_id = device_id
        self.name = name
        self.model = model
        self.os_version = os_version
        self.ip_addr = ""
        self.scale = 2 if model in HOME_BUTTON_MODELS else 3
        self.logic_w = 375 if model in HOME_BUTTON_MODELS else 390
        self.logic_h = 667 if model in HOME_BUTTON_MODELS else 844
        self.width = self.logic_w * self.scale
        self.height = self.logic_h * self.scale
        self.fps_limit = 60
        self.hub = hub
        self.emit_event = emit_event
        self.active = True
        self.wda_session_id = None
        self.wda_ready = False
        self.last_jpeg_b64 = ""
        self._wda_proc = None
        self._last_wda_launch_attempt = 0.0
        self._last_wda_auto_install_attempt = 0.0
        self._auto_installing_wda = False
        self._ti_dev = None
        self._touch_down = None
        self._touch_last = None
        self._touch_down_ts = 0.0
        self._last_touch_up_ts = 0.0
        self._last_scroll_ts = 0.0
        self._scroll_lock = threading.Lock()
        self._latest_scroll = None
        self._macro_stop_flag = False
        self._wda_http_lock = threading.Lock()
        self._wda_fast_lock = threading.Lock()
        self._wda_conn = None
        self._wda_conn_key = None
        self._wda_fast_conn = None
        self._wda_fast_conn_key = None
        self._has_fast_wda = None
        self._settings_applied_sid = None
        self._action_queue = queue.Queue(maxsize=128)
        threading.Thread(target=self._action_worker, daemon=True).start()
        threading.Thread(target=self._stream_worker, daemon=True).start()

    def to_meta(self, loading=0):
        return {
            "serial": self.serial,
            "serial_num": self.serial,
            "onlySerial": self.serial,
            "name": self.name or self.model,
            "model": self.model or "iPhone",
            "width": self.width,
            "height": self.height,
            "mode": 0,
            "loading": loading,
            "status": "online",
            "os_version": self.os_version,
        }

    def _close_wda_connections(self):
        for attr in ("_wda_conn", "_wda_fast_conn"):
            c = getattr(self, attr, None)
            setattr(self, attr, None)
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass

    def stop(self):
        self.active = False
        self._macro_stop_flag = True
        self._close_wda_connections()
        if self._wda_proc and self._wda_proc.poll() is None:
            try:
                self._wda_proc.terminate()
            except Exception:
                pass

    def _enqueue_action(self, fn, *args):
        try:
            self._action_queue.put_nowait((fn, args))
        except queue.Full:
            pass

    def _action_worker(self):
        while self.active:
            try:
                fn, args = self._action_queue.get(timeout=0.5)
                try:
                    fn(*args)
                except Exception:
                    pass
            except queue.Empty:
                continue

    def _get_tidevice(self):
        if tidevice is None:
            return None
        if self._ti_dev is None:
            try:
                self._ti_dev = tidevice.Device(self.serial)
            except Exception:
                return None
        return self._ti_dev

    def _capture_usb_screenshot_jpeg(self):
        dev = self._get_tidevice()
        if dev is None:
            return ""
        try:
            img = dev.screenshot()
            iw, ih = img.size
            if iw > 0 and ih > 0:
                self.width, self.height = iw, ih
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=72)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            self._ti_dev = None
            return ""

    def _new_wda_http_conn(self, timeout=4.0):
        if self.device_id is not None:
            key = ("usb", int(self.device_id))
            conn = UsbmuxHTTPConnection(self.device_id, 8100, timeout=timeout)
            return conn, key
        if self.ip_addr:
            key = ("tcp", str(self.ip_addr))
            conn = http.client.HTTPConnection(self.ip_addr, 8100, timeout=timeout)
            return conn, key
        raise ConnectionError("No transport for device")

    def _persistent_http_exchange(self, conn_attr, key_attr, lock, method, path, payload=None, timeout=4.5):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Connection": "keep-alive"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        with lock:
            last_err = None
            for _attempt in range(2):
                conn = getattr(self, conn_attr)
                cur_key = getattr(self, key_attr)
                want_key = ("usb", int(self.device_id)) if self.device_id is not None else (("tcp", str(self.ip_addr)) if self.ip_addr else None)
                if want_key is None:
                    raise ConnectionError("No transport for device")
                if conn is None or cur_key != want_key:
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    conn, cur_key = self._new_wda_http_conn(timeout=timeout)
                    setattr(self, conn_attr, conn)
                    setattr(self, key_attr, cur_key)
                else:
                    conn.timeout = timeout
                    if getattr(conn, "sock", None) is not None:
                        try:
                            conn.sock.settimeout(timeout)
                        except Exception:
                            pass
                try:
                    conn.request(method, path, body=body, headers=headers)
                    if cur_key[0] == "tcp" and getattr(conn, "sock", None) is not None:
                        try:
                            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        except Exception:
                            pass
                    resp = conn.getresponse()
                    status = resp.status
                    raw = resp.read()
                    if resp.will_close:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        setattr(self, conn_attr, None)
                    data = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
                    return status, data
                except (http.client.HTTPException, OSError, EOFError) as exc:
                    last_err = exc
                    try:
                        conn.close()
                    except Exception:
                        pass
                    setattr(self, conn_attr, None)
            raise last_err if last_err is not None else ConnectionError("WDA HTTP request failed")

    def _wda_raw_request(self, method, path, payload=None, timeout=4.5):
        return self._persistent_http_exchange("_wda_conn", "_wda_conn_key", self._wda_http_lock, method, path, payload=payload, timeout=timeout)

    def _wda_fast_request(self, method, path, payload=None, timeout=2.5):
        return self._persistent_http_exchange("_wda_fast_conn", "_wda_fast_conn_key", self._wda_fast_lock, method, path, payload=payload, timeout=timeout)

    def _apply_wda_turbo_settings(self, sid):
        if not sid:
            return
        try:
            st, _ = self._wda_raw_request(
                "POST",
                f"/session/{sid}/appium/settings",
                {
                    "settings": {
                        "mjpegScalingFactor": 100,
                        "mjpegServerScreenshotQuality": 24,
                        "mjpegServerFramerate": 38,
                        "waitForIdleTimeout": 0,
                        "animationCoolOffTimeout": 0,
                        "reduceMotion": True,
                    }
                },
                timeout=2.5,
            )
            if st == 200:
                self._settings_applied_sid = sid
        except Exception:
            pass

    def _create_new_wda_session(self):
        self._has_fast_wda = None
        status, res = self._wda_raw_request("POST", "/session", {"capabilities": {}}, timeout=5.0)
        if status == 200:
            sid = res.get("sessionId") or (res.get("value") or {}).get("sessionId")
            if sid:
                self.wda_session_id = sid
                self._sync_window_size(sid)
                self._apply_wda_turbo_settings(sid)
                return sid
        return None

    def _sync_window_size(self, sid):
        try:
            st, win = self._wda_raw_request("GET", f"/session/{sid}/window/size", timeout=2.5)
            if st == 200:
                val = win.get("value") or {}
                lw = int(val.get("width") or 0)
                lh = int(val.get("height") or 0)
                if lw > 0 and lh > 0:
                    self.logic_w, self.logic_h = lw, lh
                    self.width, self.height = lw * self.scale, lh * self.scale
        except Exception:
            pass

    def _wda_session_request(self, method, sub_path, payload=None, timeout=4.5):
        """Send a request scoped to /session/<sid><sub_path>, auto-recovering expired sessions once."""
        sid = self.wda_session_id or self._create_new_wda_session()
        if not sid:
            raise ConnectionError("WDA session unavailable")
        status, data = self._wda_raw_request(method, f"/session/{sid}{sub_path}", payload=payload, timeout=timeout)
        err_str = json.dumps(data.get("value") or "").lower()
        if status in (404, 400) and ("session" in err_str or "does not exist" in err_str):
            sid = self._create_new_wda_session()
            if sid:
                status, data = self._wda_raw_request(method, f"/session/{sid}{sub_path}", payload=payload, timeout=timeout)
        return status, data

    def _ensure_wda_session(self):
        try:
            st, info = self._wda_raw_request("GET", "/status", timeout=2.0)
            if st != 200:
                self.wda_ready = False
                return False
            ios_info = (info.get("value") or {}).get("ios") or {}
            if ios_info.get("ip"):
                self.ip_addr = ios_info["ip"]
            if not self.wda_session_id:
                self._create_new_wda_session()
            elif self._settings_applied_sid != self.wda_session_id:
                self._apply_wda_turbo_settings(self.wda_session_id)
            self.wda_ready = self.wda_session_id is not None
            return self.wda_ready
        except Exception:
            self.wda_ready = False
            self._has_fast_wda = None
            return False

    @staticmethod
    def _resolve_bundled_wda_ipa():
        res_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(APP_SUPPORT, "WebDriverAgentRunner.ipa"),
            os.path.join(res_dir, "WebDriverAgentRunner.ipa"),
        ]
        existing = [p for p in candidates if os.path.isfile(p)]
        if not existing:
            return ""
        return max(existing, key=lambda p: os.path.getmtime(p))

    def _auto_install_wda_after_restore(self, ipa_path):
        try:
            dev = self._get_tidevice()
            if dev is not None and os.path.isfile(ipa_path):
                dev.app_install(ipa_path)
                # Trigger immediate WDA launch on next _stream_worker tick
                self._last_wda_launch_attempt = 0.0
        except Exception:
            pass
        finally:
            self._auto_installing_wda = False

    def _try_launch_installed_wda(self):
        now = time.time()
        if now - self._last_wda_launch_attempt < 6.0:
            return
        self._last_wda_launch_attempt = now

        if self._wda_proc and self._wda_proc.poll() is None:
            return

        discovered_bundles = []
        paired_ok = False
        dev = self._get_tidevice()
        if dev is not None:
            try:
                for app in dev.installation.iter_installed(app_type="User"):
                    paired_ok = True
                    bid = app.get("CFBundleIdentifier") or ""
                    low = bid.lower()
                    if "webdriveragent" in low or "xctrunner" in low or ".wda" in low:
                        discovered_bundles.append(bid)
                if not paired_ok:
                    paired_ok = bool(dev.get_value("ProductVersion"))
            except Exception:
                paired_ok = False

        major_ver = 17
        try:
            major_ver = int(str(self.os_version).split(".")[0])
        except Exception:
            pass

        # Background Auto-Heal right after iOS Restore (Apple Configurator):
        # If USB iPhone is paired, has zero WDA bundles installed, and cooldown (>=120s) has elapsed:
        if (
            not discovered_bundles
            and paired_ok
            and dev is not None
            and not self._auto_installing_wda
            and (now - self._last_wda_auto_install_attempt >= 120.0)
        ):
            dev_mode_ok = True
            if major_ver >= 16:
                try:
                    dev_mode_ok = bool(dev.get_value("DeveloperModeStatus", domain="com.apple.security.mac.amfi"))
                except Exception:
                    dev_mode_ok = True
            self._last_wda_auto_install_attempt = now
            if not dev_mode_ok:
                # Automatically reveal "Developer Mode" menu in Settings -> Privacy & Security without needing Xcode
                try:
                    dev._send_action_to_amfi_lockdown(0)
                except Exception:
                    pass
                return
            ipa_path = self._resolve_bundled_wda_ipa()
            if ipa_path:
                self._auto_installing_wda = True
                threading.Thread(
                    target=self._auto_install_wda_after_restore,
                    args=(ipa_path,),
                    daemon=True,
                ).start()
                return

        if major_ver <= 16 and discovered_bundles:
            env = os.environ.copy()
            env["PYTHONPATH"] = _BUNDLED_SITE + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            try:
                self._wda_proc = subprocess.Popen(
                    ["/usr/bin/python3", "-m", "tidevice", "-u", self.serial, "xctest", "-B", discovered_bundles[0]],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass

        if not discovered_bundles:
            return

        for bundle_id in discovered_bundles:
            try:
                subprocess.run(
                    ["/usr/bin/xcrun", "devicectl", "device", "process", "launch", "--device", self.serial, bundle_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            except Exception:
                pass

    def _push_frame(self, b64_jpeg):
        if not b64_jpeg or not self.hub:
            return
        self.last_jpeg_b64 = b64_jpeg
        meta_json = json.dumps(self.to_meta(loading=0), ensure_ascii=False)
        self.hub.broadcast_text(f"{meta_json}&&data:image/jpeg;base64,{b64_jpeg}")

    def _stream_worker(self):
        placeholder = generate_placeholder_jpeg(self.name, "Connecting to iPhone...")
        first_shot = self._capture_usb_screenshot_jpeg()
        if first_shot:
            self._push_frame(first_shot)
        elif placeholder:
            self._push_frame(placeholder)

        while self.active:
            if not self._ensure_wda_session():
                self._try_launch_installed_wda()
                live_shot = self._capture_usb_screenshot_jpeg()
                if live_shot:
                    self._push_frame(live_shot)
                    time.sleep(0.35)
                else:
                    if placeholder:
                        self._push_frame(placeholder)
                    time.sleep(2.0)
                continue

            streamed = self._read_mjpeg_stream()
            if not streamed and self.active:
                try:
                    st, shot = self._wda_raw_request("GET", "/screenshot", timeout=3.0)
                    b64_png = shot.get("value") if st == 200 else None
                    if isinstance(b64_png, str) and len(b64_png) > 100:
                        self.last_jpeg_b64 = b64_png
                        meta_json = json.dumps(self.to_meta(loading=0), ensure_ascii=False)
                        self.hub.broadcast_text(f"{meta_json}&&data:image/png;base64,{b64_png}")
                    else:
                        self.wda_ready = False
                except Exception:
                    self.wda_ready = False
                time.sleep(max(0.12, 1.0 / max(1, self.fps_limit)))

    def _read_mjpeg_stream(self):
        sock = None
        try:
            if self.device_id is not None:
                sock = UsbmuxClient.connect_device_port(self.device_id, 9100, timeout=3.0)
            elif self.ip_addr:
                sock = socket.create_connection((self.ip_addr, 9100), timeout=3.0)
            else:
                return False
            sock.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n")
            sock.settimeout(5.0)
            buf = bytearray()
            last_emit = 0.0
            while self.active:
                chunk = sock.recv(131072)
                if not chunk:
                    break
                buf.extend(chunk)
                # Drain any immediately buffered bytes so we always push the freshest frame with zero lag
                while self.active:
                    rdy, _, _ = select.select([sock], [], [], 0.0)
                    if not rdy:
                        break
                    more = sock.recv(131072)
                    if not more:
                        break
                    buf.extend(more)
                latest_jpeg = None
                while True:
                    soi = buf.find(b"\xff\xd8")
                    if soi == -1:
                        if len(buf) > 131072:
                            del buf[:-2]
                        break
                    eoi = buf.find(b"\xff\xd9", soi + 2)
                    if eoi == -1:
                        if soi > 0:
                            del buf[:soi]
                        if len(buf) > 1048576:
                            buf.clear()
                        break
                    latest_jpeg = bytes(buf[soi : eoi + 2])
                    del buf[: eoi + 2]
                if latest_jpeg is not None:
                    now = time.perf_counter()
                    min_dt = 1.0 / max(55, min(60, self.fps_limit))
                    if now - last_emit >= min_dt:
                        last_emit = now
                        self._push_frame(base64.b64encode(latest_jpeg).decode("ascii"))
            return True
        except Exception:
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def _to_logic_coords(self, x, y, src_w, src_h):
        w = src_w if src_w > 0 else self.width
        h = src_h if src_h > 0 else self.height
        # Keep portrait/landscape sync if device rotated
        if (w > h and self.logic_w < self.logic_h) or (w < h and self.logic_w > self.logic_h):
            self.logic_w, self.logic_h = self.logic_h, self.logic_w
        lx = max(1, min(self.logic_w - 1, int(round(x * self.logic_w / max(1, w)))))
        ly = max(1, min(self.logic_h - 1, int(round(y * self.logic_h / max(1, h)))))
        return lx, ly

    def handle_control_bytes(self, raw_bytes):
        if not raw_bytes or not self.wda_ready:
            return
        msg_type = raw_bytes[0]

        # TYPE_KEYCODE = 0
        if msg_type == 0 and len(raw_bytes) >= 14:
            action = raw_bytes[1]
            if action != 0:  # process key down only
                return
            keycode, _repeat, meta = struct.unpack(">iii", raw_bytes[2:14])
            ctrl_or_cmd = (meta & 0x1000) != 0 or (meta & 0x10000) != 0 or raw_bytes[12] == 16
            if keycode == 50 and ctrl_or_cmd:  # Ctrl+V / Cmd+V
                clip = get_mac_clipboard()
                if clip:
                    self._enqueue_action(self.send_text, clip)
                return
            if keycode == 3:  # HOME
                self._enqueue_action(self.press_button, "home")
            elif keycode == 187:  # APP_SWITCH (Menu)
                self._enqueue_action(self.open_app_switcher)
            elif keycode == 4:  # BACK
                self._enqueue_action(self.swipe_back)
            elif keycode == 24:  # VOLUME_UP
                self._enqueue_action(self.press_button, "volumeUp")
            elif keycode == 25:  # VOLUME_DOWN
                self._enqueue_action(self.press_button, "volumeDown")
            elif keycode == 26:  # POWER
                self._enqueue_action(self.toggle_lock)
            elif keycode == 66 or keycode == 160:  # ENTER / NUMPAD_ENTER
                self._enqueue_action(self.send_text, "\n")
            elif keycode == 67 or keycode == 112:  # BACKSPACE / DELETE
                self._enqueue_action(self.send_text, "\b")
            elif keycode in ANDROID_KEYMAP:
                shift = (meta & 0x1) != 0 or (meta & 0x100000) != 0
                normal_ch, shift_ch = ANDROID_KEYMAP[keycode]
                self._enqueue_action(self.send_text, shift_ch if shift else normal_ch)

        # TYPE_TEXT = 1 (int8(1) + int32BE(len) + utf8_bytes)
        elif msg_type == 1 and len(raw_bytes) >= 5:
            tlen = struct.unpack(">I", raw_bytes[1:5])[0]
            txt = raw_bytes[5 : 5 + tlen].decode("utf-8", errors="ignore")
            if txt:
                self._enqueue_action(self.send_text, txt)

        # TYPE_TOUCH = 2
        elif msg_type == 2 and len(raw_bytes) >= 22:
            action = raw_bytes[1]  # 0=down, 1=up, 2=move
            x, y, rw, rh = struct.unpack(">IIHH", raw_bytes[10:22])
            lx, ly = self._to_logic_coords(x, y, rw, rh)
            now_mono = time.monotonic()
            if action == 0:
                self._touch_down = (lx, ly)
                self._touch_last = (lx, ly)
                self._touch_down_ts = now_mono
            elif action == 2:
                self._touch_last = (lx, ly)
            elif action == 1:
                if self._touch_down is not None:
                    sx, sy = self._touch_down
                    ex, ey = lx, ly
                    raw_dt = max(0.0, now_mono - self._touch_down_ts)
                    dt = max(0.03, raw_dt)
                    self._touch_down = None
                    self._last_touch_up_ts = now_mono
                    dist = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
                    if dist <= 12:
                        if raw_dt >= 0.55:
                            self._enqueue_action(self._wda_touch_hold, sx, sy, min(raw_dt, 2.5))
                        else:
                            self._enqueue_action(self._wda_tap, sx, sy)
                    else:
                        # Snappy swipe duration (80ms - 180ms)
                        move_ms = int(min(max(dt * 650.0, 80.0), 180.0))
                        self._enqueue_action(self._wda_swipe, sx, sy, ex, ey, move_ms)
                elif now_mono - self._last_touch_up_ts > 0.08:
                    # Fallback if mousedown was missed (e.g. window focus click): never drop a quick tap
                    self._last_touch_up_ts = now_mono
                    self._enqueue_action(self._wda_tap, lx, ly)

        # TYPE_SCROLL = 3 (u8(3) + u32BE(x) + u32BE(y) + u16BE(w) + u16BE(h) + i16BE(hScroll) + i16BE(vScroll))
        elif msg_type == 3 and len(raw_bytes) >= 17:
            now = time.time()
            if now - self._last_scroll_ts < 0.045:
                return
            self._last_scroll_ts = now
            x, y, rw, rh, h_scroll, v_scroll = struct.unpack(">IIHHhh", raw_bytes[1:17])
            lx, ly = self._to_logic_coords(x, y, rw, rh)
            step_y = max(120, int(self.logic_h * 0.32))
            step_x = max(100, int(self.logic_w * 0.35))
            scroll_target = None
            if v_scroll != 0:
                # Positive vScroll = wheel up = scroll page up (finger moves down)
                ey = min(self.logic_h - 20, ly + step_y) if v_scroll > 0 else max(20, ly - step_y)
                scroll_target = (lx, ly, lx, ey, 105)
            elif h_scroll != 0:
                ex = min(self.logic_w - 20, lx + step_x) if h_scroll > 0 else max(20, lx - step_x)
                scroll_target = (lx, ly, ex, ly, 105)
            if scroll_target is not None:
                with self._scroll_lock:
                    already_queued = self._latest_scroll is not None
                    self._latest_scroll = scroll_target
                if not already_queued:
                    self._enqueue_action(self._flush_latest_scroll)

        # TYPE_BACK_OR_SCREEN_ON = 4
        elif msg_type == 4:
            if len(raw_bytes) < 2 or raw_bytes[1] == 0:
                self._enqueue_action(self.swipe_back)

        # TYPE_EXPAND_NOTIFICATION_PANEL = 5
        elif msg_type == 5:
            self._enqueue_action(self._wda_swipe, self.logic_w // 2, 2, self.logic_w // 2, int(self.logic_h * 0.75), 150)

        # TYPE_COLLAPSE_PANELS = 7
        elif msg_type == 7:
            self._enqueue_action(self._wda_swipe, self.logic_w // 2, self.logic_h - 8, self.logic_w // 2, int(self.logic_h * 0.25), 150)

        # TYPE_SET_CLIPBOARD = 9
        elif msg_type == 9 and len(raw_bytes) > 13:
            # scrcpy set_clipboard: type(1) + sequence(8) + paste(1) + len(4) + utf8
            paste_flag = raw_bytes[9] != 0
            clen = struct.unpack(">I", raw_bytes[10:14])[0]
            txt = raw_bytes[14 : 14 + clen].decode("utf-8", errors="ignore")
            self._enqueue_action(self.push_pasteboard, txt)
            if paste_flag and txt:
                self._enqueue_action(self.send_text, txt)

        # TYPE_SET_SCREEN_POWER_MODE = 10
        elif msg_type == 10 and len(raw_bytes) >= 2:
            mode = raw_bytes[1]
            self._enqueue_action(self.set_lock, mode == 0)

    def _flush_latest_scroll(self):
        with self._scroll_lock:
            item = self._latest_scroll
            self._latest_scroll = None
        if item is not None:
            sx, sy, ex, ey, move_ms = item
            self._wda_swipe(sx, sy, ex, ey, move_ms)

    def _try_fast_wda(self, path, payload, timeout=2.5):
        if self._has_fast_wda is False:
            return False
        try:
            st, _ = self._wda_fast_request("POST", path, payload=payload, timeout=timeout)
            if st == 200:
                self._has_fast_wda = True
                return True
            if st == 404:
                self._has_fast_wda = False
                return False
        except ConnectionRefusedError:
            self.wda_ready = False
            if self._has_fast_wda is True:
                return True
        except Exception:
            if self._has_fast_wda is True:
                return True
        return False

    def _wda_tap(self, x, y):
        ix, iy = int(x), int(y)
        # Synthesize a 55ms stationary hold + liftUp at 63ms (~4 frames @ 60Hz, matching XCTest's
        # native 0.05s-0.065s tap duration) so SpringBoard SBIconView & Dock never drop sub-frame taps.
        if self._try_fast_wda(
            "/wda/fastSwipe",
            {"sx": ix, "sy": iy, "ex": ix, "ey": iy, "duration": 0.055},
        ):
            return
        if self._try_fast_wda("/wda/fastTap", {"x": ix, "y": iy}):
            return
        self._wda_session_request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": ix, "y": iy},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 55},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    def _wda_touch_hold(self, x, y, duration):
        if self._try_fast_wda("/wda/fastHold", {"x": int(x), "y": int(y), "duration": round(float(duration), 3)}):
            return
        self._wda_session_request("POST", "/wda/touchAndHold", {"x": int(x), "y": int(y), "duration": float(duration)})

    def _wda_swipe(self, sx, sy, ex, ey, move_ms=110):
        clamped_ms = int(min(max(move_ms, 80), 180))
        if self._try_fast_wda(
            "/wda/fastSwipe",
            {"sx": int(sx), "sy": int(sy), "ex": int(ex), "ey": int(ey), "duration": round(clamped_ms / 1000.0, 3)},
        ):
            return
        self._wda_session_request(
            "POST",
            "/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": int(sx), "y": int(sy)},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 10},
                            {"type": "pointerMove", "duration": clamped_ms, "x": int(ex), "y": int(ey)},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    def swipe_back(self):
        mid_y = self.logic_h // 2
        self._wda_swipe(3, mid_y, int(self.logic_w * 0.75), mid_y, move_ms=115)

    def open_app_switcher(self):
        if self.model in HOME_BUTTON_MODELS:
            # Double press Home for Touch ID iPhones
            self.press_button("home")
            time.sleep(0.05)
            self.press_button("home")
        else:
            # Swipe up from bottom edge and pause in middle for Face ID iPhones
            cx = self.logic_w // 2
            self._wda_session_request(
                "POST",
                "/actions",
                {
                    "actions": [
                        {
                            "type": "pointer",
                            "id": "finger1",
                            "parameters": {"pointerType": "touch"},
                            "actions": [
                                {"type": "pointerMove", "duration": 0, "x": cx, "y": self.logic_h - 4},
                                {"type": "pointerDown", "button": 0},
                                {"type": "pointerMove", "duration": 180, "x": cx, "y": int(self.logic_h * 0.55)},
                                {"type": "pause", "duration": 320},
                                {"type": "pointerUp", "button": 0},
                            ],
                        }
                    ]
                },
            )

    def press_button(self, button_name="home"):
        if self._try_fast_wda("/wda/fastButton", {"name": button_name}):
            return
        try:
            self._wda_session_request("POST", "/wda/pressButton", {"name": button_name})
        except Exception:
            try:
                self._wda_raw_request("POST", "/wda/pressButton", {"name": button_name})
            except Exception:
                pass

    def is_locked(self):
        try:
            st, res = self._wda_raw_request("GET", "/wda/locked", timeout=2.0)
            return bool(res.get("value", False)) if st == 200 else False
        except Exception:
            return False

    def set_lock(self, lock_flag):
        try:
            self._wda_raw_request("POST", "/wda/lock" if lock_flag else "/wda/unlock", {})
        except Exception:
            pass

    def toggle_lock(self):
        self.set_lock(not self.is_locked())

    def send_text(self, text):
        if not text:
            return
        if self._try_fast_wda("/wda/fastKeys", {"text": text}):
            return
        try:
            self._wda_session_request("POST", "/wda/keys", {"value": list(text)})
        except Exception:
            pass

    def push_pasteboard(self, text):
        try:
            b64 = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
            self._wda_session_request("POST", "/wda/setPasteboard", {"content": b64, "contentType": "plaintext"})
        except Exception:
            try:
                b64 = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
                self._wda_raw_request("POST", "/wda/setPasteboard", {"content": b64, "contentType": "plaintext"})
            except Exception:
                pass

    def pull_pasteboard(self):
        try:
            st, res = self._wda_session_request("POST", "/wda/getPasteboard", {"contentType": "plaintext"})
            val = res.get("value") or ""
            return base64.b64decode(val).decode("utf-8", errors="ignore") if val else ""
        except Exception:
            return ""

    def save_screenshot(self, out_file):
        out_file = normalize_mac_path(out_file)
        try:
            if self.wda_ready:
                st, res = self._wda_raw_request("GET", "/screenshot", timeout=4.0)
                b64 = res.get("value") if st == 200 else None
                if b64:
                    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
                    with open(out_file, "wb") as f:
                        f.write(base64.b64decode(b64))
                    return True
            dev = self._get_tidevice()
            if dev is not None:
                os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
                dev.screenshot().save(out_file)
                return True
        except Exception:
            pass
        return False

    # --- App Management ---

    def list_apps(self):
        out = []
        dev = self._get_tidevice()
        if dev is not None:
            try:
                for app in dev.installation.iter_installed(app_type="User"):
                    bid = app.get("CFBundleIdentifier") or ""
                    if not bid or "webdriveragent" in bid.lower() or "xctrunner" in bid.lower():
                        continue
                    name = app.get("CFBundleDisplayName") or app.get("CFBundleName") or bid
                    ver = app.get("CFBundleShortVersionString") or app.get("CFBundleVersion") or "1.0"
                    out.append({"bundle_id": bid, "app_name": name, "version": str(ver)})
            except Exception:
                pass
        return out

    def launch_app(self, bundle_id):
        if not bundle_id:
            return False
        if self.is_locked():
            self.set_lock(False)
            time.sleep(0.2)
        if self.wda_ready:
            try:
                st, _ = self._wda_raw_request("POST", "/wda/apps/launchUnattached", {"bundleId": bundle_id}, timeout=4.0)
                if st == 200:
                    return True
            except Exception:
                pass
        dev = self._get_tidevice()
        if dev is not None:
            try:
                dev.app_start(bundle_id)
                return True
            except Exception:
                pass
        try:
            subprocess.Popen(
                ["/usr/bin/xcrun", "devicectl", "device", "process", "launch", "--device", self.serial, bundle_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def stop_app(self, bundle_id):
        if not bundle_id:
            return False
        if self.wda_ready:
            try:
                self._wda_session_request("POST", "/wda/apps/terminate", {"bundleId": bundle_id}, timeout=3.0)
                return True
            except Exception:
                pass
        dev = self._get_tidevice()
        if dev is not None:
            try:
                dev.app_stop(bundle_id)
                return True
            except Exception:
                pass
        return False

    def install_ipa(self, ipa_path):
        ipa_path = normalize_mac_path(ipa_path)
        if not ipa_path or not os.path.exists(ipa_path):
            return "File not found"
        dev = self._get_tidevice()
        if dev is not None:
            try:
                dev.app_install(ipa_path)
                return "OK"
            except Exception as e:
                return str(e)
        try:
            subprocess.run(
                ["/usr/bin/xcrun", "devicectl", "device", "install", "app", "--device", self.serial, ipa_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
            return "OK"
        except Exception as e:
            return str(e)

    def uninstall_app(self, bundle_id):
        if not bundle_id:
            return 0
        dev = self._get_tidevice()
        if dev is not None:
            try:
                dev.app_uninstall(bundle_id)
                return 1
            except Exception:
                return 0
        try:
            subprocess.run(
                ["/usr/bin/xcrun", "devicectl", "device", "uninstall", "app", "--device", self.serial, bundle_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
            return 1
        except Exception:
            return 0

    def reboot_device(self):
        dev = self._get_tidevice()
        if dev is not None:
            try:
                dev.reboot()
                return True
            except Exception:
                pass
        try:
            subprocess.Popen(
                ["/usr/bin/xcrun", "devicectl", "device", "reboot", "--device", self.serial],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    # --- Apple File Conduit (AFC) File Management ---

    def afc_list_dir(self, rel_path):
        dev = self._get_tidevice()
        if dev is None:
            return ""
        p = normalize_mac_path(rel_path or "/")
        if not p.startswith("/"):
            p = "/" + p
        try:
            sync = dev.sync
            entries = []
            for name in sync.listdir(p):
                if name in (".", ".."):
                    continue
                full = p.rstrip("/") + "/" + name
                try:
                    st = sync.stat(full)
                    ifmt = st.get("st_ifmt") if isinstance(st, dict) else getattr(st, "st_ifmt", None)
                    is_dir = (ifmt == "S_IFDIR" or ifmt == 0o040000)
                except Exception:
                    is_dir = False
                entries.append(name + ("/" if is_dir else ""))
            return "\n".join(entries)
        except Exception:
            return ""

    def afc_pull(self, src_path, dst_path):
        dev = self._get_tidevice()
        if dev is None:
            return False
        src = normalize_mac_path(src_path)
        dst = normalize_mac_path(dst_path)
        if not src.startswith("/"):
            src = "/" + src
        try:
            os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
            dev.sync.pull(src, dst)
            return True
        except Exception:
            return False

    def afc_remove(self, target_path):
        dev = self._get_tidevice()
        if dev is None:
            return "Device unavailable"
        p = normalize_mac_path(target_path)
        if not p.startswith("/"):
            p = "/" + p
        try:
            st = dev.sync.stat(p)
            ifmt = st.get("st_ifmt") if isinstance(st, dict) else getattr(st, "st_ifmt", None)
            if ifmt == "S_IFDIR" or ifmt == 0o040000:
                dev.sync.rmtree(p)
            else:
                dev.sync.remove(p)
            return None
        except Exception as e:
            return str(e)

    def push_media_file(self, local_path):
        local_path = normalize_mac_path(local_path)
        if not local_path or not os.path.isfile(local_path):
            return "File not found"
        dev = self._get_tidevice()
        if dev is None:
            return "Device unavailable"
        try:
            fname = os.path.basename(local_path)
            remote_dir = "/Downloads"
            try:
                dev.sync.mkdir(remote_dir)
            except Exception:
                pass
            remote_path = f"{remote_dir}/{fname}"
            with open(local_path, "rb") as f:
                dev.sync.push_content(remote_path, f)
            return "OK"
        except Exception as e:
            return str(e)

    # --- Macro Action Playback ---

    def play_macro(self, key_events):
        self._macro_stop_flag = False
        if not isinstance(key_events, list):
            return
        for item in key_events:
            if self._macro_stop_flag or not self.active:
                break
            if not isinstance(item, dict):
                continue
            delay_ms = int(item.get("delay") or 0)
            if delay_ms > 0:
                time.sleep(min(delay_ms / 1000.0, 10.0))
            ev = item.get("event")
            if isinstance(ev, list) and ev:
                self.handle_control_bytes(bytes(x & 0xFF for x in ev))

    def stop_macro(self):
        self._macro_stop_flag = True


# ---------------------------------------------------------------------------
# Device Manager (macOS usbmuxd + Lockdown + CoreDevice)
# ---------------------------------------------------------------------------

class DeviceManager:
    def __init__(self, hub, emit_event):
        self.hub = hub
        self.emit_event = emit_event
        self.sessions = {}
        self.lock = threading.Lock()
        self._devicectl_cache = {}
        self._last_devicectl_ts = 0.0

    def start(self):
        self.hub.set_on_connect(self._on_ws_client_connected)
        threading.Thread(target=self._poll_usb_loop, daemon=True).start()

    def _on_ws_client_connected(self, conn):
        time.sleep(0.15)
        with self.lock:
            sessions = list(self.sessions.values())
        for s in sessions:
            meta_json = json.dumps(s.to_meta(loading=0), ensure_ascii=False)
            b64 = s.last_jpeg_b64 or generate_placeholder_jpeg(s.name, "Connected via macOS USB")
            self.hub.send_text_to(conn, f"{meta_json}&&data:image/jpeg;base64,{b64}")

    def _refresh_devicectl_metadata(self):
        now = time.time()
        if now - self._last_devicectl_ts < 8.0:
            return
        self._last_devicectl_ts = now
        tmp_json = os.path.join(CACHE_DIR, "devicectl_devices.json")
        try:
            subprocess.run(
                ["/usr/bin/xcrun", "devicectl", "list", "devices", "--json-output", tmp_json],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
            )
            if os.path.exists(tmp_json):
                data = json.load(open(tmp_json, "r", encoding="utf-8"))
                for dev in (data.get("result") or {}).get("devices") or []:
                    hw = dev.get("hardwareProperties") or {}
                    dp = dev.get("deviceProperties") or {}
                    udid = hw.get("udid") or ""
                    if udid:
                        prod_type = hw.get("productType") or ""
                        marketing = hw.get("marketingName") or IPHONE_MODELS.get(prod_type) or prod_type or "iPhone"
                        self._devicectl_cache[udid] = {
                            "name": dp.get("name") or marketing,
                            "model": marketing,
                            "os_version": dp.get("osVersionNumber") or "17.0",
                        }
        except Exception:
            pass

    @staticmethod
    def _query_lockdown_info(device_id):
        sock = None
        try:
            sock = UsbmuxClient.connect_device_port(device_id, 62078, timeout=2.0)
            req = plistlib.dumps({"Request": "GetValue", "Label": "XiaoweiMacOS"})
            sock.sendall(struct.pack(">I", len(req)) + req)
            rlen = struct.unpack(">I", sock.recv(4))[0]
            buf = b""
            while len(buf) < rlen:
                chunk = sock.recv(rlen - len(buf))
                if not chunk:
                    break
                buf += chunk
            val = plistlib.loads(buf).get("Value") or {}
            prod_type = val.get("ProductType") or ""
            model = IPHONE_MODELS.get(prod_type) or prod_type or "iPhone"
            return {
                "name": val.get("DeviceName") or model,
                "model": model,
                "os_version": val.get("ProductVersion") or "16.0",
            }
        except Exception:
            return {}
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def _poll_usb_loop(self):
        while True:
            try:
                usb_list = [d for d in UsbmuxClient.list_devices() if d.get("connection_type") == "USB"]
                if usb_list:
                    self._refresh_devicectl_metadata()
                seen = set()
                for d in usb_list:
                    serial = d["serial"]
                    seen.add(serial)
                    with self.lock:
                        existing = self.sessions.get(serial)
                    if existing is None:
                        meta = self._devicectl_cache.get(serial) or self._query_lockdown_info(d["device_id"])
                        sess = IOSDeviceSession(
                            serial=serial,
                            device_id=d["device_id"],
                            name=meta.get("name", f"iPhone ({serial[-4:]})"),
                            model=meta.get("model", "iPhone"),
                            os_version=meta.get("os_version", "16.0"),
                            hub=self.hub,
                            emit_event=self.emit_event,
                        )
                        with self.lock:
                            self.sessions[serial] = sess
                    else:
                        existing.device_id = d["device_id"]

                removed = []
                with self.lock:
                    for serial in list(self.sessions.keys()):
                        if "." not in serial and serial not in seen:
                            sess = self.sessions.pop(serial)
                            removed.append(sess)
                for sess in removed:
                    sess.stop()
                    self.emit_event("pull_out_device", json.dumps({"serial": sess.serial}))
                    self.hub.broadcast_text(
                        json.dumps({"serial": sess.serial, "width": 0, "height": 0, "loading": 0}) + "&&"
                    )
            except Exception:
                pass
            time.sleep(1.5)

    def handle_ws_message(self, text):
        try:
            msg = json.loads(text)
        except Exception:
            return
        serial = msg.get("serial")
        if not serial:
            return
        with self.lock:
            sess = self.sessions.get(serial)
        if not sess:
            return
        code = msg.get("code", 0)
        if code == 1:
            fps = int(msg.get("fps_model") or 60)
            sess.fps_limit = max(58, min(60, fps))
        elif code == 2:
            scr_off = msg.get("screen_off")
            if scr_off == 0:
                sess._enqueue_action(sess.set_lock, False)
            elif scr_off == 1:
                sess._enqueue_action(sess.set_lock, True)
        elif code == 0:
            ev = msg.get("event")
            if isinstance(ev, list) and ev:
                sess.handle_control_bytes(bytes(x & 0xFF for x in ev))

    def handle_ws_binary(self, raw_bytes):
        if not raw_bytes:
            return
        with self.lock:
            sessions = list(self.sessions.values())
        for sess in sessions:
            sess.handle_control_bytes(raw_bytes)


# ---------------------------------------------------------------------------
# Local SQLite Pool (for Tauri plugin:sql|*)
# ---------------------------------------------------------------------------

class SqlitePool:
    def __init__(self):
        self.lock = threading.Lock()
        self.conns = {}

    def _resolve_db_path(self, db_spec):
        name = db_spec
        if name.startswith("sqlite:"):
            name = name[len("sqlite:") :]
        if not os.path.isabs(name):
            name = os.path.join(APP_SUPPORT, name)
        os.makedirs(os.path.dirname(name), exist_ok=True)
        return name

    def _get_conn(self, db_spec):
        path = self._resolve_db_path(db_spec)
        with self.lock:
            conn = self.conns.get(path)
            if conn is None:
                conn = sqlite3.connect(path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self.conns[path] = conn
            return conn

    @staticmethod
    def _convert_placeholders(query):
        import re
        return re.sub(r"\$(\d+)", r"?\1", query)

    def load(self, db_spec):
        self._get_conn(db_spec)
        return db_spec

    def execute(self, db_spec, query, values):
        conn = self._get_conn(db_spec)
        sql = self._convert_placeholders(query)
        with self.lock:
            cur = conn.cursor()
            cur.execute(sql, values or [])
            conn.commit()
            return [cur.rowcount if cur.rowcount >= 0 else 0, cur.lastrowid or 0]

    def select(self, db_spec, query, values):
        conn = self._get_conn(db_spec)
        sql = self._convert_placeholders(query)
        with self.lock:
            cur = conn.cursor()
            cur.execute(sql, values or [])
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def close(self, db_spec):
        if not db_spec:
            return True
        path = self._resolve_db_path(db_spec)
        with self.lock:
            conn = self.conns.pop(path, None)
            if conn:
                conn.close()
        return True


# ---------------------------------------------------------------------------
# Tauri Command Dispatcher
# ---------------------------------------------------------------------------

class CommandRouter:
    def __init__(self, ws_hub, device_mgr, sql_pool):
        self.ws_hub = ws_hub
        self.device_mgr = device_mgr
        self.sql_pool = sql_pool
        self.pending_events = []
        self.event_lock = threading.Lock()
        self.computer_id = self._get_mac_hardware_uuid()

    @staticmethod
    def _get_mac_hardware_uuid():
        try:
            out = subprocess.check_output(
                ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode("utf-8", errors="ignore")
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
        return socket.gethostname()

    def queue_event(self, event_name, payload):
        with self.event_lock:
            self.pending_events.append({"event": event_name, "payload": payload})

    def drain_events(self):
        with self.event_lock:
            ev = self.pending_events[:]
            self.pending_events.clear()
            return ev

    def dispatch(self, cmd, args):
        args = args or {}

        # SQL plugin commands
        if cmd == "plugin:sql|load":
            return self.sql_pool.load(args.get("db", "sqlite:xiaowei.db"))
        if cmd == "plugin:sql|execute":
            return self.sql_pool.execute(args.get("db", "sqlite:xiaowei.db"), args.get("query", ""), args.get("values", []))
        if cmd == "plugin:sql|select":
            return self.sql_pool.select(args.get("db", "sqlite:xiaowei.db"), args.get("query", ""), args.get("values", []))
        if cmd == "plugin:sql|close":
            return self.sql_pool.close(args.get("db", ""))

        # Core startup & config commands
        if cmd == "read_sys_config":
            return json.dumps({"brand": {"brand_code": "WECAN0A95C"}})
        if cmd == "read_config":
            if os.path.exists(CONFIG_PATH):
                try:
                    return open(CONFIG_PATH, "r", encoding="utf-8").read()
                except Exception:
                    pass
            return json.dumps(
                {
                    "input": {"switch": True},
                    "encoder": {"use_soft_encoder": False},
                    "airplay": {"name": ""},
                    "adb": {"mutil": False},
                }
            )
        if cmd == "write_config":
            s = args.get("strConfig")
            if isinstance(s, str):
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    f.write(s)
            return True
        if cmd == "cur_env":
            return "prod"
        if cmd == "get_ws_port":
            return self.ws_hub.port
        if cmd == "get_windows_language":
            return "vi-VN"
        if cmd == "get_computer_id":
            return self.computer_id
        if cmd == "get_computer_name":
            return socket.gethostname()
        if cmd == "get_cur_time":
            return {"timestamp": int(time.time() * 1000)}
        if cmd == "is_duration_greater_than_24_hours":
            old_ts = int(args.get("oldTimestamp") or 0)
            return (int(time.time() * 1000) - old_ts) > 86400 * 1000
        if cmd == "check_service":
            return {"code": 200, "msg": "ok"}
        if cmd == "check_auto_update":
            return {"is_update": False, "is_forced_update": False, "down_load_url": ""}
        if cmd == "version_notice":
            return {"code": 200, "data": {"Content": ""}}
        if cmd == "oem_adv_config":
            return {"code": 200, "data": {}}
        if cmd == "get_system_config":
            return {"code": 200, "data": {}}
        if cmd == "get_brand_owner":
            return {"cv_switch": 0}
        if cmd == "get_brand_cloud_service":
            return {"code": 0}
        if cmd == "check_brand_stop":
            return False
        if cmd == "check_client_token":
            return False
        if cmd == "get_device_info":
            return {
                "is_vip": False,
                "device_qty": 10,
                "accessible_qty": 10,
                "hid_qty": 10,
                "max_bound_computer": 1,
                "act_bind_times": 0,
            }

        # Device discovery & status
        if cmd == "get_usb_devices":
            with self.device_mgr.lock:
                return len(self.device_mgr.sessions)
        if cmd == "get_device_list":
            with self.device_mgr.lock:
                return [s.to_meta() for s in self.device_mgr.sessions.values()]
        if cmd == "check_adb_device":
            with self.device_mgr.lock:
                return "\n".join(self.device_mgr.sessions.keys())
        if cmd == "get_device_mode":
            return 0
        if cmd == "device_is_accessible":
            return False
        if cmd == "has_hid_devices":
            return False
        if cmd == "check_hid_app_installed":
            return True
        if cmd == "get_root":
            return 0
        if cmd == "get_density":
            return 326
        if cmd == "get_serial_ip":
            serial = args.get("serial", "")
            with self.device_mgr.lock:
                sess = self.device_mgr.sessions.get(serial)
                return sess.ip_addr if sess else ""
        if cmd == "get_ip_serial":
            ip = args.get("ip", "")
            with self.device_mgr.lock:
                for sess in self.device_mgr.sessions.values():
                    if sess.ip_addr and sess.ip_addr == ip:
                        return sess.serial
            return ""
        if cmd == "get_size":
            serial = args.get("serial", "")
            with self.device_mgr.lock:
                sess = self.device_mgr.sessions.get(serial)
                if sess:
                    return f"{sess.width}x{sess.height}"
            return "750x1334"
        if cmd == "get_device_share_info":
            return "{}"
        if cmd == "p2p_get_share_list":
            return "[]"
        if cmd == "cloud_phone_tag_list":
            return []

        # Batch Provisioning & Apple Configurator Wi-Fi Profile RPC endpoints
        if cmd == "batch_provision_devices":
            res_dir = os.path.dirname(os.path.abspath(__file__))
            if res_dir not in sys.path:
                sys.path.insert(0, res_dir)
            import batch_provision_ios
            return batch_provision_ios.run_batch_provision(
                force=bool(args.get("force")),
                renew=bool(args.get("renew")),
                quiet=True,
            )
        if cmd == "generate_wifi_mobileconfig":
            res_dir = os.path.dirname(os.path.abspath(__file__))
            if res_dir not in sys.path:
                sys.path.insert(0, res_dir)
            import batch_provision_ios
            out_p = batch_provision_ios.generate_wifi_mobileconfig(
                ssid=str(args.get("ssid") or ""),
                password=str(args.get("password") or ""),
                out_path=str(args.get("outPath") or ""),
                hidden=bool(args.get("hidden")),
            )
            return {"ok": True, "path": out_p}

        # Per-device commands
        serial = args.get("serial", "")
        with self.device_mgr.lock:
            sess = self.device_mgr.sessions.get(serial) if serial else None

        if cmd == "screen_locked":
            return sess.is_locked() if sess else False
        if cmd == "lock_screen":
            if sess:
                lock_val = args.get("lock")
                # In Xiaowei UI: lock=1 means lock screen, lock=2 means wake/unlock screen!
                should_lock = (lock_val == 1 or lock_val is True)
                sess._enqueue_action(sess.set_lock, should_lock)
            return True
        if cmd in ("input_text", "paste_text", "paste_pwd"):
            msg = args.get("message") or args.get("text") or ""
            if sess and msg:
                sess._enqueue_action(sess.send_text, msg)
            return True
        if cmd == "input_enter":
            if sess:
                sess._enqueue_action(sess.send_text, "\n")
                return 1
            return 0
        if cmd == "push_pasteboard":
            txt = args.get("text") or args.get("message") or ""
            if sess:
                sess._enqueue_action(sess.push_pasteboard, txt)
            return True
        if cmd in ("pull_pasteboard", "copy"):
            return sess.pull_pasteboard() if sess else ""
        if cmd == "paste":
            if sess:
                clip = get_mac_clipboard() or sess.pull_pasteboard()
                if clip:
                    sess._enqueue_action(sess.send_text, clip)
            return True

        # Screenshots & Media
        if cmd == "screenshot":
            out_file = args.get("outFile") or os.path.join(
                os.path.expanduser("~/Pictures"), f"xiaowei_{int(time.time())}.png"
            )
            return sess.save_screenshot(out_file) if sess else False
        if cmd == "screenshot_push":
            if sess:
                out_dir = os.path.expanduser("~/Pictures/XiaoweiScreenshots")
                os.makedirs(out_dir, exist_ok=True)
                out_file = os.path.join(out_dir, f"{sess.name}_{int(time.time())}.png")
                return sess.save_screenshot(out_file)
            return False
        if cmd in ("push_photo", "push_video"):
            p = args.get("path") or ""
            return sess.push_media_file(p) if sess else "Device not connected"
        if cmd == "download_image":
            url = args.get("url") or ""
            save_path = normalize_mac_path(args.get("savePath") or "")
            if url and save_path:
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                    urllib.request.urlretrieve(url, save_path)
                    return True
                except Exception:
                    return False
            return False

        # App Manager
        if cmd == "get_apk_list":
            return json.dumps(sess.list_apps(), ensure_ascii=False) if sess else "[]"
        if cmd == "get_apk_info":
            return ""
        if cmd == "launch_app":
            bundle_id = args.get("package") or args.get("bundleId") or ""
            return sess.launch_app(bundle_id) if sess else False
        if cmd == "app_stop":
            bundle_id = args.get("activity") or args.get("bundleId") or args.get("package") or ""
            return sess.stop_app(bundle_id) if sess else False
        if cmd in ("app_install", "install_apk"):
            app_path = args.get("path") or args.get("fileName") or args.get("file_name") or ""
            return sess.install_ipa(app_path) if sess else "Device not connected"
        if cmd == "app_uninstall":
            bundle_id = args.get("bundleId") or args.get("package") or ""
            return sess.uninstall_app(bundle_id) if sess else 0

        # File Manager (AFC)
        if cmd == "file_view":
            return sess.afc_list_dir(args.get("path", "/")) if sess else ""
        if cmd == "file_pull":
            return sess.afc_pull(args.get("srcPath", ""), args.get("dstPath", "")) if sess else False
        if cmd == "file_remove":
            return sess.afc_remove(args.get("path", "")) if sess else "Device not connected"

        # Macro / Action Recording Playback
        if cmd == "action_play":
            if sess:
                key_events = args.get("keyEvents") or []
                threading.Thread(target=sess.play_macro, args=(key_events,), daemon=True).start()
            return True
        if cmd == "action_act":
            if sess and args.get("actType") == 2:
                sess.stop_macro()
            return True

        # Built-in Quick Commands & Device Lifecycle
        if cmd == "adb_command":
            raw_cmd = (args.get("command") or "").strip()
            if not sess:
                return "Error: device offline"
            if "KEYCODE_VOLUME_UP" in raw_cmd:
                sess._enqueue_action(sess.press_button, "volumeUp")
                return "Volume Up OK"
            if "KEYCODE_VOLUME_DOWN" in raw_cmd:
                sess._enqueue_action(sess.press_button, "volumeDown")
                return "Volume Down OK"
            if "KEYCODE_HOME" in raw_cmd:
                sess._enqueue_action(sess.press_button, "home")
                return "Home OK"
            if "reboot" in raw_cmd:
                sess.reboot_device()
                return "Rebooting device..."
            if "screencap" in raw_cmd:
                out_dir = os.path.expanduser("~/Pictures/XiaoweiScreenshots")
                os.makedirs(out_dir, exist_ok=True)
                out_p = os.path.join(out_dir, f"shot_{int(time.time())}.png")
                sess.save_screenshot(out_p)
                return f"Saved screenshot to {out_p}"
            return f"Executed on iOS ({sess.name})"

        if cmd in ("reboot", "reboot_ext"):
            return sess.reboot_device() if sess else False
        if cmd == "switch_direction":
            if sess:
                direction = args.get("direction")
                try:
                    orient = "LANDSCAPE" if direction == "horizontal" else "PORTRAIT"
                    sess._wda_session_request("POST", "/orientation", {"orientation": orient})
                except Exception:
                    pass
            return True
        if cmd == "reconnect_device":
            if sess:
                sess._close_wda_connections()
                sess._has_fast_wda = None
                sess._settings_applied_sid = None
                sess.wda_session_id = None
                sess.wda_ready = False
            return True
        if cmd in ("disconnect", "close_device"):
            serials_str = args.get("serials") or serial
            for s_id in str(serials_str).split(","):
                s_id = s_id.strip()
                if not s_id:
                    continue
                with self.device_mgr.lock:
                    removed = self.device_mgr.sessions.pop(s_id, None)
                if removed:
                    removed.stop()
            return True

        # Benign UI / telemetry stubs
        if cmd in (
            "notify_core_client_ready",
            "enqueue_core_analytics_event",
            "client_event_reporting",
            "sync_client_stat",
            "track_phone_share_ui_event",
            "push_scan_ips",
            "open_api_ws_connect",
            "set_auto_mirror",
            "set_state",
            "wallpapers_device",
            "calibrate_mouse",
            "mouse_reset",
            "restart_adb",
        ):
            return True
        if cmd == "get_core_analytics_context":
            return {"os": "macos", "arch": "arm64", "version": "3.8.81"}

        return None


# ---------------------------------------------------------------------------
# Local HTTP + RPC Server
# ---------------------------------------------------------------------------

def main():
    rpc_port_file = sys.argv[1] if len(sys.argv) > 1 else ""
    web_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

    MIME_MAP = {
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".ico": "image/x-icon",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".otf": "font/otf",
        ".ttf": "font/ttf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }

    router_ref = [None]
    ws_hub = WebSocketHub(
        lambda txt: router_ref[0] and router_ref[0].device_mgr.handle_ws_message(txt),
        binary_handler=lambda b: router_ref[0] and router_ref[0].device_mgr.handle_ws_binary(b),
    )
    ws_port = ws_hub.start()

    sql_pool = SqlitePool()
    router = CommandRouter(ws_hub, None, sql_pool)
    device_mgr = DeviceManager(ws_hub, router.queue_event)
    router.device_mgr = device_mgr
    router_ref[0] = router
    device_mgr.start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path == "/health":
                with ws_hub.lock:
                    n_ws = len(ws_hub.clients)
                with device_mgr.lock:
                    devs = [
                        {
                            "serial": s.serial,
                            "name": s.name,
                            "model": s.model,
                            "os_version": s.os_version,
                            "wda_ready": s.wda_ready,
                            "wda_session": s.wda_session_id,
                            "size": f"{s.width}x{s.height}",
                            "has_frame": len(s.last_jpeg_b64) > 1000,
                        }
                        for s in device_mgr.sessions.values()
                    ]
                body = json.dumps({"ok": True, "ws_clients": n_ws, "usb_devices": len(devs), "devices": devs}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            parsed = urllib.parse.urlparse(self.path)
            rel = urllib.parse.unquote(parsed.path or "/").lstrip("/")
            if not rel:
                rel = "index.html"
            full = os.path.normpath(os.path.join(web_root, rel))
            if not full.startswith(os.path.normpath(web_root)) or not os.path.isfile(full):
                full = os.path.join(web_root, "index.html")
            if not os.path.isfile(full):
                self.send_response(404)
                self.end_headers()
                return
            ext = os.path.splitext(full)[1].lower()
            mime = MIME_MAP.get(ext, "application/octet-stream")
            data = open(full, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
                if self.path == "/events":
                    res = {"ok": True, "events": router.drain_events()}
                else:
                    cmd = req.get("cmd", "")
                    args = req.get("args", {})
                    data = router.dispatch(cmd, args)
                    res = {"ok": True, "result": data, "events": router.drain_events()}
                body = json.dumps(res, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                err = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)

    httpd = None
    for candidate_port in [19881, 19882, 19883, 0]:
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate_port), Handler)
            break
        except OSError:
            continue
    rpc_port = httpd.server_address[1]
    info = {"rpc_port": rpc_port, "ws_port": ws_port, "pid": os.getpid()}
    if rpc_port_file:
        with open(rpc_port_file, "w", encoding="utf-8") as f:
            json.dump(info, f)
    print(json.dumps(info), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
