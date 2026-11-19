#!/bin/bash
# ==============================================================================
#   XIAOWEI iOS for macOS — SCRIPT CÀI ĐẶT & MỞ APP LẦN ĐẦU TRÊN MÁY MAC MỚI
# ==============================================================================

clear
echo "=================================================================="
echo "    🚀 XIAOWEI iOS (APPLE SILICON) — KHỞI CHẠY TRÊN MÁY MAC MỚI   "
echo "=================================================================="
echo ""

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$DIR/Xiaowei iOS.app"
APP_DEST="/Applications/Xiaowei iOS.app"

# 1. Kiểm tra kiến trúc vi xử lý Apple Silicon
ARCH="$(uname -m)"
echo "[1/4] Kiểm tra phần cứng máy Mac..."
if [ "$ARCH" != "arm64" ]; then
  echo "⚠️ CẢNH BÁO: Máy Mac của bạn đang chạy chip Intel ($ARCH)."
  echo "   Bản build này được tối ưu đặc biệt cho chip Apple Silicon (M1/M2/M3/M4)."
  echo "   Ứng dụng có thể không khởi chạy được hoặc chạy qua Rosetta 2."
  echo ""
else
  echo "✅ Máy Mac Apple Silicon ($ARCH) hợp lệ!"
fi

# 2. Cài đặt vào thư mục Ứng dụng (/Applications)
echo "[2/4] Kiểm tra và cài đặt ứng dụng vào /Applications..."
if [ -d "$APP_SRC" ]; then
  if [ -d "$APP_DEST" ]; then
    echo "ℹ️  Đã có 'Xiaowei iOS.app' trong /Applications. Đang cập nhật bản mới nhất..."
    rm -rf "$APP_DEST"
  fi
  cp -R "$APP_SRC" /Applications/
  echo "✅ Đã chép 'Xiaowei iOS.app' vào thư mục /Applications thành công!"
  TARGET_APP="$APP_DEST"
elif [ -d "$APP_DEST" ]; then
  echo "✅ Tìm thấy 'Xiaowei iOS.app' đã có sẵn trong /Applications."
  TARGET_APP="$APP_DEST"
else
  echo "❌ Không tìm thấy 'Xiaowei iOS.app' trong thư mục cài đặt!"
  echo "   Vui lòng giải nén toàn bộ thư mục và để file .command cùng với Xiaowei iOS.app."
  echo ""
  read -p "Nhấn Enter để thoát..."
  exit 1
fi

# 3. Gỡ bỏ kiểm duyệt Gatekeeper (Quarantine) & Cấp quyền thực thi
echo "[3/4] Gỡ chặn bảo mật macOS (Gatekeeper Quarantine) & phân quyền..."
xattr -cr "$TARGET_APP" 2>/dev/null || true
xattr -dr com.apple.quarantine "$TARGET_APP" 2>/dev/null || true
chmod -R 755 "$TARGET_APP" 2>/dev/null || true
chmod +x "$TARGET_APP/Contents/MacOS/XiaoweiIOS" 2>/dev/null || true
chmod +x "$TARGET_APP/Contents/Resources/backend_bridge.py" 2>/dev/null || true
chmod +x "$TARGET_APP/Contents/Resources/batch_provision_ios.py" 2>/dev/null || true

# Cấp quyền cho bộ công cụ Restore đi kèm nếu có
if [ -d "$DIR/Bo-Cong-Cu-Restore-Nhieu-May" ]; then
  chmod +x "$DIR/Bo-Cong-Cu-Restore-Nhieu-May"/*.command 2>/dev/null || true
  chmod +x "$DIR/Bo-Cong-Cu-Restore-Nhieu-May"/batch_provision_ios.py 2>/dev/null || true
fi

echo "✅ Đã gỡ bỏ cách ly bảo mật Gatekeeper và kích hoạt quyền chạy thành công!"

# 4. Kiểm tra môi trường Python
echo "[4/4] Kiểm tra môi trường hệ thống..."
if [ -x "/usr/bin/python3" ]; then
  PY_VER=$(/usr/bin/python3 --version 2>&1)
  echo "✅ Môi trường Python: $PY_VER (Sẵn sàng)"
else
  echo "⚠️ Chưa tìm thấy Python3 mặc định. Nếu máy hỏi cài đặt Command Line Tools, hãy chọn 'Install'."
fi

echo ""
echo "=================================================================="
echo "  🎉 CÀI ĐẶT HOÀN TẤT! ĐANG MỞ ỨNG DỤNG XIAOWEI iOS..."
echo "=================================================================="
echo ""
echo "💡 MẸO SỬ DỤNG:"
echo "   - Từ lần sau, bạn có thể mở trực tiếp từ Launchpad hoặc"
echo "     bấm vào icon 'Xiaowei iOS' trong thư mục Applications."
echo "   - Cắm iPhone qua cáp USB, mở khóa màn hình và bấm 'Tin cậy (Trust)'."
echo "   - Dùng phím tắt Cmd+Shift+R để nạp WDA siêu tốc cho toàn bộ dàn máy."
echo "=================================================================="
echo ""

open "$TARGET_APP"

sleep 2
exit 0
