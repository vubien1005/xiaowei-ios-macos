import Cocoa
import WebKit
import UniformTypeIdentifiers

// MARK: - Custom URL Scheme Handler (tauri://localhost/...)

final class TauriSchemeHandler: NSObject, WKURLSchemeHandler {
    private let webRoot: URL

    init(webRoot: URL) {
        self.webRoot = webRoot
        super.init()
    }

    private func mimeType(for ext: String) -> String {
        switch ext.lowercased() {
        case "html", "htm": return "text/html; charset=utf-8"
        case "js", "mjs": return "application/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "ico": return "image/x-icon"
        case "wav": return "audio/wav"
        case "mp3": return "audio/mpeg"
        case "otf": return "font/otf"
        case "ttf": return "font/ttf"
        case "woff": return "font/woff"
        case "woff2": return "font/woff2"
        default: return "application/octet-stream"
        }
    }

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let reqURL = urlSchemeTask.request.url else {
            urlSchemeTask.didFailWithError(URLError(.badURL))
            return
        }

        var relPath = reqURL.path
        if relPath.isEmpty || relPath == "/" {
            relPath = "/index.html"
        }
        let cleanRel = String(relPath.drop(while: { $0 == "/" }))
        var fileURL = webRoot.appendingPathComponent(cleanRel)

        if !FileManager.default.fileExists(atPath: fileURL.path) {
            fileURL = webRoot.appendingPathComponent("index.html")
        }

        do {
            let data = try Data(contentsOf: fileURL)
            let mime = mimeType(for: fileURL.pathExtension)
            let headers: [String: String] = [
                "Content-Type": mime,
                "Content-Length": "\(data.count)",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache"
            ]
            if let response = HTTPURLResponse(
                url: reqURL,
                statusCode: 200,
                httpVersion: "HTTP/1.1",
                headerFields: headers
            ) {
                urlSchemeTask.didReceive(response)
                urlSchemeTask.didReceive(data)
                urlSchemeTask.didFinish()
            } else {
                urlSchemeTask.didFailWithError(URLError(.cannotParseResponse))
            }
        } catch {
            urlSchemeTask.didFailWithError(error)
        }
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}
}

// MARK: - Tauri 2 IPC Bridge + Native macOS Window/FS/Clipboard/Dialog Integration

final class TauriBridge: NSObject, WKScriptMessageHandlerWithReply {
    weak var window: NSWindow?
    weak var webView: WKWebView?
    var rpcPort: Int = 0
    private var fileHandles: [Int: FileHandle] = [:]
    private var nextRid: Int = 100

    private let appSupportDir: URL = {
        let p = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("com.xiaowei.iphone")
        try? FileManager.default.createDirectory(at: p, withIntermediateDirectories: true)
        return p
    }()

    private let appCacheDir: URL = {
        let p = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            .appendingPathComponent("com.xiaowei.iphone")
        try? FileManager.default.createDirectory(at: p, withIntermediateDirectories: true)
        return p
    }()

    func resolveBaseDirectory(_ code: Int) -> URL {
        let fm = FileManager.default
        switch code {
        case 1: return fm.urls(for: .musicDirectory, in: .userDomainMask).first!
        case 2, 16: return appCacheDir
        case 3, 4, 5, 13, 14, 15: return appSupportDir
        case 6: return fm.urls(for: .documentDirectory, in: .userDomainMask).first!
        case 7: return fm.urls(for: .downloadsDirectory, in: .userDomainMask).first!
        case 8: return fm.urls(for: .picturesDirectory, in: .userDomainMask).first!
        case 11: return Bundle.main.resourceURL ?? appSupportDir
        case 12: return URL(fileURLWithPath: NSTemporaryDirectory())
        case 17:
            let p = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/com.xiaowei.iphone")
            try? fm.createDirectory(at: p, withIntermediateDirectories: true)
            return p
        case 18: return fm.urls(for: .desktopDirectory, in: .userDomainMask).first!
        case 21: return fm.homeDirectoryForCurrentUser
        default: return appSupportDir
        }
    }

