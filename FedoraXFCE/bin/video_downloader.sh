#!/bin/bash

# Paths
BASE_DIR="$HOME/video"
INPUT_FILE="$BASE_DIR/files.txt"
TEMP_DIR="$BASE_DIR/01_downloaded"
SLIDES_DIR="$BASE_DIR/02_slides"
FFMPEG="$HOME/apps/ffmpeg/ffmpeg"

# Create directories and input file if they don't exist
mkdir -p "$TEMP_DIR" "$SLIDES_DIR"
touch "$INPUT_FILE"

echo "📁 Working directories:"
echo " - Downloads: $TEMP_DIR"
echo " - Encoded slides: $SLIDES_DIR"
echo " - URL list file: $INPUT_FILE"
echo

COUNTER=1

pad_number() {
    printf "%03d" "$1"
}

while IFS= read -r url || [[ -n "$url" ]]; do
    url="$(echo "$url" | xargs)"  # trim leading/trailing whitespace
    [[ -z "$url" || "$url" =~ ^# ]] && continue  # skip empty lines or comments

    echo "➡️ Processing: $url"

    NUM=$(pad_number "$COUNTER")
    FILENAME=""
    SAFE_NAME=""

    if [[ "$url" =~ "youtube.com" || "$url" =~ "youtu.be" ]]; then
        echo "🎥 YouTube → yt-dlp"
        yt_id=$(yt-dlp --get-id "$url")
        SAFE_NAME="${yt_id}"
        yt-dlp -S "res:1080,fps" -o "$TEMP_DIR/${NUM}_${SAFE_NAME}.%(ext)s" "$url"
        FILENAME=$(ls -t "$TEMP_DIR/${NUM}_${SAFE_NAME}."* | head -n1)

    elif [[ "$url" == *.m3u8 ]]; then
        echo "🌐 .m3u8 → ffmpeg"
        base=$(basename "$url")
        SAFE_NAME="${base%%.*}"
        FILENAME="$TEMP_DIR/${NUM}_${SAFE_NAME}.ts"
        ${FFMPEG} -y -i "$url" -c copy "${NUM}_$FILENAME"

    else
        echo "⚠️ Unsupported URL format: $url"
        continue
    fi

    OUTPUT_NAME="${NUM}_${SAFE_NAME}.mp4"
    OUTPUT_PATH="$SLIDES_DIR/$OUTPUT_NAME"

    echo "📦 Re-encoding for Telegram..."
    "$FFMPEG" -y -i "$FILENAME" \
        -hide_banner \
        -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=2,crop=iw:ih-0:0:0,scale=iw/1:-2" \
        -crf 30 \
        -r 2 \
        -vcodec libx264 \
        -profile:v main \
        -pix_fmt yuv420p \
        -c:a aac -b:a 64k -ac 1 \
        -tune stillimage \
        -preset faster \
        -movflags +faststart \
        "$OUTPUT_PATH" < /dev/null

    echo "✅ Saved: $OUTPUT_PATH"
    echo

    ((COUNTER++))

done < "$INPUT_FILE"

echo "🎉 All done! Encoded videos are in '$SLIDES_DIR'."
