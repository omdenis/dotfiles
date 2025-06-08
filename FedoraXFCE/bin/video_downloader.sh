#!/bin/bash

# === Paths ===
BASE_DIR="$HOME/video"
INPUT_FILE="$BASE_DIR/files.txt"
TEMP_DIR="$BASE_DIR/01_downloaded"
FFMPEG="$HOME/apps/ffmpeg/ffmpeg"

# === Init ===
mkdir -p "$TEMP_DIR"
touch "$INPUT_FILE"

echo "📁 Working directories:"
echo " - Downloads: $TEMP_DIR"
echo " - URL list file: $INPUT_FILE"
echo

pad_number() {
    printf "%03d" "$1"
}

print_file_info() {
    local file="$1"

    # === VIDEO ===
    vcodec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    width=$(ffprobe -v error -select_streams v:0 -show_entries stream=width \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    height=$(ffprobe -v error -select_streams v:0 -show_entries stream=height \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    fps_raw=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    vbitrate=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    # === AUDIO ===
    acodec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    arate=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    channels=$(ffprobe -v error -select_streams a:0 -show_entries stream=channels \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    abitrate=$(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate \
        -of default=noprint_wrappers=1:nokey=1 "$file")

    # === DURATION ===
    duration=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$file" | awk '{printf "%.1f", $1}')

    min=$(awk "BEGIN {printf \"%d\", $duration/60}")
    sec=$(awk "BEGIN {printf \"%02d\", $duration%60}")
    duration_fmt="${min}:${sec}"

    # === Format ===
    IFS="/" read -r num den <<< "$fps_raw"
    if [[ "$den" -eq 0 || -z "$den" ]]; then
        fps_val="?"
    else
        fps_val=$(awk "BEGIN {printf \"%.2f\", $num/$den}")
    fi

    [[ "$vbitrate" =~ ^[0-9]+$ ]] && vbitrate_kbps=$((vbitrate / 1000)) || vbitrate_kbps="?"
    [[ "$abitrate" =~ ^[0-9]+$ ]] && abitrate_kbps=$((abitrate / 1000)) || abitrate_kbps="?"

    case "$channels" in
        1) achan="mono" ;;
        2) achan="stereo" ;;
        *) achan="${channels}ch" ;;
    esac

    # === Output ===
    echo "$OUTPUT_PATH"
    echo "Video: $vcodec, ${width}x${height}, fps=${fps_val}, ${vbitrate_kbps} kbps"
    echo "Audio: $acodec, $achan, ${arate} Hz, ${abitrate_kbps} kbps"
    echo "Duration: $duration_fmt (${duration}s)"
    echo
}


# === STEP 1: DOWNLOAD ===
echo "🔽 Step 1: Downloading all files..."
echo
exec 3< "$INPUT_FILE"
COUNTER=1
while IFS= read -r url <&3; do
    url="$(echo "$url" | xargs)"
    [[ -z "$url" || "$url" =~ ^# ]] && continue

    echo "➡️  Downloading: $url"
    NUM=$(pad_number "$COUNTER")
    SAFE_NAME=""
    FILENAME=""

    if [[ "$url" =~ "youtube.com" || "$url" =~ "youtu.be" ]]; then
        yt_id=$(yt-dlp --get-id "$url")
        SAFE_NAME="${yt_id}"
        yt-dlp -S "res:1080,fps" -o "$TEMP_DIR/${NUM}_${SAFE_NAME}.%(ext)s" "$url"
    elif [[ "$url" == *.m3u8 ]]; then
        base=$(basename "$url")
        SAFE_NAME="${base%%.*}"
        FILENAME="$TEMP_DIR/${NUM}_${SAFE_NAME}.ts"
        "$FFMPEG" -y -i "$url" -c copy "$FILENAME"
    else
        echo "⚠️  Unsupported URL: $url"
        continue
    fi

    echo
    echo

    ((COUNTER++))
done < "$INPUT_FILE"

exec 3<&-
echo "✅ Downloads complete!"
echo
echo
echo

# === STEP 2: ENCODE ===
echo "🎬 Step 2: Encoding all downloaded files..."
for FILE in "$TEMP_DIR"/*; do
    [[ ! -f "$FILE" ]] && continue

    SAFE_NAME=$(basename "$FILE")
    SAFE_NAME="${SAFE_NAME%.*}"
    OUTPUT_NAME="${SAFE_NAME}.mp4"

    echo "📌 [ORIGINAL]"
    print_file_info "$FILE"    

    # === Encode 1: Slides full ===
    TYPE="02_slides"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    echo "📦 [Slides]"
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=2,crop=iw:ih-0:0:0,scale=iw/1:-2" \
        -crf 30 -r 2 \
        -vcodec libx264 -preset faster -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null
    print_file_info "$OUTPUT_PATH"        

    # === Encode 2: Mobile HQ ===
    TYPE="03_mobile"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    echo "📦 [Mobile HQ]"
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=20,scale=iw/2:ih/2:flags=lanczos" \
        -crf 23 \
        -vcodec libx264 -preset slow -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null    
    print_file_info "$OUTPUT_PATH"

    # === Encode 3: Slides x2 ===
    TYPE="02_slides_half"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    echo "📦 [Slides, ½ size]"
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -filter:v "fps=2,scale=iw/2:ih/2:flags=lanczos" \
        -crf 30 -r 2 \
        -vcodec libx264 -preset faster -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null    
    print_file_info "$OUTPUT_PATH"

    ((COUNTER++))
done

echo "🎉 All encoding complete! 🎉"
echo