    private func resolveFSPath(_ rawPath: String, options: [String: Any]?) -> URL {
        let decoded = (rawPath.removingPercentEncoding ?? rawPath).replacingOccurrences(of: "\\", with: "/")
        if decoded.hasPrefix("file://"), let u = URL(string: decoded) {
            return u
        }
        if decoded.hasPrefix("/") {
            return URL(fileURLWithPath: decoded)
        }
        if let baseDir = options?["baseDir"] as? Int {
            return resolveBaseDirectory(baseDir).appendingPathComponent(decoded)
        }
        return appSupportDir.appendingPathComponent(decoded)
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage,
        replyHandler: @escaping (Any?, String?) -> Void
    ) {
        guard let body = message.body as? [String: Any],
              let cmd = body["cmd"] as? String else {
            replyHandler(NSNull(), nil)
            return
        }
        let args = body["args"] as? [String: Any] ?? [:]
        let rawBytes = body["rawBytes"] as? [Int]
        let options = body["options"] as? [String: Any]

        // Handle UI / macOS-native commands on MainActor
        switch cmd {
        case "plugin:app|version":
            replyHandler("3.8.81", nil)
            return

        // Event plugin (managed in JS + backend event pump)
        case "plugin:event|listen":
            let handlerId = args["handler"] as? Int ?? Int.random(in: 1...999_999)
            replyHandler(handlerId, nil)
            return
        case "plugin:event|unlisten", "plugin:event|emit", "plugin:event|emit_to":
            replyHandler(NSNull(), nil)
            return

        // Global shortcut stub (safe no-op)
        case "plugin:global-shortcut|register":
            replyHandler(NSNull(), nil)
            return

        // Path plugin
        case "plugin:path|resolve_directory":
            let dirCode = args["directory"] as? Int ?? 14
            replyHandler(resolveBaseDirectory(dirCode).path, nil)
            return
        case "plugin:path|join", "plugin:path|resolve":
            let parts = args["paths"] as? [String] ?? []
            var acc = ""
            for rawPart in parts where !rawPart.isEmpty {
                let p = rawPart.replacingOccurrences(of: "\\", with: "/")
                if p.hasPrefix("/") {
                    acc = p
                } else if acc.isEmpty {
                    acc = p
                } else {
                    acc = (acc as NSString).appendingPathComponent(p)
                }
            }
            replyHandler(acc, nil)
            return

        // Clipboard
        case "get_clipboard", "plugin:clipboard-manager|read_text":
            let txt = NSPasteboard.general.string(forType: .string) ?? ""
            replyHandler(txt, nil)
            return
        case "put_clipboard":
            let txt = args["body"] as? String ?? ""
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(txt, forType: .string)
            replyHandler(true, nil)
            return

        // Shell open
        case "plugin:shell|open":
            if let rawPath = args["path"] as? String {
                let pathStr = rawPath.replacingOccurrences(of: "\\", with: "/")
                if (pathStr.hasPrefix("http://") || pathStr.hasPrefix("https://") || pathStr.hasPrefix("mailto:")),
                   let url = URL(string: pathStr) {
                    NSWorkspace.shared.open(url)
                } else {
                    NSWorkspace.shared.open(URL(fileURLWithPath: pathStr))
                }
            }
            replyHandler(NSNull(), nil)
            return

        // Native File Open Dialog
        case "plugin:dialog|open":
            let panel = NSOpenPanel()
            let opts = args["options"] as? [String: Any] ?? args
            panel.canChooseDirectories = (opts["directory"] as? Bool) ?? false
            panel.canChooseFiles = !panel.canChooseDirectories
            panel.allowsMultipleSelection = (opts["multiple"] as? Bool) ?? false
            if let title = opts["title"] as? String {
                panel.title = title
            }
            let res = panel.runModal()
            if res == .OK {
                if panel.allowsMultipleSelection {
                    replyHandler(panel.urls.map { $0.path }, nil)
                } else {
                    replyHandler(panel.url?.path ?? NSNull(), nil)
                }
            } else {
                replyHandler(NSNull(), nil)
            }
            return

        case "plugin:dialog|message":
            let alert = NSAlert()
            alert.messageText = (args["title"] as? String) ?? "Xiaowei iOS"
            alert.informativeText = (args["message"] as? String) ?? ""
            let buttons = (args["buttons"] as? String) ?? "Ok"
            alert.addButton(withTitle: "Đồng ý")
            if buttons == "OkCancel" {
                alert.addButton(withTitle: "Hủy")
            }
            let r = alert.runModal()
            replyHandler(r == .alertFirstButtonReturn ? "Ok" : "Cancel", nil)
            return

        // FileSystem plugin
        case "plugin:fs|exists":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            replyHandler(FileManager.default.fileExists(atPath: p.path), nil)
            return
        case "plugin:fs|mkdir":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            try? FileManager.default.createDirectory(at: p, withIntermediateDirectories: true)
            replyHandler(NSNull(), nil)
            return
        case "plugin:fs|read_dir":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            let items = (try? FileManager.default.contentsOfDirectory(atPath: p.path)) ?? []
            let entries: [[String: Any]] = items.map { name in
                var isDir: ObjCBool = false
                let full = p.appendingPathComponent(name).path
                FileManager.default.fileExists(atPath: full, isDirectory: &isDir)
                return [
                    "name": name,
                    "isDirectory": isDir.boolValue,
                    "isFile": !isDir.boolValue,
                    "isSymlink": false
                ]
            }
            replyHandler(entries, nil)
            return
        case "plugin:fs|read_text_file":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            let data = (try? Data(contentsOf: p)) ?? Data()
            replyHandler(Array(data), nil)
            return
        case "plugin:fs|write_text_file":
            let headers = options?["headers"] as? [String: Any]
            let rawP = (headers?["path"] as? String) ?? (args["path"] as? String) ?? ""
            var parsedOpts: [String: Any]? = nil
            if let optStr = headers?["options"] as? String,
               let optData = optStr.data(using: .utf8) {
                parsedOpts = (try? JSONSerialization.jsonObject(with: optData)) as? [String: Any]
            }
            let p = resolveFSPath(rawP, options: parsedOpts)
            try? FileManager.default.createDirectory(at: p.deletingLastPathComponent(), withIntermediateDirectories: true)
            if let bytes = rawBytes {
                let data = Data(bytes.map { UInt8(truncatingIfNeeded: $0) })
                try? data.write(to: p)
            } else if let s = args["contents"] as? String {
                try? s.data(using: .utf8)?.write(to: p)
            }
            replyHandler(NSNull(), nil)
            return
        case "plugin:fs|remove":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            try? FileManager.default.removeItem(at: p)
            replyHandler(NSNull(), nil)
            return
        case "plugin:fs|create":
            let p = resolveFSPath(args["path"] as? String ?? "", options: args["options"] as? [String: Any])
            try? FileManager.default.createDirectory(at: p.deletingLastPathComponent(), withIntermediateDirectories: true)
            FileManager.default.createFile(atPath: p.path, contents: Data())
            if let fh = try? FileHandle(forUpdating: p) {
                nextRid += 1
                fileHandles[nextRid] = fh
                replyHandler(nextRid, nil)
            } else {
                replyHandler(0, nil)
            }
            return
        case "plugin:fs|write":
            if let rid = args["rid"] as? Int, let fh = fileHandles[rid] {
                if let arr = args["data"] as? [Int] {
                    let d = Data(arr.map { UInt8(truncatingIfNeeded: $0) })
                    try? fh.write(contentsOf: d)
                    replyHandler(d.count, nil)
                    return
                }
            }
            replyHandler(0, nil)
            return
        case "plugin:resources|close":
            if let rid = args["rid"] as? Int, let fh = fileHandles.removeValue(forKey: rid) {
                try? fh.close()
            }
            replyHandler(NSNull(), nil)
            return

        // Window plugin
        case _ where cmd.hasPrefix("plugin:window|") || cmd.hasPrefix("plugin:webview|"):
            handleWindowCommand(cmd, args: args, replyHandler: replyHandler)
            return

        default:
            break
        }

        // Forward backend commands asynchronously to Python iOS/SQLite/WS daemon
        forwardToBackend(cmd: cmd, args: args, replyHandler: replyHandler)
    }

