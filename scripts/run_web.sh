#!/usr/bin/env bash
# 啟動 pygbag dev server，建置時暫時把不需要打包的大檔案搬到 /tmp，
# 結束後（不論 pygbag 正常退出或 Ctrl+C）會搬回原位。
#
# 用法：
#   bash scripts/run_web.sh
#   bash scripts/run_web.sh --port 8080
#
# 加額外 pygbag 參數會直接傳遞下去。

set -e

EXCLUDED=(
  "assets/pic/kenney_tower-defense-top-down"
  "assets/sfx/_old_wav"
)

STASH_DIR="/tmp/tower_defense_excluded_$$"
mkdir -p "$STASH_DIR"

# 搬走（保持原始相對路徑結構）
for path in "${EXCLUDED[@]}"; do
  if [ -e "$path" ]; then
    mkdir -p "$STASH_DIR/$(dirname "$path")"
    mv "$path" "$STASH_DIR/$path"
    echo "Stashed: $path"
  fi
done

# 結束時還原
restore() {
  for path in "${EXCLUDED[@]}"; do
    if [ -e "$STASH_DIR/$path" ]; then
      mkdir -p "$(dirname "$path")"
      mv "$STASH_DIR/$path" "$path"
      echo "Restored: $path"
    fi
  done
  rm -rf "$STASH_DIR"
}
trap restore EXIT INT TERM

# 跑 pygbag（額外參數透傳）
pygbag --width 1280 --height 720 "$@" main.py
