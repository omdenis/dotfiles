#!/bin/bash

# Пути
BASE_DIR="$HOME/video"
INPUT_FILE="$BASE_DIR/files.txt"
TEMP_DIR="$BASE_DIR/01_downloaded"
SLIDES_DIR="$BASE_DIR/02_slides"
FFMPEG="$HOME/apps/ffmpeg-*-static/ffmpeg"

# Создание каталогов и файла
mkdir -p "$TEMP_DIR" "$SLIDES_DIR"
touch "$INPUT_FILE"

echo "📁 Рабочие директории:"
echo " - Скачанные: $TEMP_DIR"
echo " - Пережатые: $SLIDES_DIR"
echo " - Файл со ссылками: $INPUT_FILE"
echo

COUNTER=1

pad_number() {
    printf "%03d" "$1"
}

while IFS= read -r url || [[ -n "$url" ]]; do
    url="$(echo "$url" | xargs)"  # очистить от пробелов
    [[ -z "$url" || "$url" =~ ^# ]] && continue

    echo "➡️ Обрабатываем: $url"

    NUM=$(pad_number "$COUNTER")
    FILENAME=""
    SAFE_NAME=""

    if [[ "$url" =~ "youtube.com" || "$url" =~ "youtu.be" ]]; then
        echo "YouTube → yt-dlp"
        yt_id=$(yt-dlp --get-id "$url")
        SAFE_NAME="${yt_id}"
        yt-dlp -S "res:1080,fps" -o "$TEMP_DIR/${NUM}_${SAFE_NAME}.%(ext)s" "$url" 
        FILENAME=$(ls -t "$TEMP_DIR/${NUM}_${SAFE_NAME}."* | head -n1)

    elif [[ "$url" == *.m3u8 ]]; then
        echo ".m3u8 → ffmpeg"
        base=$(basename "$url")
        SAFE_NAME="${base%%.*}"
        FILENAME="$TEMP_DIR/${NUM}_${SAFE_NAME}.ts"
        ${FFMPEG} -y -i "$url" -c copy "${NUM}_$FILENAME"

    else
        echo "⚠️ Неизвестный формат URL: $url"
        continue
    fi

    OUTPUT_NAME="${NUM}_${SAFE_NAME}.mp4"
    OUTPUT_PATH="$SLIDES_DIR/$OUTPUT_NAME"

    echo "📦 Перекодируем для Telegram..."
    # ${FFMPEG} -hide_banner -y -i "$FILENAME" \
    #     -c:v libx264 -preset veryslow -crf 28 -g 300 -keyint_min 300 \
    #     -c:a aac -b:a 128k -movflags +faststart "$OUTPUT_PATH"

    echo "✅ Сохранено: $OUTPUT_PATH"
    echo

    ((COUNTER++))

done < "$INPUT_FILE"

echo "🎉 Всё завершено! Пережатые файлы ждут в '$OUTPUT_DIR'."
