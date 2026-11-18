# Xiaowei iOS for macOS (Apple Silicon Native) 🚀📱

Ứng dụng điều khiển, quản lý và tự động hóa hàng loạt iPhone qua USB dành riêng cho **macOS (Apple Silicon arm64)**, được chuyển đổi và tối ưu hóa toàn diện từ phiên bản Windows sang kiến trúc Native macOS mượt mà, ổn định với **giao diện 100% Tiếng Việt**.

---

## ✨ Điểm Nổi Bật & Tính Năng Chính

### 1. Native macOS Performance (Apple Silicon)
- **Tốc độ phản hồi cực nhanh**: Tích hợp nhân điều khiển **Turbo WebDriverAgent (WDA)** tùy biến với các endpoint chuyên biệt (`/wda/fastTap`, `/wda/fastSwipe`, `/wda/fastHold`, `/wda/fastKeys`, `/wda/fastButton`), đưa độ trễ thao tác xuống chỉ còn **~3 – 6 ms** (thay vì 500 – 800 ms như WDA mặc định).
- **Màn hình truyền trực tiếp (Streaming) mượt mà**: Luồng hình ảnh MJPEG qua cổng USB đạt **~35 – 36 FPS**, không giật lag.
- **Hỗ trợ 1-click & Trackpad Tap-to-Click**: Tương thích hoàn hảo với chuột và tính năng chạm để bấm (Tap-to-Click) trên bàn rê chuột MacBook, phản hồi tức thì với 0ms giữ chuột.

### 2. Giao Diện Việt Hóa 100% & Co Giãn Linh Hoạt
- **100% Tiếng Việt chuẩn**: Dịch toàn bộ 2,389 chuỗi giao diện, không còn sót tiếng Trung hay tiếng Thái.
- **Thanh công cụ điều khiển co giãn (Resizable Toolbar)**: Bảng công cụ bên phải cho phép kéo chuột co giãn tự do từ `150px` đến `480px`, tự động ghi nhớ kích thước đã chọn và hỗ trợ nháy đúp để căn chuẩn `275px` giúp hiển thị đầy đủ mọi nhãn chức năng.

### 3. Bộ Công Cụ Restore & Cài Hàng Loạt 1 Chạm ($0 Chi Phí)
- **Tự động hóa hoàn toàn với Apple Configurator**:
  - Tạo hồ sơ cấu hình Wi-Fi tự động (`.mobileconfig`) chỉ với 1 cú click.
  - Tự động bỏ qua toàn bộ các bước thiết lập ban đầu (*Hello*, Siri, Face ID/Passcode, Apple ID...) và tự động **Tin cậy (Trust)** máy Mac sau khi Restore trắng.
- **Bộ công cụ nạp WDA song song**:
  - Tự động nhận diện thiết bị mới hoặc vừa Restore.
  - Tự động kích hoạt hiển thị **Chế độ nhà phát triển (Developer Mode)** trên iOS 16, 17, 18+ mà không cần mở Xcode.
  - Tự động đăng ký UDID và cài đặt/gia hạn chứng chỉ 7 ngày miễn phí cho cả dàn máy.
  - Tích hợp sẵn menu **Thiết bị & Khôi phục** ngay trên thanh menu macOS (`Cmd + Shift + R`).

---

## 🏛️ Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────────────────┐
│                      macOS App Bundle                       │
│                   (/Applications/Xiaowei iOS.app)           │
├──────────────────────────────┬──────────────────────────────┤
│ Frontend (Vue 3 / Naive UI)  │ Native Cocoa Shell (Swift)   │
│ - 100% Tiếng Việt (vi-VN)    │ - WKWebView with FirstMouse  │
│ - Resizable Control Panel    │ - Tauri 2 IPC Shim           │
│ - Low-latency Touch Canvas   │ - Native Menus & Shortcuts   │
├──────────────────────────────┴──────────────────────────────┤
│               macOS Python Service (backend_bridge.py)      │
│ - Static & RPC HTTP Server (127.0.0.1:19881)                │
│ - High-throughput WebSocket Server (127.0.0.1:55556)        │
│ - AFC File Manager & App Installation Manager               │
│ - Fast WDA Connection Pool & Auto-Healing Daemon            │
├─────────────────────────────────────────────────────────────┤
│                    Apple USB Stack (/var/run/usbmuxd)       │
│ - Lockdown Service           │ - tidevice (Core Automation) │
│ - MJPEG Video Stream (9100)  │ - Turbo WDA Service (8100)   │
└──────────────────────────────┴──────────────────────────────┘
                              │ USB Lightning / Type-C Cable
