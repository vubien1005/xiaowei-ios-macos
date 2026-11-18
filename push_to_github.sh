#!/usr/bin/env zsh
set -e

cd "$(dirname "$0")"

echo "=== Đẩy dự án Xiaowei iOS lên GitHub ==="

# Kiểm tra kết nối SSH
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo "✅ Đã xác thực SSH thành công với GitHub!"
  git push -u origin main
  echo "🚀 Đã đẩy mã nguồn lên GitHub thành công!"
  exit 0
fi

echo "⚠️ Chưa xác thực SSH với GitHub."
echo "Bạn có thể chọn 1 trong 2 cách sau:"
echo "1. Thêm SSH Key vào GitHub (Khuyên dùng - chỉ làm 1 lần):"
echo "   - Mã SSH Key đã được sao chép vào Clipboard (hoặc xem trong ~/.ssh/id_ed25519.pub)"
echo "   - Mở: https://github.com/settings/ssh/new và dán vào."
echo ""
echo "2. Hoặc nhập GitHub Personal Access Token (Classic hoặc Fine-grained có quyền repo):"
read -s "TOKEN?Nhập GitHub Token: "
echo ""

if [ -n "$TOKEN" ]; then
  git remote set-url origin "https://vubien1005:${TOKEN}@github.com/vubien1005/xiaowei-ios-macos.git"
  git push -u origin main
  # Đổi lại URL sạch không lộ token trong config
  git remote set-url origin "https://github.com/vubien1005/xiaowei-ios-macos.git"
  echo "🚀 Đã đẩy mã nguồn lên GitHub thành công qua Token!"
fi
