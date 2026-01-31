#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Media Downloader Tool

This script scans the current directory for .txt files containing media URLs
(YouTube, m3u8, etc.) and downloads them using yt-dlp and ffmpeg.

Features:
- Scans current directory for .txt files with URLs
- Downloads media files using yt-dlp
- Each .txt file creates its own output directory (named after the .txt file)
- Files saved with numbered prefixes (001, 002, etc.)
- For YouTube: uses video title with underscores + video ID in filename
- For m3u8: uses m3u8 filename
- Automatically compresses videos to Telegram format (15fps, x2 smaller resolution)
- Compressed files saved to ./telegram_15fps_x2/ subdirectory

Usage:
    python downloader.py
    
Example:
    files.txt → downloads to ./files/ directory
              → compressed to ./files/telegram_15fps_x2/
    course.txt → downloads to ./course/ directory
               → compressed to ./course/telegram_15fps_x2/
    
Requirements:
    - yt-dlp installed in system
    - ffmpeg installed (custom path or system)
    - pip install curl-cffi
    - pip install --upgrade yt-dlp
"""

import sys
import re
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

# Configuration
FFMPEG_PATH = Path("~/apps/ffmpeg/ffmpeg").expanduser()
# Use yt-dlp as Python module to access venv dependencies (curl-cffi)
YTDLP_BIN = [sys.executable, "-m", "yt_dlp"]

def get_ffmpeg_command() -> str:
    """Get ffmpeg executable path (custom or system)"""
    if FFMPEG_PATH.exists():
        return str(FFMPEG_PATH)
    return "ffmpeg"

def get_ffprobe_command() -> str:
    """Get ffprobe executable path (custom or system)"""
    ffprobe_path = FFMPEG_PATH.parent / "ffprobe"
    if ffprobe_path.exists():
        return str(ffprobe_path)
    return "ffprobe"

def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS"""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size"""
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} GB"
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"

def print_media_info(filepath: Path, label: str = "File info"):
    """Print media file details using ffprobe"""
    ffprobe = get_ffprobe_command()
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(filepath),
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15
        )
        if result.returncode != 0:
            return

        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [])

        file_size = filepath.stat().st_size
        duration = float(fmt.get("duration", 0))
        bitrate = int(fmt.get("bit_rate", 0))

        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

        parts = [f"  [{label}]"]
        parts.append(f"  Size: {format_size(file_size)}")
        if duration > 0:
            parts.append(f"  Duration: {format_duration(duration)}")
        if bitrate > 0:
            parts.append(f"  Bitrate: {bitrate // 1000} kbps")
        if video:
            w = video.get("width", "?")
            h = video.get("height", "?")
            codec = video.get("codec_name", "?")
            fps_str = video.get("r_frame_rate", "")
            fps = ""
            if fps_str and "/" in fps_str:
                num, den = fps_str.split("/")
                try:
                    fps = f"{int(num) / int(den):.1f}"
                except (ValueError, ZeroDivisionError):
                    fps = fps_str
            parts.append(f"  Video: {w}x{h}, {codec}, {fps} fps")
        if audio:
            acodec = audio.get("codec_name", "?")
            sample_rate = audio.get("sample_rate", "?")
            channels = audio.get("channels", "?")
            parts.append(f"  Audio: {acodec}, {sample_rate} Hz, {channels}ch")

        print("\n".join(parts))
    except Exception:
        pass

def compress_to_telegram(src: Path, dst: Path) -> bool:
    """
    Re-encode to compact H.264 suitable for Telegram:
      - 15 fps
      - half resolution (scale by 0.5)
      - CRF 25, preset slow
      - mono 64k AAC audio
    
    Returns True if successful, False otherwise
    """
    # Scale filter that ensures even dimensions (required for H.264)
    # trunc(iw/4)*2 = divide by 2 and round down to nearest even number
    scale_filter = "scale=trunc(iw/4)*2:trunc(ih/4)*2:flags=lanczos"
    
    ffmpeg_cmd = get_ffmpeg_command()
    
    args = [
        ffmpeg_cmd,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",
        "-max_muxing_queue_size", "512",
        "-vf", scale_filter,
        "-r", "15",
        "-crf", "25",
        "-vcodec", "libx264", "-preset", "slow", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-b:a", "64k",  # Mono 64k AAC audio
        "-movflags", "+faststart",
        str(dst),
    ]
    
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        if result.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return True
        else:
            print(f"  [ERROR] Compression failed:")
            if result.stdout:
                print(result.stdout)
            return False
    except Exception as e:
        print(f"  [ERROR] Compression exception: {e}")
        return False

def check_dependencies():
    """Check if yt-dlp and ffmpeg are available"""
    # Check yt-dlp
    try:
        result = subprocess.run(
            YTDLP_BIN + ["--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"ERROR: yt-dlp not found")
            print("Install: pip install yt-dlp")
            return False
        
        # Show current version
        current_version = result.stdout.strip()
        print(f"  yt-dlp version: {current_version}")

        # Check for updates
        try:
            update_check = subprocess.run(
                YTDLP_BIN + ["--update-to", "stable", "--no-update"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            # Check if update is available by looking at stderr/stdout
            output = update_check.stdout + update_check.stderr
            if "already up to date" in output.lower() or "latest" in output.lower():
                print(f"  [OK] yt-dlp is up to date")
            elif "available" in output.lower() or "update" in output.lower():
                print(f"  [WARNING] yt-dlp update available! Run: sudo dnf upgrade --refresh yt-dlp")
            else:
                # Alternative check using -U --simulate
                update_check2 = subprocess.run(
                    YTDLP_BIN + ["-U"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10
                )
                output2 = update_check2.stdout + update_check2.stderr
                if "already" in output2.lower() and "latest" in output2.lower():
                    print(f"  [OK] yt-dlp is up to date")
                elif "updated" in output2.lower() or "restart" in output2.lower():
                    print(f"  [INFO] yt-dlp was just updated, restart may be needed")
                else:
                    print(f"  [INFO] Could not verify update status")
        except (subprocess.TimeoutExpired, Exception):
            print(f"  [INFO] Could not check for updates (timeout or error)")
            
    except FileNotFoundError:
        print(f"ERROR: {YTDLP_BIN} not found in PATH")
        print("Install: pip install yt-dlp")
        return False
    
    # Check ffmpeg (try custom path first, then system)
    ffmpeg_cmd = None
    if FFMPEG_PATH.exists():
        ffmpeg_cmd = str(FFMPEG_PATH)
    else:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                ffmpeg_cmd = "ffmpeg"
        except FileNotFoundError:
            pass
    
    if not ffmpeg_cmd:
        print(f"ERROR: ffmpeg not found")
        print(f"Checked: {FFMPEG_PATH} and system PATH")
        print("Install ffmpeg or update FFMPEG_PATH in script")
        return False
    
    return True

def find_txt_files(root: Path) -> list[Path]:
    """Find all .txt files in current directory"""
    files = []
    for p in sorted(root.iterdir()):
        if p.is_file() and p.suffix.lower() == ".txt":
            files.append(p)
    return files

def extract_urls_from_file(txt_file: Path) -> list[str]:
    """Extract URLs from text file (one URL per line)"""
    urls = []
    try:
        content = txt_file.read_text(encoding='utf-8')
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Basic URL validation
            if line.startswith('http://') or line.startswith('https://'):
                urls.append(line)
    except Exception as e:
        print(f"WARNING: Failed to read {txt_file.name}: {e}")
    return urls

def get_output_dir_for_txt(txt_file: Path) -> Path:
    """Get output directory based on .txt filename (without extension)"""
    dir_name = txt_file.stem  # filename without .txt extension
    return Path(".").resolve() / dir_name

def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL"""
    youtube_patterns = [
        'youtube.com',
        'youtu.be',
        'youtube-nocookie.com'
    ]
    return any(pattern in url.lower() for pattern in youtube_patterns)