┌─────────────────────────────▼───────────────────────────────┐
│               Dàn iPhone (iOS 12 -> iOS 18+)                │
│             com.bienvu.wda2026.runner.xctrunner             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Cấu Trúc Dự Án

```
xiaowei-ios-macos/
├── Sources/
│   └── main.swift               # Mã nguồn Native Swift (Cocoa, WKWebView, Tauri 2 IPC shim)
├── Resources/
│   ├── backend_bridge.py        # Python backend daemon (usbmuxd, RPC, WebSocket, WDA pool)
│   ├── batch_provision_ios.py   # Tool nạp/gia hạn WDA & kích hoạt Developer Mode hàng loạt
│   ├── WebDriverAgentRunner.ipa # Gói Turbo WDA siêu tốc đã ký
│   ├── Info.plist               # Cấu hình macOS App Bundle
│   ├── AppIcon.icns             # Icon chuẩn macOS
│   ├── sys_config.toml          # Mã định danh phiên bản/thương hiệu
│   └── web/                     # Bộ tài nguyên giao diện Vue 3 đã Việt hóa 100%
├── Bo-Cong-Cu-Restore-Nhieu-May/ # Thư mục công cụ chạy ngoài Finder cho người dùng
│   ├── 1-Tai-Hoac-Mo-Apple-Configurator.command
│   ├── 2-Tao-Cau-Hinh-WiFi-Tu-Dong.command
│   ├── 3-Cai-Va-Gia-Han-WDA-Hang-Loat.command
│   └── HUONG-DAN-NHANH.md
├── build.sh                     # Script tự động biên dịch và đóng gói ứng dụng .app
├── localize_vi.py               # Bộ công cụ quét và ánh xạ Việt hóa 2,389 mục
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Biên Dịch (Build from Source)

### Yêu Cầu Hệ Thống:
- Máy Mac chạy chip **Apple Silicon (M1 / M2 / M3 / M4)**.
- macOS 13.0 trở lên.
- Đã cài đặt **Command Line Tools** hoặc **Xcode** (`xcode-select --install`).
- Python 3.9+ (mặc định có sẵn trên macOS).

### Các bước biên dịch:

1. **Clone repository về máy:**
   ```bash
   git clone https://github.com/vubien1005/xiaowei-ios-macos.git
   cd xiaowei-ios-macos
   ```

2. **Cài đặt thư viện Python bổ trợ:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install tidevice pillow pyOpenSSL
   ```

3. **Chạy script build ứng dụng:**
   ```bash
   chmod +x build.sh
   ./build.sh
   ```

4. **Cài đặt vào thư mục Ứng dụng:**
   ```bash
   cp -R "build/Xiaowei iOS.app" /Applications/
   ```

Ứng dụng **Xiaowei iOS** sẽ xuất hiện trong Launchpad và thư mục `/Applications`, sẵn sàng sử dụng.

---

## ⚡ Hướng Dẫn Sử Dụng Nhanh

1. Cắm iPhone vào máy Mac qua cáp USB, mở khóa màn hình và chọn **Tin cậy máy tính này (Trust)** nếu được hỏi.
2. Mở ứng dụng **Xiaowei iOS.app**.
3. Thiết bị sẽ tự động xuất hiện trên màn hình lưới. Bạn có thể:
   - Click chuột hoặc chạm bàn rê để mở ứng dụng ngay tức thì.
   - Nháy đúp vào thiết bị để mở chế độ **Màn hình lớn**.
   - Kéo cạnh phải của **Thanh công cụ điều khiển** để phóng to/thu nhỏ danh sách chức năng theo ý muốn.
   - Sử dụng phím tắt `Cmd + Shift + R` (hoặc menu **Thiết bị & Khôi phục**) để tự động cài đặt/gia hạn WDA cho nhiều máy cùng lúc.

---

## 📄 Bản Quyền & Giấy Phép

Dự án phục vụ mục đích nghiên cứu, học tập, tối ưu hóa giao diện và trải nghiệm quản lý thiết bị iOS trên nền tảng macOS.
Mọi bản quyền thương hiệu thuộc về chủ sở hữu tương ứng.