    private func handleWindowCommand(
        _ cmd: String,
        args: [String: Any],
        replyHandler: @escaping (Any?, String?) -> Void
    ) {
        guard let win = window else {
            replyHandler(NSNull(), nil)
            return
        }
        let scale = win.backingScaleFactor
        switch cmd {
        case "plugin:window|get_all_windows":
            replyHandler(["main"], nil)
        case "plugin:webview|get_all_webviews":
            replyHandler([["label": "main", "windowLabel": "main"]], nil)
        case "plugin:window|scale_factor":
            replyHandler(scale, nil)
        case "plugin:window|inner_size", "plugin:window|outer_size", "plugin:webview|webview_size":
            let f = win.frame
            replyHandler(["width": Int(f.width * scale), "height": Int(f.height * scale)], nil)
        case "plugin:window|inner_position", "plugin:window|outer_position", "plugin:webview|webview_position":
            let f = win.frame
            replyHandler(["x": Int(f.origin.x * scale), "y": Int(f.origin.y * scale)], nil)
        case "plugin:window|is_fullscreen":
            replyHandler(win.styleMask.contains(.fullScreen), nil)
        case "plugin:window|is_minimized":
            replyHandler(win.isMiniaturized, nil)
        case "plugin:window|is_maximized":
            replyHandler(win.isZoomed, nil)
        case "plugin:window|is_focused":
            replyHandler(win.isKeyWindow, nil)
        case "plugin:window|is_decorated":
            replyHandler(false, nil)
        case "plugin:window|is_resizable", "plugin:window|is_maximizable",
             "plugin:window|is_minimizable", "plugin:window|is_closable",
             "plugin:window|is_visible", "plugin:window|is_enabled":
            replyHandler(true, nil)
        case "plugin:window|is_always_on_top":
            replyHandler(win.level == .floating, nil)
        case "plugin:window|set_always_on_top":
            let onTop = (args["value"] as? Bool) ?? false
            win.level = onTop ? .floating : .normal
            replyHandler(NSNull(), nil)
        case "plugin:window|title":
            replyHandler(win.title, nil)
        case "plugin:window|set_title":
            if let t = args["value"] as? String {
                win.title = t
            }
            replyHandler(NSNull(), nil)
        case "plugin:window|theme":
            let isDark = NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            replyHandler(isDark ? "dark" : "light", nil)
        case "plugin:window|minimize":
            win.miniaturize(nil)
            replyHandler(NSNull(), nil)
        case "plugin:window|unminimize":
            win.deminiaturize(nil)
            replyHandler(NSNull(), nil)
        case "plugin:window|maximize", "plugin:window|toggle_maximize", "plugin:window|unmaximize":
            win.zoom(nil)
            replyHandler(NSNull(), nil)
        case "plugin:window|set_fullscreen":
            let wantFS = (args["value"] as? Bool) ?? false
            if wantFS != win.styleMask.contains(.fullScreen) {
                win.toggleFullScreen(nil)
            }
            replyHandler(NSNull(), nil)
        case "plugin:window|center":
            win.center()
            replyHandler(NSNull(), nil)
        case "plugin:window|close", "plugin:window|destroy":
            NSApp.terminate(nil)
            replyHandler(NSNull(), nil)
        case "plugin:window|hide":
            win.orderOut(nil)
            replyHandler(NSNull(), nil)
        case "plugin:window|show", "plugin:window|set_focus":
            win.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            replyHandler(NSNull(), nil)
        case "plugin:window|start_dragging":
            if let currentEvent = NSApp.currentEvent {
                win.performDrag(with: currentEvent)
            }
            replyHandler(NSNull(), nil)
        case "plugin:window|set_size":
            if let sizeObj = args["value"] as? [String: Any] {
                let phys = (sizeObj["Physical"] as? [String: Any]) ?? (sizeObj["Logical"] as? [String: Any]) ?? sizeObj
                let isPhys = sizeObj["Physical"] != nil
                if let w = phys["width"] as? Double, let h = phys["height"] as? Double {
                    let div = isPhys ? scale : 1.0
                    var f = win.frame
                    f.size = NSSize(width: max(800, w / div), height: max(560, h / div))
                    win.setFrame(f, display: true, animate: true)
                }
            }
            replyHandler(NSNull(), nil)
        default:
            replyHandler(NSNull(), nil)
        }
    }

    private func forwardToBackend(
        cmd: String,
        args: [String: Any],
        replyHandler: @escaping (Any?, String?) -> Void
    ) {
        guard rpcPort > 0, let url = URL(string: "http://127.0.0.1:\(rpcPort)/rpc") else {
            replyHandler(NSNull(), nil)
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 15
        let payload: [String: Any] = ["cmd": cmd, "args": args]
        req.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        URLSession.shared.dataTask(with: req) { [weak self] data, _, err in
            DispatchQueue.main.async {
                if let err = err {
                    replyHandler(nil, err.localizedDescription)
                    return
                }
                guard let data = data,
                      let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
                    replyHandler(NSNull(), nil)
                    return
                }
                if let events = obj["events"] as? [[String: Any]], !events.isEmpty {
                    self?.deliverEvents(events)
                }
                if (obj["ok"] as? Bool) == true {
                    replyHandler(obj["result"] ?? NSNull(), nil)
                } else {
                    replyHandler(nil, (obj["error"] as? String) ?? "RPC error")
                }
            }
        }.resume()
    }

