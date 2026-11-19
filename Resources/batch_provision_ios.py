#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xiaowei iOS — Công cụ Cài đặt, Khôi phục sau Restore & Gia hạn WDA Hàng loạt (0đ)
Zero-dependency macOS batch provisioner for USB-connected iPhones (iOS 15, 16, 17, 18+):
  1. Tự động ghép đôi (Lockdown Pair) hoặc báo rõ máy nào cần chạm 1 lần "Tin cậy (Trust)".
  2. Tự động kiểm tra & kích hoạt hiện menu "Chế độ nhà phát triển (Developer Mode)" trên iOS 16+ qua AMFI Lockdown.
  3. Kiểm tra siêu tốc (<0.5s) WDA trên cổng 8100 mà KHÔNG làm gián đoạn phiên điều khiển đang chạy.
  4. Tự động cài đặt mới (sau khi Restore trắng bằng Apple Configurator) hoặc gia hạn 7 ngày (Apple ID miễn phí 0đ).
  5. Tự động đăng ký UDID máy iPhone mới tinh với Apple (0đ) qua xcodebuild -allowProvisioningUpdates,
     giữ nguyên vỏ Turbo WDA (MinimumOSVersion 15.0 + /wda/fastTap <5ms) tương thích mọi đời iOS 15–18+.
  6. Tạo file cấu hình Wi-Fi tự động (.mobileconfig chuẩn Apple) để gắn vào Apple Configurator Blueprints.
