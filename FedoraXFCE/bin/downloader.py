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
- For YouTube: uses video title in filename
- For m3u8: uses m3u8 filename
- Sanitizes filenames (only letters and numbers)

Usage:
    python downloader.py
    
Example:
    files.txt → downloads to ./files/ directory
    course.txt → downloads to ./course/ directory
    
Requirements:
    - yt-dlp installed in system
    - ffmpeg installed (custom path or system)
"""

import sys
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

# Configuration
FFMPEG_PATH = Path("~/apps/ffmpeg/ffmpeg").expanduser()
YTDLP_BIN = "yt-dlp"

def check_dependencies():
    """Check if yt-dlp and ffmpeg are available"""
    # Check yt-dlp
    try:
        result = subprocess.run(
            [YTDLP_BIN, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"ERROR: {YTDLP_BIN} not found in PATH")
            print("Install: pip install yt-dlp")
            return False
        
        # Show current version
        current_version = result.stdout.strip()
        print(f"  yt-dlp version: {current_version}")
        
        # Check for updates
        try:
            update_check = subprocess.run(
                [YTDLP_BIN, "--update-to", "stable", "--no-update"],
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
                    [YTDLP_BIN, "-U"],
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

def sanitize_filename(name: str) -> str:
    """Remove all non-alphanumeric characters from filename"""
    # Remove extension if present
    name = Path(name).stem
    # Keep only letters, numbers, and spaces
    name = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ\s]', '', name)
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    # Trim and remove spaces
    name = name.strip().replace(' ', '')
    return name

def get_youtube_title(url: str) -> str:
    """Get YouTube video title using yt-dlp"""
    try:
        cmd = [
            YTDLP_BIN,
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

def get_filename_from_url(url: str, index: int) -> str:
    """
    Generate filename based on URL
    - YouTube: {index}_{sanitized_title}.mp4
    - m3u8: {index}_{sanitized_m3u8_name}.mp4
    """
    prefix = f"{index:03d}"
    
    if is_youtube_url(url):
        # Try to get YouTube title
        title = get_youtube_title(url)
        if title:
            sanitized = sanitize_filename(title)
            if sanitized:
                return f"{prefix}_{sanitized}.mp4"
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
    
    cmd = [
        YTDLP_BIN,
        "-o", str(output_path),
        url
    ]
    
    # Add ffmpeg location if custom path
    if ffmpeg_location:
        cmd.extend(["--ffmpeg-location", ffmpeg_location])
    
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
                return False
        else:
            print(f"  [ERROR] Download failed")
            if result.stdout:
                print(f"  Details: {result.stdout[:200]}")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
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
        
        # Download each URL
        success_count = 0
        fail_count = 0
        
        for index, url in enumerate(urls, start=1):
            # Generate filename
            filename = get_filename_from_url(url, index)
            output_path = output_dir / filename
            
            # Skip if already exists
            if output_path.exists():
                print(f"\n[{index}/{len(urls)}] Skipping (already exists): {filename}")
                success_count += 1
                continue
            
            print(f"\n[{index}/{len(urls)}]")
            if download_media(url, output_path):
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
