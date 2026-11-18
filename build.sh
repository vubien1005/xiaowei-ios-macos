#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Xiaowei iOS.app"
APP_BUNDLE="$ROOT_DIR/build/$APP_NAME"
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"

echo "[1/4] Preparing bundle structure..."
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$RES_DIR"

echo "[2/4] Compiling native Apple Silicon (arm64) binary..."
/usr/bin/swiftc \
  -O \
  -framework Cocoa \
  -framework WebKit \
  -framework UniformTypeIdentifiers \
  "$ROOT_DIR/Sources/main.swift" \
  -o "$MACOS_DIR/XiaoweiIOS"

echo "[3/4] Copying extracted UI assets, icon, and macOS iOS bridge..."
cp "$ROOT_DIR/Resources/Info.plist" "$CONTENTS/Info.plist"
cp "$ROOT_DIR/Resources/AppIcon.icns" "$RES_DIR/AppIcon.icns"
cp "$ROOT_DIR/Resources/sys_config.toml" "$RES_DIR/sys_config.toml"
cp "$ROOT_DIR/Resources/backend_bridge.py" "$RES_DIR/backend_bridge.py"
chmod +x "$RES_DIR/backend_bridge.py"
cp "$ROOT_DIR/Resources/batch_provision_ios.py" "$RES_DIR/batch_provision_ios.py"
chmod +x "$RES_DIR/batch_provision_ios.py"
if [ -f "$ROOT_DIR/Resources/HUONG-DAN-NHANH.md" ]; then
  cp "$ROOT_DIR/Resources/HUONG-DAN-NHANH.md" "$RES_DIR/HUONG-DAN-NHANH.md"
fi
if [ -d "$ROOT_DIR/.venv/lib/python3.9/site-packages" ]; then
  cp -R "$ROOT_DIR/.venv/lib/python3.9/site-packages" "$RES_DIR/site-packages"
fi
if [ -f "$ROOT_DIR/Resources/WebDriverAgentRunner.ipa" ]; then
  cp "$ROOT_DIR/Resources/WebDriverAgentRunner.ipa" "$RES_DIR/WebDriverAgentRunner.ipa"
fi
cp -R "$ROOT_DIR/Resources/web" "$RES_DIR/web"

echo "[4/4] Ad-hoc signing app bundle for macOS..."
/usr/bin/codesign --force --deep --sign - "$APP_BUNDLE"

echo "Done! Built: $APP_BUNDLE"
