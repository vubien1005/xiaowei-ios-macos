#!/usr/bin/env zsh
# 3-Cai-Va-Gia-Han-WDA-Hang-Loat.command
# Chạy 1 chạm cài đặt mới (sau khi Restore trắng) hoặc kiểm tra / gia hạn WDA hàng loạt cho toàn bộ iPhone cắm USB.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROVISIONER=""
for cand in \
  "$SCRIPT_DIR/../Resources/batch_provision_ios.py" \
  "/Applications/Xiaowei iOS.app/Contents/Resources/batch_provision_ios.py" \
  "/Users/bienvu/.gemini/antigravity/scratch/xiaowei-ios-macos/Resources/batch_provision_ios.py"
do
  if [ -f "$cand" ]; then
    PROVISIONER="$cand"
    break
  fi
done

clear
echo "=================================================================="
echo "  ⚡ XIAOWEI iOS — CÀI ĐẶT & KHÔI PHỤC WDA HÀNG LOẠT (1 CHẠM - 0Đ)"
echo "=================================================================="
echo ""

if [ -z "$PROVISIONER" ]; then
  echo "❌ Không tìm thấy công cụ batch_provision_ios.py!"
  printf "\nNhấn Enter để đóng..."
  read -r _
  exit 1
fi

/usr/bin/python3 "$PROVISIONER" --auto "$@"

echo ""
echo "💡 Mẹo: Nếu muốn BẮT BUỘC gia hạn chứng chỉ 7 ngày cho tất cả máy, gõ chữ R rồi nhấn Enter."
if [ -t 0 ]; then
  printf "Nhấn Enter để đóng..."
  read -r USER_CHOICE
  if [[ "${USER_CHOICE:l}" == "r" ]]; then
    echo ""
    /usr/bin/python3 "$PROVISIONER" --auto --renew
    echo ""
    printf "Nhấn Enter để đóng..."
    read -r _
  fi
fi
