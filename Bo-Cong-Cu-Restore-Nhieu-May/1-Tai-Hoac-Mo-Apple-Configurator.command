#!/usr/bin/env zsh
# 1-Tai-Hoac-Mo-Apple-Configurator.command
# Mở Apple Configurator nếu đã cài trên máy Mac, hoặc mở trang tải miễn phí (0đ) trên Mac App Store.

clear
echo "=================================================================="
echo "  📦 XIAOWEI iOS — MỞ / TẢI APPLE CONFIGURATOR (CHÍNH CHỦ 0Đ)"
echo "=================================================================="
echo ""

if [ -d "/Applications/Apple Configurator.app" ]; then
  echo "✅ Đã tìm thấy Apple Configurator trên máy Mac! Đang mở ứng dụng..."
  open -a "/Applications/Apple Configurator.app"
elif [ -d "/Applications/Apple Configurator 2.app" ]; then
  echo "✅ Đã tìm thấy Apple Configurator 2 trên máy Mac! Đang mở ứng dụng..."
  open -a "/Applications/Apple Configurator 2.app"
else
  echo "👉 Máy Mac chưa cài Apple Configurator."
  echo "   Đang mở trực tiếp trang tải MIỄN PHÍ (0đ) chính chủ Apple trên Mac App Store..."
  open "macappstore://apps.apple.com/app/apple-configurator/id1037126344" 2>/dev/null || \
    open "https://apps.apple.com/app/apple-configurator/id1037126344"
  echo ""
  echo "💡 Sau khi bấm 'Nhận / Cài đặt' trên App Store xong:"
  echo "   1. Chạy file số 2 (2-Tao-Cau-Hinh-WiFi-Tu-Dong.command) để tạo file Wi-Fi tự động."
  echo "   2. Tạo 1 Bản thiết kế (Blueprint) trong Apple Configurator gắn file Wi-Fi + bật Giám sát (Supervise)."
fi

echo ""
if [ -t 0 ]; then
  printf "Nhấn Enter để đóng..."
  read -r _
fi
