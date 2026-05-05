#!/usr/bin/env bash
# 把 assets/sfx/ 下的 WAV 全部轉成 OGG（Vorbis q:a 4，約 128kbps，體積大幅下降）
# 用法：bash scripts/convert_audio.sh
#
# 需要：ffmpeg（macOS: brew install ffmpeg）
#
# 轉完會：
#   1. 在原處產生 .ogg
#   2. 把舊 .wav 移到 assets/sfx/_old_wav/（不刪除，保險起見）
#   3. 列出新舊檔案大小對照

set -euo pipefail

SFX_DIR="assets/sfx"
BACKUP_DIR="$SFX_DIR/_old_wav"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg not found. Install with: brew install ffmpeg"
  exit 1
fi

# 偵測可用的 vorbis encoder
ENCODER=""
EXTRA_FLAGS=""
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q '\blibvorbis\b'; then
  ENCODER="libvorbis"
elif ffmpeg -hide_banner -encoders 2>/dev/null | grep -q '^ A....D vorbis '; then
  ENCODER="vorbis"
  EXTRA_FLAGS="-strict experimental"
else
  echo "ERROR: ffmpeg has no vorbis encoder."
  echo "Try: brew reinstall ffmpeg"
  exit 1
fi
echo "Using encoder: $ENCODER"

if [ ! -d "$SFX_DIR" ]; then
  echo "ERROR: $SFX_DIR not found. Run from project root."
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Converting WAV -> OGG ..."
echo

shopt -s nullglob nocaseglob
for wav in "$SFX_DIR"/*.wav; do
  base=$(basename "$wav" .wav)
  # 統一用小寫檔名輸出
  base_lc=$(echo "$base" | tr '[:upper:]' '[:lower:]')
  ogg="$SFX_DIR/${base_lc}.ogg"

  # BGM 用較高品質、較大壓縮；短音效用低品質保留清晰度
  if [[ "$base_lc" == bgmusic_* ]]; then
    quality="3"   # ~112 kbps，BGM 夠用
  else
    quality="5"   # ~160 kbps，短音效保留銳利度
  fi

  ffmpeg -y -loglevel error -i "$wav" -c:a "$ENCODER" $EXTRA_FLAGS -q:a "$quality" "$ogg"

  old_size=$(stat -f%z "$wav" 2>/dev/null || stat -c%s "$wav")
  new_size=$(stat -f%z "$ogg" 2>/dev/null || stat -c%s "$ogg")
  pct=$(( (new_size * 100) / old_size ))

  printf "  %-40s %8d B -> %8d B (%2d%%)\n" \
    "$base.wav -> ${base_lc}.ogg" "$old_size" "$new_size" "$pct"

  mv "$wav" "$BACKUP_DIR/$(basename "$wav")"
done

echo
echo "Done. Old WAVs backed up to $BACKUP_DIR/"
echo "If everything works, you can delete that folder to free disk."