    func pollBackendEvents() {
        guard rpcPort > 0, let url = URL(string: "http://127.0.0.1:\(rpcPort)/events") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.httpBody = Data("{}".utf8)
        req.timeoutInterval = 3
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            guard let data = data,
                  let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                  let events = obj["events"] as? [[String: Any]],
                  !events.isEmpty else { return }
            DispatchQueue.main.async {
                self?.deliverEvents(events)
            }
        }.resume()
    }

    func deliverEvents(_ events: [[String: Any]]) {
        guard let wv = webView else { return }
        for ev in events {
            guard let name = ev["event"] as? String else { continue }
            let payload = ev["payload"] ?? NSNull()
            if let jsonData = try? JSONSerialization.data(withJSONObject: ["event": name, "payload": payload]),
               let jsonStr = String(data: jsonData, encoding: .utf8) {
                wv.evaluateJavaScript("window.__XIAOWEI_DISPATCH_EVENT__ && window.__XIAOWEI_DISPATCH_EVENT__(\(jsonStr));", completionHandler: nil)
            }
        }
    }
}

// MARK: - First-Mouse WKWebView (accepts immediate 1-click & Trackpad tap even when window was unfocused)

final class FirstMouseWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        return true
    }
}

// MARK: - AppDelegate & Main Window

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    private var window: NSWindow!
    private var webView: FirstMouseWebView!
    private let bridge = TauriBridge()
    private var backendProcess: Process?
    private var eventTimer: Timer?
    private var isProvisioningInFlight = false
    private var progressPanel: NSPanel?

    private static let tauriShimJS = #"""
    (function() {
      if (window.__TAURI_SHIM_INSTALLED__) return;
      window.__TAURI_SHIM_INSTALLED__ = true;

      // Desktop macOS WKWebView does not define window.TouchEvent globally (unlike Chromium WebView2);
      // polyfill it so `e instanceof TouchEvent` in TouchControl.mouseup (<300ms quick click) never throws ReferenceError!
      if (typeof window.TouchEvent === 'undefined') {
        window.TouchEvent = class TouchEvent extends UIEvent {};
      }

      const callbacks = new Map();
      const eventListeners = new Map();
      let nextCbId = 1;

      function transformCallback(cb, once = false) {
        const id = nextCbId++;
        callbacks.set(id, { cb, once });
        return id;
      }

      function unregisterCallback(id) {
        callbacks.delete(id);
      }

      function runCallback(id, data) {
        const entry = callbacks.get(id);
        if (!entry) return;
        if (entry.once) callbacks.delete(id);
        try { entry.cb(data); } catch (err) { console.error(err); }
      }

      window.__XIAOWEI_DISPATCH_EVENT__ = function(msg) {
        const list = eventListeners.get(msg.event);
        if (!list) return;
        for (const handlerId of Array.from(list)) {
          runCallback(handlerId, { event: msg.event, id: handlerId, payload: msg.payload });
        }
      };

      async function invoke(cmd, args = {}, options = undefined) {
        if (cmd === 'plugin:event|listen') {
          const evName = args.event;
          const handlerId = args.handler;
          if (!eventListeners.has(evName)) eventListeners.set(evName, new Set());
          eventListeners.get(evName).add(handlerId);
          return handlerId;
        }
        if (cmd === 'plugin:event|unlisten') {
          const set = eventListeners.get(args.event);
          if (set) set.delete(args.eventId);
          return null;
        }
        if (cmd === 'plugin:event|emit' || cmd === 'plugin:event|emit_to') {
          window.__XIAOWEI_DISPATCH_EVENT__({ event: args.event, payload: args.payload });
          return null;
        }

        let rawBytes = undefined;
        let cleanArgs = args;
        if (args instanceof Uint8Array || args instanceof ArrayBuffer) {
          const u8 = args instanceof Uint8Array ? args : new Uint8Array(args);
          rawBytes = Array.from(u8);
          cleanArgs = {};
        } else if (Array.isArray(args)) {
          rawBytes = args;
          cleanArgs = {};
        }

        return await window.webkit.messageHandlers.tauri.postMessage({
          cmd,
          args: cleanArgs || {},
          rawBytes,
          options: options || null
        });
      }

      const metadata = {
        currentWindow: { label: 'main' },
        currentWebview: { label: 'main', windowLabel: 'main' },
        windows: [{ label: 'main' }],
        webviews: [{ label: 'main', windowLabel: 'main' }]
      };

      window.isTauri = true;
      window.__TAURI_INTERNALS__ = {
        invoke,
        transformCallback,
        unregisterCallback,
        runCallback,
        callbacks,
        metadata,
        convertFileSrc(filePath, protocol = 'asset') {
          if (!filePath) return '';
          if (filePath.startsWith('http:') || filePath.startsWith('https:') || filePath.startsWith('data:')) return filePath;
          return 'file://' + encodeURI(filePath);
        },
        plugins: {
          path: { sep: '/', delimiter: ':' }
        }
      };

      window.__TAURI_EVENT_PLUGIN_INTERNALS__ = {
        unregisterListener(event, id) {
          const set = eventListeners.get(event);
          if (set) set.delete(id);
        }
      };

      window.__TAURI_OS_PLUGIN_INTERNALS__ = {
        arch: 'aarch64',
        exe_extension: '',
        family: 'unix',
        os_type: 'macos',
        platform: 'macos',
        eol: '\n',
        version: '15.0.0'
      };

      window.__TAURI__ = {
        core: { invoke }
      };

      // Support [data-tauri-drag-region] window dragging & double-click zoom on macOS
      document.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        if (e.target && e.target.closest && e.target.closest('canvas, .touch, .containerBox, .activeDeviceBox')) return;
        const el = e.target && e.target.closest ? e.target.closest('[data-tauri-drag-region]') : null;
        if (!el) return;
        const interactive = e.target.closest('button, input, a, select, textarea, canvas, [role="button"], .no-drag, .touch');
        if (interactive && interactive !== el) return;
        if (e.detail === 2) {
          invoke('plugin:window|toggle_maximize');
        } else if (e.buttons === 1) {
          invoke('plugin:window|start_dragging');
        }
      }, true);

      // macOS Cmd+V / Cmd+C support directly onto active/selected iPhones when not editing a UI text input
      document.addEventListener('keydown', async (e) => {
        if (!e.metaKey || e.ctrlKey || e.altKey) return;
        const active = document.activeElement;
        const isTypingInUI = active && (
          active.id !== 'globalDeviceInput' &&
          (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)
        );
        if (isTypingInUI) return;

        const cur = window.storage?.controlDevice?.value || window.storage?.devicesStore?.current;
        const selected = window.storage?.devicesStore?.selectAll || (cur ? [cur] : []);
        const targets = cur ? [cur] : selected;
        if (!targets || targets.length === 0) return;

        if (e.code === 'KeyV') {
          e.preventDefault();
          const clip = await invoke('get_clipboard');
          if (clip) {
            for (const dev of targets) {
              if (dev?.serial) {
                invoke('push_pasteboard', { serial: dev.serial, text: clip });
                invoke('paste_text', { serial: dev.serial, message: clip });
              }
            }
          }
        } else if (e.code === 'KeyC' && !window.getSelection()?.toString()) {
          const primary = targets[0];
          if (primary?.serial) {
            const remoteText = await invoke('pull_pasteboard', { serial: primary.serial });
            if (remoteText) {
              await invoke('put_clipboard', { body: remoteText });
            }
          }
        }
      }, true);

      // Migrate / default to Vietnamese (vi-VN) so even existing profiles boot in clear Vietnamese right away,
      // and enable direct small-screen click control (smoothControl: true) out of the box.
      try {
        if (!localStorage.getItem('__xiaowei_vi_v3')) {
          localStorage.setItem('brandCode', 'WECAN0A95C');
          localStorage.setItem('useLanguage:WECAN0A95C', 'vi-VN');
          localStorage.setItem('useLanguage:null', 'vi-VN');
          localStorage.removeItem('useLanguage');
          localStorage.setItem('isSetDefaultLang:WECAN0A95C', 'true');
          localStorage.setItem('__xiaowei_vi_v3', '1');
        } else if (!localStorage.getItem('useLanguage:WECAN0A95C')) {
          localStorage.setItem('useLanguage:WECAN0A95C', 'vi-VN');
        }
        if (!localStorage.getItem('__xiaowei_touch_v1')) {
          const cfgKey = 'config:WECAN0A95C';
          let cfgObj = {};
          try {
            const rawCfg = localStorage.getItem(cfgKey);
            if (rawCfg) cfgObj = JSON.parse(rawCfg) || {};
          } catch (_) {}
          cfgObj.smoothControl = true;
          localStorage.setItem(cfgKey, JSON.stringify(cfgObj));
          localStorage.removeItem('config');
          localStorage.setItem('__xiaowei_touch_v1', '1');
        }
      } catch (_) {}

      // Auto-trigger Xiaowei's index.html initPromiseResolve once installed
      const bootTimer = setInterval(() => {
        if (typeof window.initPromiseResolve === 'function') {
          clearInterval(bootTimer);
          window.initPromiseResolve();
        }
      }, 60);
      setTimeout(() => clearInterval(bootTimer), 10000);
    })();
    """#

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupMainMenu()
        let rpcPort = startBackendDaemon()
        bridge.rpcPort = rpcPort

        let resourceDir = Bundle.main.resourceURL ?? URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("Resources")
        let webRoot = resourceDir.appendingPathComponent("web")

        let config = WKWebViewConfiguration()
        config.setURLSchemeHandler(TauriSchemeHandler(webRoot: webRoot), forURLScheme: "tauri")
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        let contentController = WKUserContentController()
        let userScript = WKUserScript(source: Self.tauriShimJS, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        contentController.addUserScript(userScript)
        contentController.addScriptMessageHandler(bridge, contentWorld: .page, name: "tauri")
        config.userContentController = contentController

        let rect = NSRect(x: 0, y: 0, width: 1340, height: 840)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Xiaowei iOS (macOS Native)"
        window.minSize = NSSize(width: 960, height: 620)
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = false
        window.standardWindowButton(.closeButton)?.isHidden = true
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true
        window.backgroundColor = NSColor(calibratedRed: 0.09, green: 0.10, blue: 0.13, alpha: 1.0)
        window.center()

        webView = FirstMouseWebView(frame: rect, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsLinkPreview = false
        webView.setValue(false, forKey: "drawsBackground")

        bridge.window = window
        bridge.webView = webView

        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        if rpcPort > 0, let startURL = URL(string: "http://127.0.0.1:\(rpcPort)/index.html") {
            let cacheTypes: Set<String> = [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache]
            WKWebsiteDataStore.default().removeData(ofTypes: cacheTypes, modifiedSince: .distantPast) { [weak self] in
                self?.webView.load(URLRequest(url: startURL, cachePolicy: .reloadIgnoringLocalCacheData))
            }
        } else if let fallbackURL = URL(string: "tauri://localhost/index.html") {
            webView.load(URLRequest(url: fallbackURL))
        }

        eventTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.bridge.pollBackendEvents()
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript("window.initPromiseResolve && window.initPromiseResolve();", completionHandler: nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        eventTimer?.invalidate()
        if let proc = backendProcess, proc.isRunning {
            proc.terminate()
        }
    }

    private func startBackendDaemon() -> Int {
        let resourceDir = Bundle.main.resourceURL ?? URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("Resources")
        let scriptURL = resourceDir.appendingPathComponent("backend_bridge.py")
        let portFile = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("xiaowei_rpc_\(ProcessInfo.processInfo.processIdentifier).json")
        try? FileManager.default.removeItem(at: portFile)

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        proc.arguments = [scriptURL.path, portFile.path]
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            backendProcess = proc
        } catch {
            return 0
        }

        for _ in 0..<50 {
            if let data = try? Data(contentsOf: portFile),
               let info = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
               let port = info["rpc_port"] as? Int, port > 0 {
                try? FileManager.default.removeItem(at: portFile)
                return port
            }
            Thread.sleep(forTimeInterval: 0.05)
        }
        return 0
    }

    private func setupMainMenu() {
        let mainMenu = NSMenu()

        // App menu
        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Giới thiệu Xiaowei iOS", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Ẩn Xiaowei iOS", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Thoát Xiaowei iOS", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu

        // Edit menu (vital for Cmd+C / Cmd+V / Cmd+A / Cmd+Z in WKWebView!)
        let editMenuItem = NSMenuItem()
        mainMenu.addItem(editMenuItem)
        let editMenu = NSMenu(title: "Chỉnh sửa")
        editMenu.addItem(withTitle: "Hoàn tác", action: Selector(("undo:")), keyEquivalent: "z")
        editMenu.addItem(withTitle: "Làm lại", action: Selector(("redo:")), keyEquivalent: "Z")
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(withTitle: "Cắt", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Sao chép", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Dán", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Chọn tất cả", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu

        // Devices & Restore Recovery menu (0đ Apple Configurator + 1-Click Batch WDA Provisioning)
        let deviceMenuItem = NSMenuItem()
        mainMenu.addItem(deviceMenuItem)
        let deviceMenu = NSMenu(title: "Thiết bị & Khôi phục")

        let quickProvItem = NSMenuItem(
            title: "⚡ Cài & Gia hạn WDA hàng loạt (1 chạm)",
            action: #selector(runQuickBatchProvision(_:)),
            keyEquivalent: "r"
        )
        quickProvItem.keyEquivalentModifierMask = [.command, .shift]
        quickProvItem.target = self
        deviceMenu.addItem(quickProvItem)

        let forceRenewItem = NSMenuItem(
            title: "🔄 Bắt buộc cài mới / Gia hạn 7 ngày cho tất cả máy",
            action: #selector(runForceRenewBatchProvision(_:)),
            keyEquivalent: ""
        )
        forceRenewItem.target = self
        deviceMenu.addItem(forceRenewItem)

        deviceMenu.addItem(NSMenuItem.separator())

        let wifiProfileItem = NSMenuItem(
            title: "📶 Tạo file Wi-Fi tự động cho Apple Configurator (.mobileconfig)...",
            action: #selector(showGenerateWiFiProfileDialog(_:)),
            keyEquivalent: ""
        )
        wifiProfileItem.target = self
        deviceMenu.addItem(wifiProfileItem)

        let configuratorItem = NSMenuItem(
            title: "📦 Mở / Tải Apple Configurator (Miễn phí - Mac App Store)",
            action: #selector(openOrDownloadAppleConfigurator(_:)),
            keyEquivalent: ""
        )
        configuratorItem.target = self
        deviceMenu.addItem(configuratorItem)

        deviceMenu.addItem(NSMenuItem.separator())

        let guideItem = NSMenuItem(
            title: "📖 Hướng dẫn Restore trắng & Cài nhiều máy (0đ)",
            action: #selector(openRestoreGuide(_:)),
            keyEquivalent: ""
        )
        guideItem.target = self
        deviceMenu.addItem(guideItem)

        deviceMenuItem.submenu = deviceMenu

        // Window menu
        let windowMenuItem = NSMenuItem()
        mainMenu.addItem(windowMenuItem)
        let windowMenu = NSMenu(title: "Cửa sổ")
        windowMenu.addItem(withTitle: "Thu nhỏ", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Phóng to", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windowMenu.addItem(withTitle: "Đóng cửa sổ", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        windowMenuItem.submenu = windowMenu

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Thiết bị & Khôi phục (Batch Provisioning + Apple Configurator Suite)

    private func resolveResourceFile(_ filename: String) -> URL {
        if let resURL = Bundle.main.resourceURL {
            let candidate = resURL.appendingPathComponent(filename)
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
        }
        let devCandidate = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("Resources")
            .appendingPathComponent(filename)
        if FileManager.default.fileExists(atPath: devCandidate.path) {
            return devCandidate
        }
        return URL(fileURLWithPath: "/Users/bienvu/.gemini/antigravity/scratch/xiaowei-ios-macos/Resources")
            .appendingPathComponent(filename)
    }

    private func showNonBlockingProgressBanner(_ title: String) {
        dismissProgressBanner()
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 430, height: 76),
            styleMask: [.titled, .utilityWindow, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.title = "Xiaowei iOS — Đang xử lý tự động"
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.hidesOnDeactivate = false

        let content = NSView(frame: NSRect(x: 0, y: 0, width: 430, height: 76))
        let spinner = NSProgressIndicator(frame: NSRect(x: 18, y: 22, width: 28, height: 28))
        spinner.style = .spinning
        spinner.controlSize = .regular
        spinner.startAnimation(nil)
        content.addSubview(spinner)

        let label = NSTextField(wrappingLabelWithString: title)
        label.frame = NSRect(x: 58, y: 16, width: 354, height: 44)
        label.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        content.addSubview(label)

        panel.contentView = content
        if let mainWin = window {
            let wf = mainWin.frame
            let px = wf.midX - 215
            let py = wf.maxY - 120
            panel.setFrameOrigin(NSPoint(x: px, y: py))
        } else {
            panel.center()
        }
        panel.orderFront(nil)
        progressPanel = panel
    }

    private func dismissProgressBanner() {
        progressPanel?.orderOut(nil)
        progressPanel = nil
    }

    @objc private func runQuickBatchProvision(_ sender: Any?) {
        executeBatchProvision(renew: false)
    }

    @objc private func runForceRenewBatchProvision(_ sender: Any?) {
        executeBatchProvision(renew: true)
    }

    private func executeBatchProvision(renew: Bool) {
        if isProvisioningInFlight {
            let busyAlert = NSAlert()
            busyAlert.messageText = "Đang xử lý cài đặt hàng loạt"
            busyAlert.informativeText = "Hệ thống đang kiểm tra và cài đặt WDA cho các máy iPhone cắm cáp USB. Vui lòng đợi vài giây..."
            busyAlert.addButton(withTitle: "Đồng ý")
            busyAlert.runModal()
            return
        }

        let scriptURL = resolveResourceFile("batch_provision_ios.py")
        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            let errAlert = NSAlert()
            errAlert.alertStyle = .warning
            errAlert.messageText = "Không tìm thấy công cụ cài đặt hàng loạt"
            errAlert.informativeText = "Thiếu file batch_provision_ios.py tại: \(scriptURL.path)"
            errAlert.addButton(withTitle: "Đóng")
            errAlert.runModal()
            return
        }

        isProvisioningInFlight = true
        let bannerMsg = renew
            ? "Đang bắt buộc cài mới & gia hạn chứng chỉ 7 ngày cho tất cả iPhone cắm USB..."
            : "Đang quét nhanh, tự ghép đôi & cài đặt WDA hàng loạt cho iPhone cắm USB..."
        showNonBlockingProgressBanner(bannerMsg)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            var args = [scriptURL.path, "--auto", "--json"]
            if renew {
                args.append("--renew")
            }
            proc.arguments = args

            let outPipe = Pipe()
            let errPipe = Pipe()
            proc.standardOutput = outPipe
            proc.standardError = errPipe

            var rawOut = Data()
            var launchErr: String? = nil
            do {
                try proc.run()
                rawOut = outPipe.fileHandleForReading.readDataToEndOfFile()
                proc.waitUntilExit()
            } catch {
                launchErr = error.localizedDescription
            }

            DispatchQueue.main.async {
                guard let self = self else { return }
                self.isProvisioningInFlight = false
                self.dismissProgressBanner()

                let alert = NSAlert()
                alert.addButton(withTitle: "Đồng ý")

                if let launchErr = launchErr {
                    alert.alertStyle = .critical
                    alert.messageText = "Không thể chạy công cụ cài đặt hàng loạt"
                    alert.informativeText = launchErr
                    alert.runModal()
                    return
                }

                guard let obj = (try? JSONSerialization.jsonObject(with: rawOut)) as? [String: Any] else {
                    let fallbackStr = String(data: rawOut, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                    alert.alertStyle = .informational
                    alert.messageText = "Kết quả cài đặt WDA hàng loạt"
                    alert.informativeText = fallbackStr.isEmpty ? "Đã hoàn tất xử lý." : fallbackStr
                    alert.runModal()
                    return
                }

                let total = (obj["total"] as? Int) ?? 0
                let summaryVi = (obj["summary_vi"] as? String) ?? ""
                let devices = (obj["devices"] as? [[String: Any]]) ?? []
                let errCount = (obj["error_count"] as? Int) ?? 0

                alert.alertStyle = errCount > 0 ? .warning : .informational
                alert.messageText = renew
                    ? "Kết quả Cài mới / Gia hạn 7 ngày WDA"
                    : "Kết quả Cài & Khôi phục WDA hàng loạt"

                if total == 0 {
                    alert.informativeText = summaryVi
                } else {
                    var lines: [String] = [summaryVi, ""]
                    for (idx, d) in devices.enumerated() {
                        let ready = (d["ready"] as? Bool) ?? false
                        let status = (d["status"] as? String) ?? ""
                        let icon = ready ? "✅" : (status == "error" ? "❌" : "👉")
                        let name = (d["name"] as? String) ?? "iPhone"
                        let model = (d["model"] as? String) ?? "iPhone"
                        let osVer = (d["os_version"] as? String) ?? ""
                        let msgVi = (d["message_vi"] as? String) ?? ""
                        let verPart = osVer.isEmpty ? "" : " (iOS \(osVer))"
                        lines.append("\(idx + 1). \(icon) \(name) — \(model)\(verPart)\n   \(msgVi)")
                    }
                    alert.informativeText = lines.joined(separator: "\n")
                }
                alert.runModal()
            }
        }
    }

    @objc private func showGenerateWiFiProfileDialog(_ sender: Any?) {
        let alert = NSAlert()
        alert.alertStyle = .informational
        alert.messageText = "Tạo file Wi-Fi tự động cho Apple Configurator"
        alert.informativeText = "Nhập Tên Wi-Fi (SSID) và Mật khẩu để tạo file WiFi-Tu-Dong-iPhone.mobileconfig. Gắn file này vào Blueprint của Apple Configurator giúp mọi iPhone sau khi Restore trắng tự động bắt Wi-Fi ngay!"
        alert.addButton(withTitle: "Tạo file .mobileconfig")
        alert.addButton(withTitle: "Hủy")

        let container = NSView(frame: NSRect(x: 0, y: 0, width: 360, height: 112))

        let ssidLabel = NSTextField(labelWithString: "Tên mạng Wi-Fi (SSID):")
        ssidLabel.frame = NSRect(x: 0, y: 88, width: 360, height: 18)
        ssidLabel.font = NSFont.systemFont(ofSize: 12, weight: .semibold)
        container.addSubview(ssidLabel)

        let ssidField = NSTextField(frame: NSRect(x: 0, y: 58, width: 360, height: 26))
        ssidField.placeholderString = "Ví dụ: PhongMay_5G"
        container.addSubview(ssidField)

        let passLabel = NSTextField(labelWithString: "Mật khẩu Wi-Fi (để trống nếu mạng không mật khẩu):")
        passLabel.frame = NSRect(x: 0, y: 32, width: 360, height: 18)
        passLabel.font = NSFont.systemFont(ofSize: 12, weight: .semibold)
        container.addSubview(passLabel)

        let passField = NSTextField(frame: NSRect(x: 0, y: 2, width: 360, height: 26))
        passField.placeholderString = "Nhập mật khẩu Wi-Fi..."
        container.addSubview(passField)

        alert.accessoryView = container
        alert.window.initialFirstResponder = ssidField

        let resp = alert.runModal()
        guard resp == .alertFirstButtonReturn else { return }

        let ssid = ssidField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = passField.stringValue

        guard !ssid.isEmpty else {
            let warn = NSAlert()
            warn.alertStyle = .warning
            warn.messageText = "Chưa nhập Tên mạng Wi-Fi (SSID)"
            warn.informativeText = "Vui lòng nhập chính xác tên mạng Wi-Fi để iPhone tự động kết nối sau khi Restore."
            warn.addButton(withTitle: "Đồng ý")
            warn.runModal()
            return
        }

        let toolkitDir = URL(fileURLWithPath: "/Users/bienvu/.gemini/antigravity/scratch/xiaowei-ios-macos/Bo-Cong-Cu-Restore-Nhieu-May")
        let targetDir: URL
        if FileManager.default.fileExists(atPath: toolkitDir.path) {
            targetDir = toolkitDir
        } else {
            targetDir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
                ?? FileManager.default.homeDirectoryForCurrentUser
        }
        let outURL = targetDir.appendingPathComponent("WiFi-Tu-Dong-iPhone.mobileconfig")
        let scriptURL = resolveResourceFile("batch_provision_ios.py")

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        proc.arguments = [
            scriptURL.path,
            "--gen-wifi-profile",
            "--ssid", ssid,
            "--password", password,
            "--out", outURL.path,
            "--json"
        ]
        let outPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            proc.waitUntilExit()
            if proc.terminationStatus == 0 && FileManager.default.fileExists(atPath: outURL.path) {
                NSWorkspace.shared.activateFileViewerSelecting([outURL])
                let done = NSAlert()
                done.alertStyle = .informational
                done.messageText = "Đã tạo file Wi-Fi tự động thành công!"
                done.informativeText = "File đã lưu tại:\n\(outURL.path)\n\nCách gắn vào Apple Configurator (chỉ làm 1 lần):\n1. Mở Apple Configurator -> Blueprints -> Edit Blueprints -> New\n2. Bấm Add -> Profiles -> chọn file WiFi-Tu-Dong-iPhone.mobileconfig\n3. Bấm Prepare -> tích Supervise devices & ẩn mọi bước Hello/Siri."
                done.addButton(withTitle: "Tuyệt vời")
                done.runModal()
            } else {
                let fail = NSAlert()
                fail.alertStyle = .warning
                fail.messageText = "Không tạo được file .mobileconfig"
                fail.informativeText = "Vui lòng kiểm tra quyền ghi thư mục đích và thử lại."
                fail.addButton(withTitle: "Đóng")
                fail.runModal()
            }
        } catch {
            let fail = NSAlert()
            fail.alertStyle = .critical
            fail.messageText = "Lỗi tạo cấu hình Wi-Fi"
            fail.informativeText = error.localizedDescription
            fail.addButton(withTitle: "Đóng")
            fail.runModal()
        }
    }

    @objc private func openOrDownloadAppleConfigurator(_ sender: Any?) {
        let candidates = [
            "/Applications/Apple Configurator.app",
            "/Applications/Apple Configurator 2.app"
        ]
        for appPath in candidates {
            if FileManager.default.fileExists(atPath: appPath) {
                NSWorkspace.shared.open(URL(fileURLWithPath: appPath))
                return
            }
        }
        if let masURL = URL(string: "macappstore://apps.apple.com/app/apple-configurator/id1037126344"),
           NSWorkspace.shared.open(masURL) {
            return
        }
        if let webURL = URL(string: "https://apps.apple.com/app/apple-configurator/id1037126344") {
            NSWorkspace.shared.open(webURL)
        }
    }

    @objc private func openRestoreGuide(_ sender: Any?) {
        let toolkitGuide = URL(fileURLWithPath: "/Users/bienvu/.gemini/antigravity/scratch/xiaowei-ios-macos/Bo-Cong-Cu-Restore-Nhieu-May/HUONG-DAN-NHANH.md")
        let guideURL = FileManager.default.fileExists(atPath: toolkitGuide.path)
            ? toolkitGuide
            : resolveResourceFile("HUONG-DAN-NHANH.md")

        if FileManager.default.fileExists(atPath: guideURL.path) {
            if !NSWorkspace.shared.open(guideURL) {
                let textEditURL = URL(fileURLWithPath: "/System/Applications/TextEdit.app")
                NSWorkspace.shared.open([guideURL], withApplicationAt: textEditURL, configuration: NSWorkspace.OpenConfiguration(), completionHandler: nil)
            }
        } else {
            let alert = NSAlert()
            alert.messageText = "Hướng dẫn Restore trắng & Cài nhiều máy (0đ)"
            alert.informativeText = "Không tìm thấy file HUONG-DAN-NHANH.md tại \(guideURL.path)."
            alert.addButton(withTitle: "Đóng")
            alert.runModal()
        }
    }
}

// MARK: - Entry Point

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
