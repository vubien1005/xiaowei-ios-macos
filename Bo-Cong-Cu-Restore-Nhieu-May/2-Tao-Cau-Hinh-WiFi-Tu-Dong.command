#!/usr/bin/env zsh
# 2-Tao-Cau-Hinh-WiFi-Tu-Dong.command
# Trình hướng dẫn tiếng Việt tạo file WiFi-Tu-Dong-iPhone.mobileconfig cho Apple Configurator Blueprints.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROVISIONER=""
for cand in \
  "$SCRIPT_DIR/batch_provision_ios.py" \
  "$SCRIPT_DIR/../Resources/batch_provision_ios.py" \
  "/Applications/Xiaowei iOS.app/Contents/Resources/batch_provision_ios.py" \
  "$SCRIPT_DIR/../Xiaowei iOS.app/Contents/Resources/batch_provision_ios.py"
do
  if [ -f "$cand" ]; then
    PROVISIONER="$cand"
    break
  fi
done

clear
echo "=================================================================="
echo "  📶 TẠO CẤU HÌNH WI-FI TỰ ĐỘNG CHO APPLE CONFIGURATOR (.mobileconfig)"
echo "=================================================================="
echo "File tạo ra giúp dàn iPhone sau khi Restore trắng TỰ BẮT WI-FI ngay lập tức"
echo "(không cần gõ tay tên mạng và mật khẩu trên từng máy)."
echo ""

if [ -z "$PROVISIONER" ]; then
  echo "❌ Không tìm thấy công cụ batch_provision_ios.py!"
  printf "\nNhấn Enter để đóng..."
  read -r _
  exit 1
fi

printf "1) Nhập TÊN MẠNG WI-FI (SSID, phân biệt chữ hoa/thường): "
read -r WIFI_SSID

while [ -z "${WIFI_SSID// /}" ]; do
  printf "   ⚠️ Tên mạng Wi-Fi không được để trống. Vui lòng nhập lại SSID: "
  read -r WIFI_SSID
done

printf "2) Nhập MẬT KHẨU WI-FI (bấm Enter bỏ qua nếu là mạng không mật khẩu): "
read -r WIFI_PASS

OUT_FILE="$SCRIPT_DIR/WiFi-Tu-Dong-iPhone.mobileconfig"
echo ""
/usr/bin/python3 "$PROVISIONER" \
  --gen-wifi-profile \
  --ssid "$WIFI_SSID" \
  --password "$WIFI_PASS" \
  --out "$OUT_FILE"

if [ $? -eq 0 ] && [ -f "$OUT_FILE" ]; then
  /usr/bin/plutil -lint "$OUT_FILE" >/dev/null 2>&1 && echo "   (Kiểm tra định dạng chuẩn Apple plist: HỢP LỆ 100%)"
  echo ""
  echo "📌 CÁCH GẮN VÀO APPLE CONFIGURATOR (Chỉ làm 1 lần duy nhất):"
  echo "   1. Mở Apple Configurator -> Menu 'Blueprints (Bản thiết kế)' -> 'Edit Blueprints' -> 'New'"
  echo "   2. Bấm nút 'Add (Thêm)' -> 'Profiles (Hồ sơ)' -> Chọn file:"
  echo "      $OUT_FILE"
  echo "   3. Bấm 'Prepare (Chuẩn bị)' -> Tích 'Supervise devices (Giám sát)' & ẩn mọi bước Hello/Siri."
  open -R "$OUT_FILE" 2>/dev/null || true
fi

echo ""
if [ -t 0 ]; then
  printf "Nhấn Enter để đóng..."
  read -r _
fi