"""

import argparse
import base64
import concurrent.futures
import datetime
import http.client
import json
import os
import plistlib
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
import uuid
import warnings
import zipfile

warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
APP_SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/com.xiaowei.iphone")
CACHE_DIR = os.path.expanduser("~/Library/Caches/com.xiaowei.iphone")
os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Locate bundled site-packages (works from .app bundle, source tree, or standalone toolkit)
_SITE_CANDIDATES = [
    os.path.join(SCRIPT_DIR, "site-packages"),
    os.path.join(SCRIPT_DIR, "..", "Xiaowei iOS.app", "Contents", "Resources", "site-packages"),
    os.path.join(SCRIPT_DIR, "Xiaowei iOS.app", "Contents", "Resources", "site-packages"),
    os.path.join(PROJECT_ROOT, ".venv", "lib", "python3.9", "site-packages"),
    os.path.join(PROJECT_ROOT, ".venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
    "/Applications/Xiaowei iOS.app/Contents/Resources/site-packages",
    os.path.expanduser("~/Library/Application Support/com.xiaowei.iphone/site-packages"),
]
BUNDLED_SITE = None
for _cand in _SITE_CANDIDATES:
    if os.path.isdir(_cand):
        if _cand not in sys.path:
            sys.path.insert(0, _cand)
        if BUNDLED_SITE is None:
            BUNDLED_SITE = _cand

USBMUXD_SOCKET = "/var/run/usbmuxd"
DEFAULT_DEV_TEAM = os.environ.get("XIAOWEI_DEVELOPMENT_TEAM", "D494LPV2H6")
WDA_XCODEPROJ_CANDIDATES = [
    os.environ.get("XIAOWEI_WDA_XCODEPROJ", ""),
    os.path.join(PROJECT_ROOT, "WebDriverAgent", "WebDriverAgent.xcodeproj"),
    os.path.expanduser("~/WebDriverAgent/WebDriverAgent.xcodeproj"),
]
_XCODE_PROVISION_LOCK = threading.Lock()

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


# ---------------------------------------------------------------------------
# Zero-Dependency Pure-Python DER + /usr/bin/openssl Pairing Shim for tidevice
# (Eliminates need for pyOpenSSL / pyasn1 when pairing freshly restored iPhones)
# ---------------------------------------------------------------------------

def _der_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _der_tlv(tag, body):
    return bytes([tag]) + _der_len(len(body)) + body


def _der_seq(*items):
    return _der_tlv(0x30, b"".join(items))


def _der_set(*items):
    return _der_tlv(0x31, b"".join(items))


def _der_int(val):
    if val == 0:
        return _der_tlv(0x02, b"\x00")
    b = val.to_bytes((val.bit_length() + 8) // 8, "big", signed=False)
    if b[0] & 0x80:
        b = b"\x00" + b
    return _der_tlv(0x02, b)


def _der_oid(oid_bytes):
    return _der_tlv(0x06, oid_bytes)


def _der_utf8(text):
    return _der_tlv(0x0C, text.encode("utf-8"))


def _der_utctime(dt):
    return _der_tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode("ascii"))


def _der_bitstring(raw_bytes):
    return _der_tlv(0x03, b"\x00" + raw_bytes)


def _der_name_cn(cn_text):
    # OID 2.5.4.3 (commonName) = 55 04 03
    atv = _der_seq(_der_oid(b"\x55\x04\x03"), _der_utf8(cn_text))
    return _der_seq(_der_set(atv))


def _build_signed_x509_pem(spki_der, issuer_cn, subject_cn, root_key_path, serial_num=1, days=3650):
    # sha256WithRSAEncryption OID 1.2.840.113549.1.1.11 = 2a 86 48 86 f7 0d 01 01 0b + NULL
    alg_sha256_rsa = _der_seq(_der_oid(b"\x2a\x86\x48\x86\xf7\x0d\x01\x01\x0b"), b"\x05\x00")
    now = datetime.datetime.now(datetime.timezone.utc)
    validity = _der_seq(
        _der_utctime(now - datetime.timedelta(minutes=5)),
        _der_utctime(now + datetime.timedelta(days=days)),
    )
    tbs = _der_seq(
        _der_int(serial_num),
        alg_sha256_rsa,
        _der_name_cn(issuer_cn),
        validity,
        _der_name_cn(subject_cn),
        spki_der,
    )
    sig = subprocess.check_output(
        ["/usr/bin/openssl", "dgst", "-sha256", "-sign", root_key_path],
        input=tbs,
        stderr=subprocess.DEVNULL,
    )
    cert_der = _der_seq(tbs, alg_sha256_rsa, _der_bitstring(sig))
    b64 = base64.encodebytes(cert_der)
    return b"-----BEGIN CERTIFICATE-----\n" + b64 + b"-----END CERTIFICATE-----\n"


def _openssl_make_certs_and_key(device_public_key: bytes):
    with tempfile.TemporaryDirectory() as td:
        root_key_path = os.path.join(td, "root.key")
        dev_pub_path = os.path.join(td, "dev_pub.pem")
        with open(dev_pub_path, "wb") as f:
            f.write(device_public_key if isinstance(device_public_key, bytes) else device_public_key.encode("utf-8"))

        subprocess.check_call(
            ["/usr/bin/openssl", "genrsa", "-out", root_key_path, "2048"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(root_key_path, "rb") as f:
            priv_key_pem = f.read()

        root_spki_der = subprocess.check_output(
            ["/usr/bin/openssl", "rsa", "-in", root_key_path, "-pubout", "-outform", "DER"],
            stderr=subprocess.DEVNULL,
        )
        try:
            dev_spki_der = subprocess.check_output(
                ["/usr/bin/openssl", "rsa", "-RSAPublicKey_in", "-in", dev_pub_path, "-pubout", "-outform", "DER"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            dev_spki_der = subprocess.check_output(
                ["/usr/bin/openssl", "rsa", "-pubin", "-in", dev_pub_path, "-pubout", "-outform", "DER"],
                stderr=subprocess.DEVNULL,
            )

        host_cert_pem = _build_signed_x509_pem(root_spki_der, "XiaoweiHostCA", "XiaoweiHostCA", root_key_path, serial_num=1)
        dev_cert_pem = _build_signed_x509_pem(dev_spki_der, "XiaoweiHostCA", "Device", root_key_path, serial_num=2)
        return host_cert_pem, priv_key_pem, dev_cert_pem


def _install_tidevice_ca_shim():
    try:
        import tidevice._ca  # noqa: F401
    except Exception:
        shim = types.ModuleType("tidevice._ca")
        shim.make_certs_and_key = _openssl_make_certs_and_key
        sys.modules["tidevice._ca"] = shim


try:
    import tidevice
    _install_tidevice_ca_shim()
except Exception:
    tidevice = None


# ---------------------------------------------------------------------------
# Direct macOS usbmuxd helpers (sub-millisecond USB list + port 8100 probe)
# ---------------------------------------------------------------------------

class UsbmuxFast:
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
    def list_usb_devices(cls):
        if not os.path.exists(USBMUXD_SOCKET):
            return []
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.5)
        try:
            sock.connect(USBMUXD_SOCKET)
            cls._send_plist(
                sock,
                1,
                {
                    "MessageType": "ListDevices",
                    "ClientVersionString": "XiaoweiProvisioner",
                    "ProgName": "XiaoweiProvisioner",
                    "kLibUSBMuxVersion": 3,
                },
            )
            resp = cls._recv_plist(sock)
            out = []
            for entry in resp.get("DeviceList", []):
                props = entry.get("Properties", {})
                if props.get("ConnectionType", "USB") != "USB":
                    continue
                serial = props.get("SerialNumber", "")
                dev_id = entry.get("DeviceID", props.get("DeviceID"))
                if serial and dev_id is not None:
                    out.append({"udid": serial, "device_id": int(dev_id)})
            return out
        except Exception:
            return []
        finally:
            sock.close()

    @classmethod
    def check_wda_ready_fast(cls, device_id, timeout=0.42):
        """Non-intrusive GET /status over usbmuxd port 8100 (<0.5s, never resets active WDA session)."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(USBMUXD_SOCKET)
            cls._send_plist(
                sock,
                2,
                {
                    "MessageType": "Connect",
                    "ClientVersionString": "XiaoweiProvisioner",
                    "ProgName": "XiaoweiProvisioner",
                    "DeviceID": int(device_id),
                    "PortNumber": int(socket.htons(8100)),
                },
            )
            resp = cls._recv_plist(sock)
            if resp.get("Number", -1) != 0:
                return False
            conn = http.client.HTTPConnection("127.0.0.1", 8100, timeout=timeout)
            conn.sock = sock
            conn.request("GET", "/status", headers={"Connection": "close"})
            http_resp = conn.getresponse()
            raw = http_resp.read()
            if http_resp.status == 200:
                data = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
                return isinstance(data, dict)
            return False
        except Exception:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Apple Configuration Profile (.mobileconfig) Generator for Wi-Fi Auto-Join
# ---------------------------------------------------------------------------

