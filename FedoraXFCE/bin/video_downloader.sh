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

get_safe_name_from_url() {
    local url="$1"
    local name=""

    if [[ "$url" =~ "youtube.com" || "$url" =~ "youtu.be" ]]; then
        name=$(yt-dlp --get-id "$url" 2>/dev/null)
    else
        # remove query params
        local clean_url="${url%%\?*}"
        local base=$(basename "$clean_url")
        name="${base%%.*}"
    fi

    # fallback if name is empty
    if [[ -z "$name" ]]; then
        name="unknown_$(date +%s)"
    fi

    echo "$name"
}

merge_media_files() {
    local DIR="$1"
    local FFMPEG="$HOME/apps/ffmpeg/ffmpeg"

    [[ ! -d "$DIR" ]] && echo "❌ Directory does not exist: $DIR" && return 1

    local BASENAME=$(basename "$DIR")
    local PARENT=$(dirname "$DIR")
    local OUTPUT_FILE
    local TMP_LIST="$DIR/concat_list.txt"
    mkdir -p "$PARENT/09_results"

    local TYPE=""
    local FIRST_FILE=$(find "$DIR" -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.ts" -o -iname "*.m4a" -o -iname "*.mp3" \) | head -n 1)

    [[ -z "$FIRST_FILE" ]] && echo "⚠️ No supported media files found." && return 1

    local EXT="${FIRST_FILE##*.}"
    case "$EXT" in
        mp4|mov|mkv|ts)
            TYPE="video"
            OUTPUT_FILE="$PARENT/09_results/${BASENAME}_joined.mp4"
            ;;
        m4a|mp3)
            TYPE="audio"
            OUTPUT_FILE="$PARENT/09_results/${BASENAME}_joined.${EXT}"
            ;;
        *)
            echo "⚠️ Unsupported file type: $EXT"
            return 1
            ;;
    esac

    > "$TMP_LIST"
    find "$DIR" -type f -iname "*.${EXT}" | sort | while read -r f; do
        echo "file '$f'" >> "$TMP_LIST"
    done

    [[ ! -s "$TMP_LIST" ]] && echo "⚠️ Nothing to merge." && return 1

    "$FFMPEG" -y -hide_banner -loglevel error \
        -f concat -safe 0 -i "$TMP_LIST" -c copy "$OUTPUT_FILE"

    rm -f "$TMP_LIST"

    print_file_info "📦" "$OUTPUT_FILE"
}


validate_file() {
    local file="$1"

    # Проверка: существует и не пустой
    if [[ ! -f "$file" || ! -s "$file" ]]; then
        echo "⚠️  Skipped: File not found or empty → $file"
        return 1
    fi

    # Проверка: можно ли считать duration
    if ! ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$file" > /dev/null; then
        echo "⚠️  Skipped: File not valid media or corrupted → $file"
        return 1
    fi

    return 0
}

