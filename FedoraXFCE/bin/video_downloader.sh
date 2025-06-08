#!/bin/bash

# Paths
BASE_DIR="$HOME/video"
INPUT_FILE="$BASE_DIR/files.txt"
TEMP_DIR="$BASE_DIR/01_downloaded"
FFMPEG="$HOME/apps/ffmpeg/ffmpeg"

# Create directories and input file if they don't exist
mkdir -p "$TEMP_DIR" 
touch "$INPUT_FILE"

echo "📁 Working directories:"
echo " - Downloads: $TEMP_DIR"
echo " - Encoded slides: $SLIDES_DIR"
echo " - URL list file: $INPUT_FILE"
echo

exec 3< "$INPUT_FILE"  

COUNTER=1

pad_number() {
    printf "%03d" "$1"
}

while IFS= read -r url <&3; do
# while IFS= read -r url || [[ -n "$url" ]]; do
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

    echo "📦 Re-encoding for Telegram: slides and presentations"
    TYPE="02_slides"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    mkdir -p "$BASE_DIR/$TYPE/"
    "$FFMPEG" -y -i "$FILENAME" \
        -hide_banner \
        -nostats \
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
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -preset faster \
        -movflags +faststart \
        "$OUTPUT_PATH" < /dev/null
    echo "✅ Saved: $OUTPUT_PATH"
    ffprobe -i "$OUTPUT_PATH" -hide_banner
    echo
    echo

    echo "📦 Re-encoding for Telegram: high quality video for mobile devices"
    TYPE="03_mobile"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    mkdir -p "$BASE_DIR/$TYPE/"
    "$FFMPEG" -y -i "$FILENAME" \
        -hide_banner \
        -nostats \
        -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=20,scale=iw/2:ih/2:flags=lanczos" \
        -crf 23 \
        -c:v libx264 \
        -preset slow \
        -profile:v main \
        -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -movflags +faststart \
        "$OUTPUT_PATH" < /dev/null
    echo "✅ Saved: $OUTPUT_PATH"
    ffprobe -i "$OUTPUT_PATH" -hide_banner
    echo
    echo

    echo "📦 Re-encoding for Telegram: slides and presentations (/2 size)"
    TYPE="02_slides_x2"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    mkdir -p "$BASE_DIR/$TYPE/"
    "$FFMPEG" -y -i "$FILENAME" \
        -hide_banner \
        -nostats \
        -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=2,scale=iw/2:ih/2:flags=lanczos" \
        -crf 30 \
        -r 2 \
        -vcodec libx264 \
        -profile:v main \
        -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -preset faster \
        -movflags +faststart \
        "$OUTPUT_PATH" < /dev/null
    echo "✅ Saved: $OUTPUT_PATH"
    ffprobe -i "$OUTPUT_PATH" -hide_banner
    echo
    echo

    ((COUNTER++))

done < "$INPUT_FILE"

echo "🎉 All done! Encoded videos are in '$SLIDES_DIR'."
exec 3<&-
