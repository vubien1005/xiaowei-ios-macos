# 📖 Hướng Dẫn Restore Trắng & Tự Động Hóa Nhiều Máy iPhone (Chi Phí 0đ)

Giải pháp **100% chính chủ Apple & hoàn toàn miễn phí (0đ)** kết hợp **Apple Configurator** + **Bộ công cụ 1 chạm Xiaowei iOS**, giúp bạn Restore trắng 1 máy hoặc hàng chục máy iPhone qua Hub USB mà **không phải gõ Wi-Fi, không phải bấm qua từng bước Hello / Siri / Mật khẩu / Apple ID, tự nhận Tin cậy (Trust) máy Mac và tự cài lại Turbo WDA siêu mượt**.

---

## 🛠️ PHẦN 1: Chuẩn Bị 1 Lần Duy Nhất (Chỉ mất ~3 phút)

Bạn chỉ cần thiết lập **Bản thiết kế (Blueprint)** này đúng **1 lần đầu tiên** trên máy Mac. Từ lần sau cứ cắm máy vào là dùng mãi mãi:

### Bước 1: Cài đặt Apple Configurator (Miễn phí trên Mac App Store)
- Nháy đúp file **`1-Tai-Hoac-Mo-Apple-Configurator.command`** (hoặc trong ứng dụng **Xiaowei iOS**, bấm menu trên cùng **Thiết bị & Khôi phục -> 📦 Mở / Tải Apple Configurator**).
- Tải miễn phí từ Mac App Store và mở ứng dụng lên.

### Bước 2: Tạo file Wi-Fi tự động (`.mobileconfig`)
- Nháy đúp file **`2-Tao-Cau-Hinh-WiFi-Tu-Dong.command`** (hoặc vào menu **Thiết bị & Khôi phục -> 📶 Tạo file Wi-Fi tự động cho Apple Configurator**).
- Nhập **Tên Wi-Fi (SSID)** và **Mật khẩu Wi-Fi** của phòng máy -> hệ thống sẽ xuất ngay file **`WiFi-Tu-Dong-iPhone.mobileconfig`**.

### Bước 3: Tạo Bản thiết kế (Blueprint) bỏ qua mọi màn hình Hello
1. Trong **Apple Configurator**, chọn thanh menu trên cùng: **Blueprints (Bản thiết kế) -> Edit Blueprints (Chỉnh sửa bản thiết kế) -> bấm nút `New` (Mới)** ở góc dưới và đặt tên (ví dụ: `Setup Nhanh Xiaowei`).
2. **Gắn Wi-Fi tự động**: Bấm nút **`Add` (Thêm) -> `Profiles` (Hồ sơ)** trên thanh công cụ -> chọn file **`WiFi-Tu-Dong-iPhone.mobileconfig`** vừa tạo.
3. **Bỏ qua màn hình Hello & Tự động Tin cậy (Supervise)**:
   - Bấm nút **`Prepare` (Chuẩn bị)** trên thanh công cụ.
   - Chọn **Manual Configuration (Cấu hình thủ công)** -> tích chọn:
     - ✅ **Supervise devices (Giám sát thiết bị)** *(giúp máy Mac tự động được Tin cậy / Trust 100%, không cần bấm tay trên iPhone!)*
     - ✅ **Allow devices to pair with other computers (Cho phép ghép đôi với máy tính)**
     - *(Bỏ tích "Add to Automated Device Enrollment")* -> bấm **Next**.
   - Chọn **Do not enroll in MDM (Không đăng ký MDM)** -> bấm **Next**.
   - Tạo hoặc chọn Tên Tổ chức bất kỳ (ví dụ: `Xiaowei Lab`) và chọn *Generate a new supervision identity* -> bấm **Next**.
   - Ở mục **Configure iOS Setup Assistant (Các bước thiết lập iOS)**: đổi sang **Do not show any of these steps (Không hiển thị bất kỳ bước nào)** -> bấm **Prepare**.
4. Bấm nút **`Done` (Xong)** ở góc dưới phải để lưu Bản thiết kế.

---

## ⚡ PHẦN 2: Quy Trình Mỗi Khi Cần Restore Trắng 1 Máy Hoặc 10 Máy