print_file_info() {
    local format="$1"
    local file="$2"

    # === MEDIA TYPE: audio-only?
    ext=$(basename "$file" | awk -F. '{print tolower($NF)}')
    if [[ "$ext" == "mp3" || "$ext" == "m4a" || "$ext" == "aac" || "$ext" == "flac" || "$ext" == "wav" ]]; then
        is_audio_only=true
    else
        is_audio_only=false
    fi
    
    # === File size ===
    filesize_bytes=$(stat -c%s "$file" 2>/dev/null)
    filesize_mb=$(awk "BEGIN {printf \"%.1f\", $filesize_bytes / 1024 / 1024}")

    # === VIDEO ===
    if ! $is_audio_only; then
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
    fi

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

    if ! $is_audio_only; then
        [[ "$vbitrate" =~ ^[0-9]+$ ]] && vbitrate_kbps=$((vbitrate / 1000)) || vbitrate_kbps="?"
    fi
    [[ "$abitrate" =~ ^[0-9]+$ ]] && abitrate_kbps=$((abitrate / 1000)) || abitrate_kbps="?"

    case "$channels" in
        1) achan="mono" ;;
        2) achan="stereo" ;;
        *) achan="${channels}ch" ;;
    esac

    # === Output ===
    echo
    echo "$format ${filesize_mb} MB "
    echo "$file"
    if ! $is_audio_only; then
        echo "Video: $vcodec, ${width}x${height}, fps=${fps_val}, ${vbitrate_kbps} kbps"
    fi
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
    SAFE_NAME=$(get_safe_name_from_url "$url")
    FILENAME=""

    if [[ "$url" =~ "youtube.com" || "$url" =~ "youtu.be" || "$url" == *playlist* || "$url" == *mp4* ]]; then
        yt-dlp -S "res:1080,fps" -o "$TEMP_DIR/${NUM}_${SAFE_NAME}.%(ext)s" "$url"
        FILENAME=$(ls -t "$TEMP_DIR/${NUM}_${SAFE_NAME}."* | head -n1)
    elif [[ "$url" == *.m3u8 || "$url" == *".m3u8?"* ]]; then
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
echo
for FILE in "$TEMP_DIR"/*; do
    [[ ! -f "$FILE" ]] && continue

    SAFE_NAME=$(basename "$FILE")
    SAFE_NAME="${SAFE_NAME%.*}"
    OUTPUT_NAME="${SAFE_NAME}.mp4"

    print_file_info "📌 [ORIGINAL]" "$FILE"    
    validate_file "$FILE"
    
    # === Encode 2: Mobile HQ ===
    TYPE="03_mobile"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -vf "fps=20,scale=if(gte(iw\,2)\,iw/2\,iw/2+1):if(gte(ih\,2)\,ih/2\,ih/2+1),scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos" \
        -crf 23 \
        -vcodec libx264 -preset slow -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null    
    print_file_info "📦 [Mobile HQ]" "$OUTPUT_PATH"
    
    # === Encode 1: Slides full ===
    TYPE="02_slides"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -vf "fps=2" \
        -crf 30 -r 2 \
        -vcodec libx264 -preset faster -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null
    print_file_info "📦 [Slides]" "$OUTPUT_PATH"

    # === Encode 3: Slides x2 ===
    TYPE="02_slides_half"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"    
    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 4 \
        -map_metadata -1 \
        -max_muxing_queue_size 512 \
        -vf "fps=2,scale=if(gte(iw\,2)\,iw/2\,iw/2+1):if(gte(ih\,2)\,ih/2\,ih/2+1),scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos" \
        -crf 30 -r 2 \
        -vcodec libx264 -preset faster -profile:v main -pix_fmt yuv420p \
        -c:a aac -ac 1 -b:a 64k \
        -tune stillimage \
        -movflags +faststart "$OUTPUT_PATH" < /dev/null    
    print_file_info "📦 [Slides, ½ size]" "$OUTPUT_PATH"

     # === Encode 4: Audio (mp3) ===
    TYPE="04_audio"
    mkdir -p "$BASE_DIR/$TYPE/"
    OUTPUT_PATH="$BASE_DIR/$TYPE/$OUTPUT_NAME"    
    OUTPUT_PATH="$BASE_DIR/$TYPE/${SAFE_NAME}.m4a"

    "$FFMPEG" -y -i "$FILE" \
        -hide_banner -nostats -loglevel error \
        -threads 2 \
        -map_metadata -1 \
        -vn \
        -c:a aac -ac 1 -b:a 64k \
        "$OUTPUT_PATH" < /dev/null
    print_file_info "🎧 [Audio only]" "$OUTPUT_PATH"

done

merge_media_files "$BASE_DIR/01_downloaded"
merge_media_files "$BASE_DIR/02_slides"
merge_media_files "$BASE_DIR/02_slides_half"
merge_media_files "$BASE_DIR/03_mobile"
merge_media_files "$BASE_DIR/04_audio"

echo "🎉 All encoding complete! 🎉"
echo