def generate_wifi_mobileconfig(ssid: str, password: str = "", out_path: str = "", hidden: bool = False) -> str:
    ssid = (ssid or "").strip()
    if not ssid:
        raise ValueError("Tên mạng Wi-Fi (SSID) không được để trống.")

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ssid).strip("-").lower() or "default"
    wifi_uuid = str(uuid.uuid4()).upper()
    root_uuid = str(uuid.uuid4()).upper()

    wifi_payload = {
        "AutoJoin": True,
        "CaptiveBypass": False,
        "DisableAssociationMACRandomization": False,
        "EncryptionType": "Any" if password else "None",
        "HIDDEN_NETWORK": bool(hidden),
        "IsHotspot": False,
        "PayloadDescription": f"Tự động kết nối mạng Wi-Fi {ssid}",
        "PayloadDisplayName": f"Wi-Fi ({ssid})",
        "PayloadIdentifier": f"com.xiaowei.ios.wifi.managed.{slug}.{wifi_uuid[:8].lower()}",
        "PayloadType": "com.apple.wifi.managed",
        "PayloadUUID": wifi_uuid,
        "PayloadVersion": 1,
        "ProxyType": "None",
        "SSID_STR": ssid,
    }
    if password:
        wifi_payload["Password"] = password

    profile = {
        "PayloadContent": [wifi_payload],
        "PayloadDescription": (
            "Hồ sơ cấu hình giúp iPhone tự động bắt Wi-Fi ngay sau khi Restore trắng bằng Apple Configurator "
            "(không cần gõ mật khẩu tay trên từng máy)."
        ),
        "PayloadDisplayName": f"Wi-Fi Tự Động - {ssid}",
        "PayloadIdentifier": f"com.xiaowei.ios.wifi.profile.{slug}",
        "PayloadOrganization": "Xiaowei iOS Suite",
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": root_uuid,
        "PayloadVersion": 1,
    }

    if not out_path:
        out_path = os.path.join(os.getcwd(), "WiFi-Tu-Dong-iPhone.mobileconfig")
    out_path = os.path.abspath(os.path.expanduser(out_path))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        plistlib.dump(profile, f, fmt=plistlib.FMT_XML, sort_keys=True)
    return out_path


# ---------------------------------------------------------------------------
# WDA IPA Locator, Inspector & $0 Auto-UDID Registration / Re-signing
# ---------------------------------------------------------------------------

def resolve_wda_ipa_path() -> str:
    """Return the freshest available WebDriverAgentRunner.ipa path."""
    candidates = [
        os.path.join(APP_SUPPORT_DIR, "WebDriverAgentRunner.ipa"),
        os.path.join(SCRIPT_DIR, "WebDriverAgentRunner.ipa"),
        "/Applications/Xiaowei iOS.app/Contents/Resources/WebDriverAgentRunner.ipa",
        os.path.join(PROJECT_ROOT, "Resources", "WebDriverAgentRunner.ipa"),
    ]
    existing = [p for p in candidates if os.path.isfile(p)]
    if not existing:
        return os.path.join(SCRIPT_DIR, "WebDriverAgentRunner.ipa")
    # Pick the IPA with the latest embedded.mobileprovision ExpirationDate (or mtime fallback)
    best_path = existing[0]
    best_exp = datetime.datetime.min
    for p in existing:
        info = inspect_ipa_provisioning(p)
        exp = info.get("expiration") or datetime.datetime.fromtimestamp(os.path.getmtime(p))
        if exp >= best_exp:
            best_exp = exp
            best_path = p
    return best_path


