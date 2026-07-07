#!/bin/bash
# Установка «Focusboard V2»:
#   1) копирует собранное приложение в /Applications
#   2) ставит launchd-агент v2-api (:3002, KeepAlive) — миссии и «Пульс»
#   3) добавляет Focusboard V2 в объекты входа, убирает старый Focus Board
#   4) чистит старое имя «Денис Таск Трекер», если оно осталось от прошлой версии
# Бэкенд v1 (com.focusboard.backend, :3001) НЕ трогается — на нём живут данные.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Focusboard V2"
OLD_APP_NAME="Денис Таск Трекер"
BUILT_APP=$(ls -d "$DIR"/release/mac*/"$APP_NAME".app 2>/dev/null | head -1 || true)
DEST_APP="/Applications/$APP_NAME.app"
AGENT_LABEL="com.denis-task-tracker.v2api"
AGENT_PLIST="$HOME/Library/LaunchAgents/$AGENT_LABEL.plist"

if [ -z "$BUILT_APP" ]; then
  echo "✗ Сначала собери приложение:  cd \"$DIR\" && npm run electron:build"
  exit 1
fi

echo "→ Убираю старое имя «${OLD_APP_NAME}», если осталось…"
osascript -e "tell application \"System Events\" to delete login item \"$OLD_APP_NAME\"" >/dev/null 2>&1 || true
rm -rf "/Applications/$OLD_APP_NAME.app"

echo "→ Копирую в /Applications…"
rm -rf "$DEST_APP"
cp -R "$BUILT_APP" "$DEST_APP"

# Ad-hoc подпись + снятие карантина. Нужно, если .app собирался не на macOS
# (Apple Silicon не запускает неподписанные arm64-бинарники). Безвредно, если уже подписан.
echo "→ Ad-hoc подпись и снятие карантина…"
codesign --force --deep --sign - "$DEST_APP" >/dev/null 2>&1 || true
xattr -dr com.apple.quarantine "$DEST_APP" >/dev/null 2>&1 || true

echo "→ Ставлю launchd-агент v2-api…"
NODE_BIN="$(command -v node || true)"
[ -z "$NODE_BIN" ] && { echo "✗ node не найден в PATH"; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$AGENT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$AGENT_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$NODE_BIN</string>
    <string>$DIR/api/server.js</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/dtt-v2api.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/dtt-v2api.log</string>
</dict>
</plist>
PLIST
launchctl unload "$AGENT_PLIST" 2>/dev/null || true
launchctl load "$AGENT_PLIST"

echo "→ Включаю автозапуск Focusboard V2 (macOS спросит разрешение — разреши)…"
osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$DEST_APP\", hidden:false}" >/dev/null 2>&1 || true

echo "→ Ставлю launchd-агент оболочки (KeepAlive — «всегда открыт», перезапуск после выхода)…"
SHELL_LABEL="com.denis.focusboardv2.shell"
SHELL_PLIST="$HOME/Library/LaunchAgents/$SHELL_LABEL.plist"
APP_BIN="$DEST_APP/Contents/MacOS/$APP_NAME"
cat > "$SHELL_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$SHELL_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$APP_BIN</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/dtt-v2shell.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/dtt-v2shell.log</string>
</dict>
</plist>
PLIST
launchctl unload "$SHELL_PLIST" 2>/dev/null || true
launchctl load "$SHELL_PLIST"

echo "→ Выключаю автозапуск старого Focus Board (launchd com.focusboard.app)…"
V1_APP_PLIST="$HOME/Library/LaunchAgents/com.focusboard.app.plist"
if [ -f "$V1_APP_PLIST" ]; then
  launchctl unload -w "$V1_APP_PLIST" 2>/dev/null || true
  echo "   (окно старого Focus Board при этом закроется — это ожидаемо)"
else
  osascript -e 'tell application "System Events" to delete login item "Focus Board"' >/dev/null 2>&1 || true
fi
# com.focusboard.backend и com.focusboard.frontend НЕ трогаем: бэкенд — общие данные

echo
echo "✓ Готово:"
echo "  • $DEST_APP (иконка и имя — как просил)"
echo "  • v2-api на :3002 — постоянный (launchd), лог: ~/Library/Logs/dtt-v2api.log"
echo "  • Оболочка (com.denis.focusboardv2.shell) — KeepAlive: приложение всегда открыто,"
echo "    перезапускается даже после Cmd+Q. Лог: ~/Library/Logs/dtt-v2shell.log"
echo "  • Автозапуск: Focusboard V2 включён, старый Focus Board выключен"
echo "  • Утром приложение само напомнит заполнить экран (нативные уведомления)"
echo
echo "Проверь: launchctl list | grep denis ; открой приложение из /Applications"
echo "Отключить «всегда открыт»:  launchctl unload -w \"$SHELL_PLIST\""