def sanitize_filename(name: str, keep_spaces: bool = False) -> str:
    """Remove all non-alphanumeric characters from filename"""
    # Remove extension if present
    name = Path(name).stem
    # Keep only letters, numbers, and spaces
    name = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ\s]', '', name)
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    # Trim
    name = name.strip()
    # Replace spaces with underscores if requested, otherwise remove
    if keep_spaces:
        name = name.replace(' ', '_')
    else:
        name = name.replace(' ', '')
    return name

def get_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    # Patterns for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_title(url: str) -> str:
    """Get YouTube video title using yt-dlp"""
    try:
        cmd = YTDLP_BIN + [
            "--get-title",
            url
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None

def get_unique_filepath(base_path: Path) -> Path:
    """
    Get unique filepath by adding _1, _2, etc. if file exists
    Example: video.mp4 -> video_1.mp4 -> video_2.mp4
    """
    if not base_path.exists():
        return base_path
    
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

def get_filename_from_url(url: str, index: int) -> str:
    """
    Generate filename based on URL
    - YouTube: {index}_{sanitized_title_with_underscores}_{video_id}.mp4
    - m3u8: {index}_{sanitized_m3u8_name}.mp4
    """
    prefix = f"{index:03d}"
    
    if is_youtube_url(url):
        # Try to get YouTube title
        title = get_youtube_title(url)
        video_id = get_youtube_id(url)
        
        if title:
            # Keep spaces as underscores for readability
            sanitized = sanitize_filename(title, keep_spaces=True)
            if sanitized and video_id:
                return f"{prefix}_{sanitized}_{video_id}.mp4"
            elif sanitized:
                return f"{prefix}_{sanitized}.mp4"
        
        # Fallback with video ID if available
        if video_id:
            return f"{prefix}_youtube_video_{video_id}.mp4"
        return f"{prefix}_youtube_video.mp4"
    else:
        # Extract filename from URL
        parsed = urlparse(url)
        path = parsed.path
        filename = Path(path).stem
        sanitized = sanitize_filename(filename)
        if sanitized:
            return f"{prefix}_{sanitized}.mp4"
        return f"{prefix}_video.mp4"

def download_media(url: str, output_path: Path) -> bool:
    """
    Download media using yt-dlp
    Returns True if successful, False otherwise
    """
    # Determine ffmpeg command
    if FFMPEG_PATH.exists():
        ffmpeg_location = str(FFMPEG_PATH.parent)
    else:
        ffmpeg_location = None
    
    # Check for cookies.txt file in current directory
    cookies_file = Path("./cookies.txt")
    
    cmd = YTDLP_BIN + [
        "-o", str(output_path),
        "--no-check-certificates",  # Skip SSL certificate verification
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    # For YouTube URLs - use player clients that don't require JS runtime and ALWAYS use cookies
    if is_youtube_url(url):
        cmd.extend(["--extractor-args", "youtube:player_client=android,web"])
        # YouTube now requires cookies for most videos - add them first
        if cookies_file.exists():
            print(f"  [INFO] Using cookies from cookies.txt for YouTube")
            cmd.extend(["--cookies", str(cookies_file)])
        else:
            print(f"  [INFO] Using cookies from Chrome browser for YouTube")
            cmd.extend(["--cookies-from-browser", "chrome"])
    
    # For direct m3u8/asset URLs - use generic extractor with impersonation
    elif ".m3u8" in url.lower() or "/assets/" in url.lower():
        cmd.extend(["--force-generic-extractor"])
        cmd.extend(["--extractor-args", "generic:impersonate=chrome"])
        # Add cookies if file exists (non-YouTube)
        if cookies_file.exists():
            print(f"  [INFO] Using cookies from cookies.txt")
            cmd.extend(["--cookies", str(cookies_file)])
    else:
        # Add cookies if file exists (other URLs)
        if cookies_file.exists():
            print(f"  [INFO] Using cookies from cookies.txt")
            cmd.extend(["--cookies", str(cookies_file)])
    
    # Add referer for Udemy and similar sites
    if "udemy" in url.lower() or "wistia" in url.lower():
        cmd.extend(["--referer", "https://www.udemy.com/"])
    
    # Add ffmpeg location if custom path
    if ffmpeg_location:
        cmd.extend(["--ffmpeg-location", ffmpeg_location])
    
    cmd.append(url)
    
    try:
        print(f"\n> Downloading: {url}")
        print(f"  Output: {output_path.name}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        if result.returncode == 0:
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"  [OK] Downloaded successfully")
                return True
            else:
                print(f"  [ERROR] Output file missing or empty")
                if result.stdout:
                    print(f"\n--- yt-dlp output ---")
                    print(result.stdout)
                    print(f"--- end of output ---\n")
                return False
        else:
            # Check if error is sign-in required, 403 Forbidden, format not available, or JS runtime warning
            is_403_error = False
            is_js_runtime_error = False
            is_signin_required = False
            is_format_error = False
            if result.stdout:
                output_lower = result.stdout.lower()
                if "403" in output_lower and "forbidden" in output_lower:
                    is_403_error = True
                if "javascript runtime" in output_lower or "js runtime" in output_lower:
                    is_js_runtime_error = True
                if "sign in" in output_lower or "authentication" in output_lower:
                    is_signin_required = True
                if "requested format is not available" in output_lower or ("format" in output_lower and "not available" in output_lower):
                    is_format_error = True
            
            print(f"  [ERROR] Download failed (exit code: {result.returncode})")
            if result.stdout:
                print(f"\n--- yt-dlp error output ---")
                print(result.stdout)
                print(f"--- end of error output ---\n")
            
            # For YouTube format errors, try alternative strategies
            if is_youtube_url(url) and is_format_error:
                print(f"  [INFO] Format not available, trying alternative download methods...")
                return download_youtube_fallback(url, output_path, ffmpeg_location)
            
            # For YouTube sign-in errors, ensure we have cookies
            if is_youtube_url(url) and is_signin_required:
                if not cookies_file.exists():
                    print(f"  [INFO] Sign-in required, exporting cookies from browser...")
                    if export_cookies_from_browser():
                        print(f"  [INFO] Retrying download with exported cookies...")
                        return download_youtube_with_cookies(url, output_path, ffmpeg_location)
                    else:
                        print(f"  [ERROR] Could not export cookies. Please ensure you're signed in to YouTube in Chrome")
                        return False
                else:
                    print(f"  [ERROR] Sign-in required but cookies.txt exists. Cookies may be expired.")
                    print(f"  [INFO] Try deleting cookies.txt and re-running to export fresh cookies")
                    return False
            
            # Retry with alternative strategies for YouTube
            if is_youtube_url(url) and (is_403_error or is_js_runtime_error):
                print(f"  [INFO] Detected YouTube download issue, trying alternative methods...")
                return download_youtube_fallback(url, output_path, ffmpeg_location)
            
            # Retry with cookies if 403 error (non-YouTube)
            if is_403_error and not is_youtube_url(url):
                print(f"  [INFO] Detected 403 Forbidden error, retrying with cookies...")
                return download_media_with_cookies(url, output_path, ffmpeg_location)
            
            return False
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        return False

def export_cookies_from_browser() -> bool:
    """
    Export cookies from Chrome browser to cookies.txt file
    Returns True if successful, False otherwise
    """
    cookies_file = Path("./cookies.txt")
    
    print(f"\n  [INFO] Exporting cookies from Chrome to cookies.txt...")
    
    # Use yt-dlp to extract cookies from Chrome
    cmd = YTDLP_BIN + [
        "--cookies-from-browser", "chrome",
        "--cookies", str(cookies_file),
        "--no-download",
        "--simulate",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Dummy URL to trigger cookie export
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30
        )
        
        if cookies_file.exists() and cookies_file.stat().st_size > 0:
            print(f"  [OK] Cookies exported to: {cookies_file.absolute()}")
            return True
        else:
            print(f"  [WARNING] Could not export cookies")
            return False
            
    except Exception as e:
        print(f"  [WARNING] Failed to export cookies: {e}")
        return False

def download_media_with_cookies(url: str, output_path: Path, ffmpeg_location: str = None) -> bool:
    """
    Retry download with cookies for 403 errors
    """
    # Check for cookies.txt file in current directory
    cookies_file = Path("./cookies.txt")
    
    # Try to export cookies from browser if file doesn't exist
    if not cookies_file.exists():
        print(f"  [INFO] cookies.txt not found, attempting to export from browser...")
        export_cookies_from_browser()
    
    # Prepare command for retry
    cmd = YTDLP_BIN + [
        "-o", str(output_path),
        "--no-check-certificates",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    # For direct m3u8/asset URLs - use generic extractor with impersonation
    if ".m3u8" in url.lower() or "/assets/" in url.lower():
        cmd.extend(["--force-generic-extractor"])
        cmd.extend(["--extractor-args", "generic:impersonate=chrome"])
    
    # Add referer for Udemy and similar sites
    if "udemy" in url.lower() or "wistia" in url.lower():
        cmd.extend(["--referer", "https://www.udemy.com/"])
    
    # Add cookies from file if exists
    if cookies_file.exists():
        print(f"  [INFO] Using cookies.txt file")
        cmd.extend(["--cookies", str(cookies_file)])
    else:
        # Fallback to direct browser cookies
        print(f"  [INFO] Using cookies from Chrome browser")
        cmd.extend(["--cookies-from-browser", "chrome"])
    
    # Add ffmpeg location if custom path
    if ffmpeg_location:
        cmd.extend(["--ffmpeg-location", ffmpeg_location])
    
    cmd.append(url)
    
    print(f"  [INFO] Retrying download with cookies...")
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        if result.returncode == 0:
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"  [OK] Downloaded successfully with cookies")
                return True
            else:
                print(f"  [ERROR] Output file missing or empty (with cookies)")
                return False
        else:
            print(f"  [ERROR] Download failed even with cookies (exit code: {result.returncode})")
            if result.stdout:
                print(f"\n--- yt-dlp error output (with cookies) ---")
                print(result.stdout)
                print(f"--- end of error output ---\n")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Exception during retry with cookies: {e}")
        return False

def download_youtube_with_cookies(url: str, output_path: Path, ffmpeg_location: str = None) -> bool:
    """
    Download YouTube video with freshly exported cookies
    """
    cookies_file = Path("./cookies.txt")
    
    cmd = YTDLP_BIN + [
        "-o", str(output_path),
        "--no-check-certificates",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--extractor-args", "youtube:player_client=android,web",
    ]
    
    # Use cookies file if it exists, otherwise use browser cookies
    if cookies_file.exists():
        cmd.extend(["--cookies", str(cookies_file)])
    else:
        cmd.extend(["--cookies-from-browser", "chrome"])
    
    # Add ffmpeg location if custom path
    if ffmpeg_location:
        cmd.extend(["--ffmpeg-location", ffmpeg_location])
    
    cmd.append(url)
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            print(f"  [OK] Downloaded successfully with cookies")
            return True
        else:
            print(f"  [ERROR] Download failed with cookies")
            if result.stdout:
                print(f"\n--- yt-dlp error output ---")
                print(result.stdout)
                print(f"--- end of error output ---\n")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        return False

def download_youtube_fallback(url: str, output_path: Path, ffmpeg_location: str = None) -> bool:
    """
    Try alternative download strategies for YouTube videos
    """
    strategies = [
        # android + web with cookies (matches primary config)
        ("android+web + cookies", ["youtube:player_client=android,web"], True, "bestvideo*+bestaudio/best"),
        # android alone with cookies
        ("android + cookies", ["youtube:player_client=android"], True, "bestvideo*+bestaudio/best"),
        # android without cookies
        ("android (no cookies)", ["youtube:player_client=android"], False, "bestvideo*+bestaudio/best"),
        # web alone with cookies
        ("web + cookies", ["youtube:player_client=web"], True, "bestvideo*+bestaudio/best"),
        # Mobile web
        ("mweb + cookies", ["youtube:player_client=mweb"], True, "best"),
        # Media connect (TV)
        ("mediaconnect", ["youtube:player_client=mediaconnect"], False, "bestvideo*+bestaudio/best"),
        # android without format restriction (any quality)
        ("android (any quality)", ["youtube:player_client=android"], True, None),
    ]
    
    cookies_file = Path("./cookies.txt")
    
    for strategy_name, extractor_args, use_cookies, format_spec in strategies:
        print(f"  [INFO] Trying {strategy_name}...")
        
        cmd = YTDLP_BIN + [
            "-o", str(output_path),
            "--no-check-certificates",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        
        # Add format selection if specified
        if format_spec:
            cmd.extend(["-f", format_spec])
        
        # Add all extractor args
        for arg in extractor_args:
            cmd.extend(["--extractor-args", arg])
        
        # Add cookies only if strategy requires them
        if use_cookies:
            if cookies_file.exists():
                cmd.extend(["--cookies", str(cookies_file)])
            else:
                cmd.extend(["--cookies-from-browser", "chrome"])
        
        # Add ffmpeg location if custom path
        if ffmpeg_location:
            cmd.extend(["--ffmpeg-location", ffmpeg_location])
        
        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                print(f"  [OK] Downloaded successfully using {strategy_name}")
                return True
            else:
                # Check for specific error messages
                if result.stdout:
                    output_lower = result.stdout.lower()
                    
                    # Show abbreviated error for failed attempts
                    lines = result.stdout.strip().split('\n')
                    error_lines = [l for l in lines if 'ERROR' in l.upper()]
                    if error_lines:
                        print(f"  [FAILED] {strategy_name}: {error_lines[-1][:80]}")
                
        except Exception as e:
            print(f"  [FAILED] {strategy_name}: {e}")
            continue
    
    print(f"  [ERROR] All YouTube download strategies failed")
    return False

def main():
    print("="*60)
    print("Media Downloader Tool")
    print("="*60)
    
    # Check dependencies
    print("\nChecking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("[OK] All dependencies available")
    
    # Check for cookies.txt and try to create if missing
    cookies_file = Path("./cookies.txt")
    if not cookies_file.exists():
        print("\n[INFO] cookies.txt not found, attempting to export from Chrome...")
        if export_cookies_from_browser():
            print("[OK] Cookies exported successfully")
        else:
            print("[WARNING] Could not export cookies, will use browser cookies directly if needed")
    else:
        print(f"\n[OK] Found cookies.txt ({cookies_file.stat().st_size} bytes)")
    
    # Find .txt files
    root = Path(".").resolve()
    txt_files = find_txt_files(root)
    
    if not txt_files:
        print("\nNo .txt files found in current directory")
        sys.exit(0)
    
    print(f"\nFound {len(txt_files)} .txt file(s):")
    for txt_file in txt_files:
        print(f"  - {txt_file.name}")
    
    # Process each .txt file separately
    total_success = 0
    total_fail = 0
    
    for txt_file in txt_files:
        print("\n" + "="*60)
        print(f"Processing: {txt_file.name}")
        print("="*60)
        
        # Extract URLs from this file
        urls = extract_urls_from_file(txt_file)
        
        if not urls:
            print(f"No URLs found in {txt_file.name}, skipping...")
            continue
        
        print(f"Found {len(urls)} URL(s)")
        
        # Create output directory based on .txt filename
        output_dir = get_output_dir_for_txt(txt_file)
        output_dir.mkdir(exist_ok=True)
        print(f"Output directory: {output_dir.name}/")
        
        # Create compressed output directory
        compressed_dir = output_dir / "telegram_15fps_x2"
        compressed_dir.mkdir(exist_ok=True)
        
        # Download each URL
        success_count = 0
        fail_count = 0
        
        for index, url in enumerate(urls, start=1):
            # Generate filename
            filename = get_filename_from_url(url, index)
            output_path = output_dir / filename
            
            # Check if file exists and get unique path
            if output_path.exists():
                unique_path = get_unique_filepath(output_path)
                print(f"\n[{index}/{len(urls)}] File exists, using: {unique_path.name}")
                output_path = unique_path
            else:
                print(f"\n[{index}/{len(urls)}]")
            
            # Download media
            if download_media(url, output_path):
                print_media_info(output_path, "Original")
                # Compress video to Telegram format
                compressed_path = compressed_dir / output_path.name
                print(f"  [INFO] Compressing to Telegram format (15fps, x2)...")

                if compress_to_telegram(output_path, compressed_path):
                    print(f"  [OK] Compressed: {compressed_path.name}")
                    print_media_info(compressed_path, "Compressed")
                    success_count += 1
                else:
                    print(f"  [WARNING] Compression failed, but original file saved")
                    success_count += 1
            else:
                fail_count += 1
        
        # File summary
        print(f"\n{txt_file.name} - Downloaded: {success_count}, Failed: {fail_count}")
        total_success += success_count
        total_fail += fail_count
    
    # Final summary
    print("\n" + "="*60)
    print("Final Summary")
    print("="*60)
    print(f"Total files processed: {len(txt_files)}")
    print(f"Total successful downloads: {total_success}")
    print(f"Total failed downloads: {total_fail}")
    print("="*60)

if __name__ == "__main__":
    main()