Mỗi khi cần dọn sạch trắng máy (xóa toàn bộ dữ liệu về xuất xưởng):

### Bước 1: Restore & Áp dụng Bản thiết kế trên Apple Configurator
1. Cắm cáp USB tất cả iPhone cần làm trắng vào Hub USB nối với máy Mac.
2. Mở **Apple Configurator**, bôi đen chọn tất cả máy cần làm trắng:
   - Chuột phải chọn **`Restore` (Khôi phục)** nếu muốn tải/chạy lại iOS trắng tinh (Apple Configurator sẽ tải sẵn 1 bản iOS vào máy Mac và chép song song ra nhiều máy cực nhanh).
   - Sau khi Restore xong (hoặc bấm gộp ngay từ đầu): Chuột phải chọn **`Apply` (Áp dụng) -> `Setup Nhanh Xiaowei`**.
3. Toàn bộ dàn iPhone sẽ **tự động kết nối Wi-Fi, bỏ qua 100% màn hình Hello / ngôn ngữ / vùng / Siri / mật khẩu**, vào thẳng **Màn hình chính (Home Screen)** và **tự nhận Tin cậy máy Mac**!

### Bước 2: Chạy 1 Chạm Cài Đặt & Lên Hình Trên Xiaowei iOS
Thực hiện **1 trong 2 cách** cực nhanh sau (chỉ tốn vài giây):
- **Cách A (Ngay trong Xiaowei iOS)**: Trên thanh menu trên cùng của macOS, chọn **Thiết bị & Khôi phục -> ⚡ Cài & Gia hạn WDA hàng loạt (1 chạm)** (phím tắt **`Cmd + Shift + R`**).
- **Cách B (Ngoài Finder)**: Nháy đúp file **`3-Cai-Va-Gia-Han-WDA-Hang-Loat.command`**.

> 💡 **Tự động khôi phục ngầm (Auto-Heal)**: Ngay cả khi bạn quên bấm nút, khi **Xiaowei iOS** đang mở mà phát hiện iPhone vừa Restore xong (đã bật Chế độ nhà phát triển nhưng chưa có WDA), ứng dụng cũng sẽ **tự động cài ngầm Turbo WDA và tự lên hình** cho bạn!

---

## 📌 2 Lưu Ý Nhỏ Khi Dùng Apple ID Cá Nhân Miễn Phí (0đ) & iOS 16+

1. **Chế độ Nhà phát triển (Developer Mode) trên iOS 16 / 17 / 18+ sau khi Restore trắng**:
   - Bình thường sau khi Restore trắng, Apple ẩn mục *Developer Mode* đi và bắt phải mở Xcode nặng nề mới hiện ra.
   - Bộ công cụ **Xiaowei iOS** đã **tự động mở khóa hiển thị mục này ngay lập tức**! Bạn chỉ cần mở trên iPhone: **Cài đặt -> Quyền riêng tư & Bảo mật -> Chế độ nhà phát triển (Developer Mode) -> Gạt Bật & Khởi động lại**.
2. **Chứng chỉ Apple ID miễn phí (0đ — hạn 7 ngày & máy mới tinh)**:
   - **Thêm iPhone mới tinh chưa từng cắm bao giờ**: Chỉ cần cắm cáp và bấm **⚡ Cài & Gia hạn WDA hàng loạt**, công cụ sẽ tự động gọi Xcode đăng ký mã UDID máy mới lên Apple (0đ) và đóng gói lại bộ **Turbo WDA siêu tốc (<5ms)** tương thích mọi đời iOS 15–18+.
   - **Xác nhận Tin cậy nhà phát triển lần đầu sau Restore**: Vào **Cài đặt -> Cài đặt chung -> Quản lý VPN & Thiết bị -> bấm Tin cậy (Trust)** tên Apple ID của bạn (chỉ bấm 1 lần sau khi Restore, máy đã có sẵn Wi-Fi tự động nên xác thực trong 1 giây).
   - **Gia hạn định kỳ sau mỗi 7 ngày**: Bấm menu **Thiết bị & Khôi phục -> 🔄 Bắt buộc cài mới / Gia hạn 7 ngày cho tất cả máy** — 1 cú click làm mới toàn bộ dàn máy!
