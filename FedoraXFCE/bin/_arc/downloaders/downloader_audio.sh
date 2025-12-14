#!/usr/bin/env bash
set -euo pipefail

# ==== Настройки ====
INPUT_FILE="./files.txt"
SRC_DIR="./src"
FFMPEG="ffmpeg"     # или путь к твоему ffmpeg
YTDLP="yt-dlp"

# ==== Проверка входных данных ====
[[ -f "$INPUT_FILE" ]] || { echo "❌ Нет файла $INPUT_FILE"; exit 1; }
mkdir -p "$SRC_DIR"

echo "📄 Список ссылок: $INPUT_FILE"
echo "📁 Папка для исходников: $SRC_DIR"
echo

# ==== Helpers ====
trim() { awk '{$1=$1; print}' <<<"$1"; }
safe_name_from_url() {
  local url="$1"
  if [[ "$url" =~ youtube\.com|youtu\.be ]]; then
    $YTDLP --get-id "$url" 2>/dev/null || echo "item_$(date +%s%3N)"
  else
    local clean="${url%%\?*}"
    local base="$(basename "$clean")"
    echo "${base%%.*}"
  fi
}

# ==== 1) Скачивание ====
echo "🔽 Скачиваем..."
n=1
while IFS= read -r raw; do
  url="$(trim "$raw")"
  [[ -z "$url" || "$url" =~ ^# ]] && continue

  printf "  [%02d] %s\n" "$n" "$url"
  name="$(safe_name_from_url "$url")"

  if [[ "$url" =~ youtube\.com|youtu\.be ]]; then
    $YTDLP -S "res:1080,fps" -o "${SRC_DIR}/${name}.%(ext)s" "$url"
  elif [[ "$url" == *.m3u8 || "$url" == *".m3u8?"* ]]; then
    $FFMPEG -y -hide_banner -loglevel error -i "$url" -c copy "${SRC_DIR}/${name}.ts"
  else
    $YTDLP -o "${SRC_DIR}/${name}.%(ext)s" "$url"
  fi

  ((n++))
done < "$INPUT_FILE"

echo "✅ Загрузка завершена."
echo

# ==== 2) Перекодирование в аудио ====
echo "🎧 Перекодируем в m4a..."
shopt -s nullglob
for f in "${SRC_DIR}"/*; do
  [[ -f "$f" ]] || continue
  base="$(basename "$f")"
  stem="${base%.*}"
  out="./${stem}.m4a"

  $FFMPEG -y -hide_banner -loglevel error \
    -i "$f" -vn -c:a aac -b:a 128k -movflags +faststart "$out"

  echo "  ✔ ${base} → $(basename "$out")"
done
shopt -u nullglob

echo
echo "🏁 Готово! Исходники в $SRC_DIR, аудио в текущей папке."