def inspect_ipa_provisioning(ipa_path: str) -> dict:
    if not ipa_path or not os.path.isfile(ipa_path):
        return {}
    try:
        with zipfile.ZipFile(ipa_path, "r") as zf:
            mp_names = [n for n in zf.namelist() if n.endswith("embedded.mobileprovision")]
            info_names = [n for n in zf.namelist() if n.endswith(".app/Info.plist") and "/PlugIns/" not in n]
            bundle_id = ""
            if info_names:
                pl = plistlib.loads(zf.read(info_names[0]))
                bundle_id = pl.get("CFBundleIdentifier", "")
            if not mp_names:
                return {"bundle_id": bundle_id}
            mp_raw = zf.read(mp_names[0])
        with tempfile.NamedTemporaryFile(suffix=".mobileprovision", delete=False) as tf:
            tf.write(mp_raw)
            tmp_mp = tf.name
        try:
            dec = subprocess.check_output(
                ["/usr/bin/security", "cms", "-D", "-i", tmp_mp],
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            mp = plistlib.loads(dec)
            exp = mp.get("ExpirationDate")
            if isinstance(exp, datetime.datetime) and exp.tzinfo is not None:
                exp = exp.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return {
                "bundle_id": bundle_id,
                "devices": set(mp.get("ProvisionedDevices") or []),
                "expiration": exp,
                "team_id": (mp.get("TeamIdentifier") or [DEFAULT_DEV_TEAM])[0],
                "entitlements": mp.get("Entitlements") or {},
            }
        finally:
            try:
                os.remove(tmp_mp)
            except Exception:
                pass
    except Exception:
        return {}


def find_apple_dev_signing_identity() -> str:
    try:
        out = subprocess.check_output(
            ["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            m = re.search(r'"(Apple Development:[^"]+)"', line)
            if m:
                return m.group(1)
            m2 = re.search(r'"(iPhone Developer:[^"]+)"', line)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return ""


def find_wda_xcodeproj() -> str:
    for p in WDA_XCODEPROJ_CANDIDATES:
        if p and os.path.isdir(p):
            return p
    return ""


def rebuild_and_resign_ipa_for_udid(udid: str, base_ipa_path: str, log_fn=None) -> tuple:
    """
    Registers a brand-new iPhone UDID (or renews an expired 7-day free Apple ID profile) for $0 via
    `xcodebuild build-for-testing ... -allowProvisioningUpdates`, then injects the fresh `embedded.mobileprovision`
    into the existing iOS 15.0+ Turbo WDA shell (`WebDriverAgentRunner.ipa`) and deep re-signs it!
    Returns (success: bool, new_ipa_path_or_error: str).
    """
    with _XCODE_PROVISION_LOCK:
        # Re-check inside lock in case another parallel worker just provisioned a fresh profile containing this UDID!
        latest_ipa = resolve_wda_ipa_path()
        info = inspect_ipa_provisioning(latest_ipa)
        now_utc = datetime.datetime.utcnow()
        if (
            udid in (info.get("devices") or set())
            and info.get("expiration")
            and info["expiration"] > now_utc + datetime.timedelta(hours=2)
        ):
            return True, latest_ipa

        xcodeproj = find_wda_xcodeproj()
        if not xcodeproj or not os.path.exists("/usr/bin/xcodebuild"):
            return (
                False,
                "Không tìm thấy Xcode hoặc mã nguồn WebDriverAgent để tự động đăng ký UDID mới miễn phí.",
            )

        sign_id = find_apple_dev_signing_identity()
        if not sign_id:
            return (
                False,
                "Chưa đăng nhập Apple ID trong Xcode (Settings -> Accounts -> Manage Certificates -> Apple Development).",
            )

        team_id = info.get("team_id") or DEFAULT_DEV_TEAM
        if log_fn:
            log_fn(f"Đang tự động đăng ký UDID {udid[-6:]} & xin chứng chỉ 7 ngày miễn phí (0đ) từ Apple qua Xcode...")

        derived_dir = os.path.join(CACHE_DIR, "wda_autoprov_build")
        os.makedirs(derived_dir, exist_ok=True)
        cmd = [
            "/usr/bin/xcodebuild",
            "build-for-testing",
            "-project",
            xcodeproj,
            "-scheme",
            "WebDriverAgentRunner",
            "-destination",
            f"id={udid}",
            "-derivedDataPath",
            derived_dir,
            f"DEVELOPMENT_TEAM={team_id}",
            "-allowProvisioningUpdates",
            "-quiet",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        built_runner = os.path.join(derived_dir, "Build", "Products", "Debug-iphoneos", "WebDriverAgentRunner-Runner.app")
        built_mp = os.path.join(built_runner, "embedded.mobileprovision")
        if proc.returncode != 0 and not os.path.isfile(built_mp):
            out_tail = (proc.stdout or b"").decode("utf-8", errors="ignore")[-500:].strip()
            return False, f"Xcode đăng ký UDID thất bại: {out_tail or 'xcodebuild error'}"

        if not os.path.isfile(built_mp):
            return False, "Xcode không tạo được file embedded.mobileprovision mới."

        try:
            dec = subprocess.check_output(["/usr/bin/security", "cms", "-D", "-i", built_mp], stderr=subprocess.DEVNULL)
            mp_plist = plistlib.loads(dec)
            raw_ent = mp_plist.get("Entitlements") or {}
            app_id = raw_ent.get("application-identifier", f"{team_id}.com.bienvu.wda2026.runner.xctrunner")
            new_team = raw_ent.get("com.apple.developer.team-identifier", team_id)
            new_bundle_id = app_id.split(".", 1)[1] if "." in app_id else "com.bienvu.wda2026.runner.xctrunner"
            clean_entitlements = {
                "application-identifier": app_id,
                "com.apple.developer.team-identifier": new_team,
                "get-task-allow": bool(raw_ent.get("get-task-allow", True)),
                "keychain-access-groups": [app_id],
            }

            with tempfile.TemporaryDirectory() as work_td:
                payload_dir = os.path.join(work_td, "Payload")
                if base_ipa_path and os.path.isfile(base_ipa_path):
                    with zipfile.ZipFile(base_ipa_path, "r") as zf:
                        zf.extractall(work_td)
                else:
                    os.makedirs(payload_dir, exist_ok=True)
                    shutil.copytree(built_runner, os.path.join(payload_dir, "WebDriverAgentRunner-Runner.app"))

                target_app = os.path.join(payload_dir, "WebDriverAgentRunner-Runner.app")
                shutil.copy2(built_mp, os.path.join(target_app, "embedded.mobileprovision"))

                # Ensure Info.plist keeps MinimumOSVersion = 15.0 (compatible with iOS 15, 16, 17, 18+)
                # and matches the exact CFBundleIdentifier of the new embedded.mobileprovision!
                info_plist_path = os.path.join(target_app, "Info.plist")
                with open(info_plist_path, "rb") as f:
                    app_info = plistlib.load(f)
                app_info["CFBundleIdentifier"] = new_bundle_id
                app_info["MinimumOSVersion"] = "15.0"
                with open(info_plist_path, "wb") as f:
                    plistlib.dump(app_info, f)

                ent_path = os.path.join(work_td, "RunnerEntitlements.plist")
                with open(ent_path, "wb") as f:
                    plistlib.dump(clean_entitlements, f)

                # Re-sign inner frameworks & dylibs -> PlugIns/*.xctest -> outer Runner.app
                xctest_dir = os.path.join(target_app, "PlugIns", "WebDriverAgentRunner.xctest")
                fw_root = os.path.join(xctest_dir, "Frameworks")
                if os.path.isdir(fw_root):
                    for entry in sorted(os.listdir(fw_root)):
                        fp = os.path.join(fw_root, entry)
                        if entry.endswith(".framework") or entry.endswith(".dylib"):
                            subprocess.check_call(
                                ["/usr/bin/codesign", "--force", "--sign", sign_id, "--timestamp=none", fp],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                for extra_fw_dir in (os.path.join(target_app, "Frameworks"),):
                    if os.path.isdir(extra_fw_dir):
                        for entry in sorted(os.listdir(extra_fw_dir)):
                            fp = os.path.join(extra_fw_dir, entry)
                            if entry.endswith(".framework") or entry.endswith(".dylib"):
                                subprocess.check_call(
                                    ["/usr/bin/codesign", "--force", "--sign", sign_id, "--timestamp=none", fp],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                if os.path.isdir(xctest_dir):
                    subprocess.check_call(
                        ["/usr/bin/codesign", "--force", "--sign", sign_id, "--timestamp=none", xctest_dir],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                subprocess.check_call(
                    [
                        "/usr/bin/codesign",
                        "--force",
                        "--sign",
                        sign_id,
                        "--entitlements",
                        ent_path,
                        "--timestamp=none",
                        target_app,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                out_ipa = os.path.join(APP_SUPPORT_DIR, "WebDriverAgentRunner.ipa")
                tmp_zip = out_ipa + ".tmp"
                with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(payload_dir):
                        rel_root = os.path.relpath(root, work_td)
                        if not files and not dirs:
                            zf.writestr(rel_root.rstrip("/") + "/", b"")
                        for fn in files:
                            full_f = os.path.join(root, fn)
                            arc_f = os.path.join(rel_root, fn)
                            zf.write(full_f, arc_f)
                os.replace(tmp_zip, out_ipa)

                # Also update writable Resources/WebDriverAgentRunner.ipa locations so future builds pick it up
                for mirror_p in (
                    os.path.join(SCRIPT_DIR, "WebDriverAgentRunner.ipa"),
                    os.path.join(PROJECT_ROOT, "Resources", "WebDriverAgentRunner.ipa"),
                ):
                    if os.path.isdir(os.path.dirname(mirror_p)) and os.access(os.path.dirname(mirror_p), os.W_OK):
                        try:
                            if os.path.abspath(mirror_p) != os.path.abspath(out_ipa):
                                shutil.copy2(out_ipa, mirror_p)
                        except Exception:
                            pass

                return True, out_ipa
        except Exception as exc:
            return False, f"Lỗi đóng gói lại IPA sau khi ký: {exc}"


# ---------------------------------------------------------------------------
# Per-Device Provisioning Pipeline
# ---------------------------------------------------------------------------

def _is_xiaowei_backend_active() -> bool:
    for port in (19881, 19882, 19883):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.35)
            conn.request("GET", "/health")
            r = conn.getresponse()
            r.read()
            conn.close()
            if r.status == 200:
                return True
        except Exception:
            pass
    return False


def _discover_installed_wda_bundles(ti_dev) -> list:
    bundles = []
    if ti_dev is None:
        return bundles
    try:
        for app in ti_dev.installation.iter_installed(app_type="User"):
            bid = app.get("CFBundleIdentifier") or ""
            low = bid.lower()
            if "webdriveragent" in low or "xctrunner" in low or ".wda" in low:
                bundles.append(bid)
    except Exception:
        pass
    return bundles


def _start_wda_for_device(udid: str, device_id: int, major_ver: int, bundles: list, ti_dev=None) -> bool:
    """Starts WDA on the device and waits briefly for port 8100 to respond."""
    if UsbmuxFast.check_wda_ready_fast(device_id, timeout=0.35):
        return True

    target_bundles = list(bundles) if bundles else ["com.bienvu.wda2026.runner.xctrunner"]
    env = os.environ.copy()
    if BUNDLED_SITE:
        env["PYTHONPATH"] = BUNDLED_SITE + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    if major_ver <= 16:
        if ti_dev is not None:
            try:
                ti_dev.mount_developer_image()
            except Exception:
                pass
        # If Xiaowei backend isn't already managing xctest, spawn a clean detached tidevice xctest daemon
        if not _is_xiaowei_backend_active():
            try:
                subprocess.Popen(
                    ["/usr/bin/python3", "-m", "tidevice", "-u", udid, "xctest", "-B", target_bundles[0]],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass
    else:
        for bid in target_bundles:
            try:
                subprocess.run(
                    ["/usr/bin/xcrun", "devicectl", "device", "process", "launch", "--device", udid, bid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                )
                break
            except Exception:
                pass

    # Wait up to ~6.5s for WDA HTTP /status on port 8100
    deadline = time.time() + 6.5
    while time.time() < deadline:
        if UsbmuxFast.check_wda_ready_fast(device_id, timeout=0.45):
            return True
        time.sleep(0.45)
    return UsbmuxFast.check_wda_ready_fast(device_id, timeout=0.45)


def provision_single_device(usb_entry: dict, force: bool = False, renew: bool = False, quiet: bool = False) -> dict:
    udid = usb_entry["udid"]
    device_id = usb_entry["device_id"]
    t0 = time.perf_counter()

    result = {
        "udid": udid,
        "short_udid": udid[-6:],
        "name": f"iPhone ({udid[-4:]})",
        "model": "iPhone",
        "os_version": "",
        "status": "error",
        "ready": False,
        "action_taken": "none",
        "message_vi": "",
        "elapsed_ms": 0,
    }

    def log_step(msg):
        if not quiet:
            print(f"  [{udid[-6:]}] {msg}", flush=True)

    if tidevice is None:
        result["message_vi"] = "Thiếu thư viện tidevice trong bộ cài ứng dụng."
        result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        return result

    dev = tidevice.Device(udid)

    # Read basic Lockdown unauthenticated values first (works even before Trust!)
    try:
        raw_name = dev.get_value("DeviceName", no_session=True)
        raw_prod = dev.get_value("ProductType", no_session=True)
        raw_ver = dev.get_value("ProductVersion", no_session=True)
        model_name = IPHONE_MODELS.get(str(raw_prod or ""), str(raw_prod or "iPhone"))
        result["model"] = model_name
        result["name"] = str(raw_name or model_name)
        result["os_version"] = str(raw_ver or "16.0")
    except Exception:
        pass

    # Step 1: Ultra-fast non-intrusive check if WDA is ALREADY online on port 8100 (<0.5s!)
    # Doing this before anything heavy guarantees active Xiaowei sessions experience 0ms interruption!
    if not force and not renew and UsbmuxFast.check_wda_ready_fast(device_id, timeout=0.42):
        result["status"] = "ready"
        result["ready"] = True
        result["action_taken"] = "already_running"
        result["message_vi"] = "Đã sẵn sàng (Đang kết nối & điều khiển mượt)"
        result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        return result

    # Step 2: Validate Lockdown pairing / Auto-Pair newly restored or newly plugged-in iPhones
    paired_ok = False
    pair_err_str = ""
    try:
        # Attempt an authenticated Lockdown session read
        ver = dev.get_value("ProductVersion")
        if ver:
            result["os_version"] = str(ver)
            paired_ok = True
    except Exception as exc:
        pair_err_str = str(exc)

    if not paired_ok:
        log_step(f"Phát hiện máy mới / vừa Restore ({result['name']}) — đang gửi lệnh Ghép đôi (Pair)...")
        try:
            dev.pair()
            ver = dev.get_value("ProductVersion")
            if ver:
                result["os_version"] = str(ver)
                paired_ok = True
        except Exception as exc:
            pair_err_str = str(exc)
            # Also trigger CoreDevice pair dialog if available
            try:
                subprocess.run(
                    ["/usr/bin/xcrun", "devicectl", "manage", "pair", "--device", udid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=4,
                )
            except Exception:
                pass

    if not paired_ok:
        low_err = pair_err_str.lower()
        result["status"] = "needs_trust"
        result["action_taken"] = "prompted_trust"
        if "password" in low_err or "passcode" in low_err:
            result["message_vi"] = (
                "Cần mở khóa màn hình iPhone và bấm 'Tin cậy (Trust)' trên máy một lần "
                "(Mẹo: Dùng Apple Configurator Supervise khi Restore sẽ tự nhận Trust 100%)."
            )
        else:
            result["message_vi"] = (
                "Cần bấm 'Tin cậy (Trust)' trên màn hình iPhone rồi chạy lại 1 chạm "
                "(Hộp thoại Tin cậy vừa được bật sẵn trên máy)."
            )
        result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        return result

    # Refresh friendly name now that authenticated Lockdown session is active
    try:
        auth_name = dev.get_value("DeviceName")
        if auth_name:
            result["name"] = str(auth_name)
    except Exception:
        pass

    major_ver = 16
    try:
        major_ver = int(str(result["os_version"]).split(".")[0])
    except Exception:
        pass

    # Step 3: Check iOS 16+ Developer Mode status & auto-reveal toggle via AMFI action=0 if disabled
    if major_ver >= 16:
        dev_mode_on = False
        try:
            dev_mode_on = bool(dev.get_value("DeveloperModeStatus", domain="com.apple.security.mac.amfi"))
        except Exception:
            # Older point releases or locked state fallback
            dev_mode_on = True

        if not dev_mode_on:
            log_step("Chế độ Nhà phát triển đang tắt sau khi Restore — đang kích hoạt hiện menu trên iPhone...")
            try:
                dev._send_action_to_amfi_lockdown(0)
            except Exception:
                pass
            result["status"] = "needs_dev_mode"
            result["action_taken"] = "revealed_dev_mode"
            result["message_vi"] = (
                "Đã bật hiện mục 'Chế độ nhà phát triển' trên iPhone! "
                "Hãy mở Cài đặt -> Quyền riêng tư & Bảo mật -> Chế độ nhà phát triển -> Gạt Bật & Khởi động lại máy."
            )
            result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            return result

    # Step 4: Check installed WDA bundles
    bundles = _discover_installed_wda_bundles(dev)
    ipa_path = resolve_wda_ipa_path()
    ipa_info = inspect_ipa_provisioning(ipa_path)
    now_utc = datetime.datetime.utcnow()
    ipa_expired = bool(ipa_info.get("expiration") and ipa_info["expiration"] <= now_utc)
    udid_missing_in_ipa = bool(ipa_info.get("devices") and udid not in ipa_info["devices"])

    need_install = bool(force or renew or not bundles)

    # If WDA is installed and user didn't ask for --force/--renew, try launching existing WDA first!
    if not need_install and bundles:
        log_step(f"WDA đã có sẵn ({bundles[0]}), đang khởi động nhanh...")
        if _start_wda_for_device(udid, device_id, major_ver, bundles, ti_dev=dev):
            result["status"] = "ready"
            result["ready"] = True
            result["action_taken"] = "launched_existing"
            result["message_vi"] = "Đã khởi động WDA thành công & sẵn sàng điều khiển"
            result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            return result
        # Existing WDA failed to start (e.g. 7-day signature expired!) -> fall through to auto-reinstall/renew!
        log_step("WDA cũ không phản hồi (có thể hết hạn 7 ngày) — chuyển sang cài mới / gia hạn tự động...")
        need_install = True

    # Step 5: Install WDA IPA (with smart $0 Xcode UDID auto-registration & 7-day renewal fallback)
    if need_install:
        if not os.path.isfile(ipa_path) or ipa_expired or udid_missing_in_ipa:
            ok_rebuild, ipa_or_err = rebuild_and_resign_ipa_for_udid(udid, ipa_path, log_fn=log_step)
            if ok_rebuild:
                ipa_path = ipa_or_err
            elif not os.path.isfile(ipa_path):
                result["status"] = "error"
                result["message_vi"] = ipa_or_err
                result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
                return result

        log_step(f"Đang cài đặt Turbo WDA lên {result['name']} ({result['model']} - iOS {result['os_version']})...")
        install_ok = False
        install_err = ""
        try:
            dev.app_install(ipa_path)
            install_ok = True
        except Exception as exc:
            install_err = str(exc)

        # Smart fallback: if tidevice install failed due to provisioning/UDID/expired cert, auto-provision via Xcode!
        if not install_ok:
            low_ie = install_err.lower()
            prov_keywords = (
                "applicationverificationfailed",
                "0xe8008015",
                "0xe8008016",
                "0xe800801c",
                "0xe8008017",
                "provisioning",
                "profile",
                "expired",
                "signature",
                "verification",
            )
            if any(k in low_ie for k in prov_keywords):
                log_step("Máy chưa có trong hồ sơ chứng chỉ hoặc chứng chỉ 7 ngày đã hết hạn — đang tự động xin cấp mới (0đ)...")
                ok_rebuild, ipa_or_err = rebuild_and_resign_ipa_for_udid(udid, ipa_path, log_fn=log_step)
                if ok_rebuild:
                    ipa_path = ipa_or_err
                    try:
                        dev.app_install(ipa_path)
                        install_ok = True
                        install_err = ""
                    except Exception as exc2:
                        install_err = str(exc2)
                else:
                    install_err = f"{install_err} | {ipa_or_err}"

        if not install_ok:
            result["status"] = "error"
            result["action_taken"] = "install_failed"
            if "trust" in install_err.lower() or "untrusted" in install_err.lower():
                result["message_vi"] = (
                    "Đã cài nhưng cần mở Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị -> Tin cậy chứng chỉ Apple Development (1 lần)."
                )
            else:
                result["message_vi"] = f"Cài WDA chưa thành công: {install_err}"
            result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            return result

        bundles = _discover_installed_wda_bundles(dev) or ["com.bienvu.wda2026.runner.xctrunner"]

    # Step 6: Start WDA and confirm readiness
    wda_up = _start_wda_for_device(udid, device_id, major_ver, bundles, ti_dev=dev)
    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    if wda_up:
        result["status"] = "ready"
        result["ready"] = True
        result["action_taken"] = "renewed_and_started" if renew else "installed_and_started"
        result["message_vi"] = (
            "Đã gia hạn 7 ngày & kết nối sẵn sàng!"
            if renew
            else "Đã cài đặt Turbo WDA & kết nối sẵn sàng!"
        )
    else:
        # Installed cleanly; if free Apple ID was used on a freshly restored phone, remind 1-time Developer App Trust if needed
        result["status"] = "installed_pending_launch"
        result["ready"] = False
        result["action_taken"] = "installed"
        result["message_vi"] = (
            "Đã cài xong WDA lên máy! Nếu là máy vừa Restore lần đầu dùng Apple ID miễn phí: "
            "vào Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị -> bấm 'Tin cậy (Trust)' nhà phát triển (cần Wi-Fi), "
            "Xiaowei iOS sẽ tự lên hình ngay!"
        )
    return result


def run_batch_provision(force: bool = False, renew: bool = False, quiet: bool = False) -> dict:
    t_start = time.perf_counter()
    usb_devices = UsbmuxFast.list_usb_devices()
    if not usb_devices:
        return {
            "ok": True,
            "total": 0,
            "ready_count": 0,
            "action_needed_count": 0,
            "error_count": 0,
            "elapsed_ms": int((time.perf_counter() - t_start) * 1000),
            "summary_vi": "Chưa phát hiện iPhone nào cắm cáp USB vào máy Mac. Hãy kiểm tra dây cáp và thử lại.",
            "devices": [],
        }

    if not quiet:
        mode_label = "BẮT BUỘC CÀI MỚI / GIA HẠN 7 NGÀY" if (renew or force) else "TỰ ĐỘNG KIỂM TRA, CÀI ĐẶT & KHÔI PHỤC"
        print(f"=== XIAOWEI iOS — {mode_label} ({len(usb_devices)} máy USB) ===", flush=True)

    results = []
    max_workers = min(8, max(1, len(usb_devices)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {
            pool.submit(provision_single_device, entry, force=force, renew=renew, quiet=quiet): idx
            for idx, entry in enumerate(usb_devices)
        }
        ordered = [None] * len(usb_devices)
        for fut in concurrent.futures.as_completed(fut_map):
            idx = fut_map[fut]
            try:
                ordered[idx] = fut.result()
            except Exception as exc:
                u = usb_devices[idx]["udid"]
                ordered[idx] = {
                    "udid": u,
                    "short_udid": u[-6:],
                    "name": f"iPhone ({u[-4:]})",
                    "model": "iPhone",
                    "os_version": "",
                    "status": "error",
                    "ready": False,
                    "action_taken": "exception",
                    "message_vi": f"Lỗi ngoài dự kiến: {exc}",
                    "elapsed_ms": 0,
                }
        results = [r for r in ordered if r is not None]

    ready_count = sum(1 for r in results if r.get("ready"))
    action_needed_count = sum(
        1 for r in results if r.get("status") in ("needs_trust", "needs_dev_mode", "installed_pending_launch")
    )
    error_count = sum(1 for r in results if r.get("status") == "error")
    total_ms = int((time.perf_counter() - t_start) * 1000)

    summary_vi = (
        f"Tổng cộng {len(results)} máy iPhone: "
        f"{ready_count} sẵn sàng điều khiển, "
        f"{action_needed_count} cần 1 thao tác xác nhận trên màn hình iPhone, "
        f"{error_count} lỗi."
    )

    if not quiet:
        print("\n--- KẾT QUẢ CHI TIẾT TỪNG MÁY ---", flush=True)
        for i, r in enumerate(results, 1):
            icon = "✅" if r.get("ready") else ("👉" if r.get("status") != "error" else "❌")
            ver_txt = f" (iOS {r['os_version']})" if r.get("os_version") else ""
            print(
                f"{i}. {icon} {r['name']} — {r['model']}{ver_txt} [{r['short_udid']}]: {r['message_vi']} ({r['elapsed_ms']}ms)",
                flush=True,
            )
        print(f"\n=> {summary_vi} (Hoàn tất trong {total_ms / 1000.0:.2f}s)", flush=True)

    return {
        "ok": error_count == 0,
        "total": len(results),
        "ready_count": ready_count,
        "action_needed_count": action_needed_count,
        "error_count": error_count,
        "elapsed_ms": total_ms,
        "summary_vi": summary_vi,
        "devices": results,
    }


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Công cụ cài đặt & gia hạn WDA hàng loạt + tạo cấu hình Wi-Fi tự động cho Apple Configurator (0đ)"
    )
    parser.add_argument("--auto", action="store_true", help="Quét và cài đặt / khôi phục tự động tất cả iPhone cắm USB")
    parser.add_argument("--renew", action="store_true", help="Bắt buộc cài mới / gia hạn chứng chỉ 7 ngày cho tất cả iPhone")
    parser.add_argument("--force", action="store_true", help="Bắt buộc cài đặt lại WDA ngay cả khi đang chạy")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON chuẩn")
    parser.add_argument("--gen-wifi-profile", action="store_true", help="Tạo file cấu hình Wi-Fi (.mobileconfig) cho Apple Configurator")
    parser.add_argument("--ssid", type=str, default="", help="Tên mạng Wi-Fi (SSID)")
    parser.add_argument("--password", type=str, default="", help="Mật khẩu Wi-Fi (bỏ trống nếu mạng mở)")
    parser.add_argument("--hidden", action="store_true", help="Mạng Wi-Fi ẩn SSID")
    parser.add_argument("--out", type=str, default="", help="Đường dẫn xuất file .mobileconfig")

    args = parser.parse_args()

    if args.gen_wifi_profile:
        try:
            saved_path = generate_wifi_mobileconfig(
                ssid=args.ssid,
                password=args.password,
                out_path=args.out,
                hidden=args.hidden,
            )
            if args.json:
                print(json.dumps({"ok": True, "path": saved_path, "ssid": args.ssid}, ensure_ascii=False))
            else:
                print(f"✅ Đã tạo file cấu hình Wi-Fi tự động thành công:\n   {saved_path}")
            return 0
        except Exception as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            else:
                print(f"❌ Lỗi tạo cấu hình Wi-Fi: {exc}", file=sys.stderr)
            return 1

    # Default action is --auto
    report = run_batch_provision(force=args.force, renew=args.renew, quiet=args.json)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("error_count", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
