#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper Transcription Tool

This script scans the current directory for audio/video files and provides
an interactive menu to select which files to transcribe using OpenAI's Whisper.

Features:
- Scans current directory for media files (audio/video)
- Interactive menu with file selection (0 for all, or specific numbers)
- Shows which files are already transcribed
- Outputs text files to ./out directory
- Supports multiple audio/video formats

Usage:
    python transcribe.py
    
Requirements:
    pip install openai-whisper
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import timedelta

# Supported audio and video formats
AUDIO_EXTS = {
    ".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".oga", ".wma", 
    ".aif", ".aiff", ".opus", ".webm"
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".wmv", ".flv", 
    ".mts", ".m2ts", ".3gp", ".mpeg", ".mpg", ".ts"
}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

def check_whisper():
    """Check if whisper is installed in the system"""
    try:
        result = subprocess.run(
            ["whisper", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False

def find_media_files(root: Path) -> list[Path]:
    """Find all media files in the current directory"""
    files = []
    for p in sorted(root.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in MEDIA_EXTS:
            files.append(p)
    return files

def file_already_transcribed(media_file: Path, output_dir: Path) -> bool:
    """Check if the file has already been transcribed"""
    txt_file = output_dir / f"{media_file.stem}.txt"
    return txt_file.exists()

def transcribe_file(
    media_file: Path, 
    output_dir: Path,
    model: str = "turbo",
    language: str = "en"
) -> tuple[bool, dict]:
    """
    Transcribe a single file using Whisper
    Returns (success: bool, stats: dict with processing info)
    """
    # Get file size
    file_size_bytes = media_file.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    print(f"\n🎙️  Transcribing: {media_file.name}")
    print(f"    📦 Size: {file_size_mb:.2f} MB")
    
    # Start timer
    start_time = time.time()
    
    cmd = [
        "whisper",
        str(media_file),
        "--model", model,
        "--language", language,
        "--output_format", "txt",
        "--output_dir", str(output_dir)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Calculate duration
        duration = time.time() - start_time
        
        stats = {
            "file_name": media_file.name,
            "file_size_mb": file_size_mb,
            "duration_seconds": duration,
            "success": False,
            "char_count": 0,
            "word_count": 0,
            "line_count": 0
        }
        
        if result.returncode == 0:
            # Read the output file to get statistics
            output_file = output_dir / f"{media_file.stem}.txt"
            if output_file.exists():
                content = output_file.read_text(encoding='utf-8')
                stats["char_count"] = len(content)
                stats["word_count"] = len(content.split())
                stats["line_count"] = len(content.splitlines())
                stats["success"] = True
                
                print(f"    ⏱️  Time: {timedelta(seconds=int(duration))}")
                print(f"    ✅ Done: {media_file.stem}.txt")
                print(f"    📊 Stats: {stats['char_count']:,} chars, {stats['word_count']:,} words, {stats['line_count']} lines")
            else:
                print(f"    ❌ Output file not found")
            return True, stats
        else:
            print(f"    ❌ Error: {result.stderr.strip()}")
            return False, stats
    except Exception as e:
        duration = time.time() - start_time
        stats = {
            "file_name": media_file.name,
            "file_size_mb": file_size_mb,
            "duration_seconds": duration,
            "success": False,
            "char_count": 0,
            "word_count": 0,
            "line_count": 0
        }
        print(f"    ❌ Exception: {e}")
        return False, stats

def show_file_menu(files: list[Path], output_dir: Path) -> list[int]:
    """
    Show file selection menu for transcription
    Returns list of selected file indices
    """
    print("\n" + "="*60)
    print("🎬 Whisper Transcription Tool")
    print("="*60)
    print("0) All files")
    
    for idx, file in enumerate(files, start=1):
        status = "✓" if file_already_transcribed(file, output_dir) else " "
        print(f"{idx}) [{status}] {file.name}")
    
    print("="*60)
    print("Enter numbers separated by space (e.g.: 1 3 5) or 0 for all")
    print("Press Enter without input to exit")
    
    while True:
        try:
            choice = input("\nChoice: ").strip()
            
            if not choice:
                return []
            
            if choice == "0":
                return list(range(len(files)))
            
            # Parse list of numbers
            selected = []
            for num in choice.split():
                try:
                    idx = int(num) - 1
                    if 0 <= idx < len(files):
                        selected.append(idx)
                    else:
                        print(f"❌ Number {num} out of range")
                except ValueError:
                    print(f"❌ '{num}' is not a number")
            
            if selected:
                return selected
            else:
                print("❌ No files selected. Try again.")
                
        except (EOFError, KeyboardInterrupt):
            print("\n\n❌ Cancelled by user")
            return []

def get_output_directory(root: Path) -> Path:
    """
    Get output directory from OBSIDIAN_PATH environment variable or use default ./out
    Shows configuration hint if OBSIDIAN_PATH is not set
    """
    obsidian_path = os.getenv("OBSIDIAN_PATH")
    
    if obsidian_path:
        output_dir = Path(obsidian_path).expanduser().resolve()
        print(f"📁 Using OBSIDIAN_PATH: {output_dir}")
    else:
        output_dir = root / "out"
        print("\n" + "ℹ️  " + "="*58)
        print("💡 Tip: You can configure a custom output directory")
        print("   Set OBSIDIAN_PATH environment variable:")
        print()
        print("   # Add to ~/.bashrc:")
        print('   export OBSIDIAN_PATH="$HOME/Documents/Obsidian/Transcripts"')
        print()
        print("   # Then reload:")
        print("   source ~/.bashrc")
        print("="*60)
        print(f"📁 Using default output: {output_dir}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def main():
    # Check if whisper is installed
    if not check_whisper():
        print("❌ Whisper not found in the system!")
        print("Install it: pip install openai-whisper")
        sys.exit(1)
    
    # Current directory
    root = Path(".").resolve()
    
    # Output directory (from OBSIDIAN_PATH or default ./out)
    output_dir = get_output_directory(root)
    
    # Find all media files
    media_files = find_media_files(root)
    
    if not media_files:
        print("🤷 No media files found in current directory")
        sys.exit(0)
    
    # Show menu and get selection
    selected_indices = show_file_menu(media_files, output_dir)
    
    if not selected_indices:
        print("\n👋 Exit")
        sys.exit(0)
    
    # Transcription settings
    model = "turbo"  # can be changed to "base", "small", "medium", "large"
    language = "en"  # can be changed to "ru", "auto", etc.
    
    print(f"\n🚀 Starting transcription")
    print(f"📊 Model: {model}")
    print(f"🌐 Language: {language}")
    print(f"📁 Output: {output_dir}")
    print(f"📝 Files to process: {len(selected_indices)}")
    
    # Transcribe selected files
    success_count = 0
    failed_count = 0
    all_stats = []
    overall_start_time = time.time()
    
    for idx in selected_indices:
        media_file = media_files[idx]
        
        # Skip already transcribed files
        if file_already_transcribed(media_file, output_dir):
            print(f"\n⏭️  Skipping (already done): {media_file.name}")
            continue
        
        success, stats = transcribe_file(media_file, output_dir, model, language)
        all_stats.append(stats)
        
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    overall_duration = time.time() - overall_start_time
    
    # Print detailed summary report
    print("\n" + "="*60)
    print("🏁 TRANSCRIPTION REPORT")
    print("="*60)
    print(f"⏱️  Total time: {timedelta(seconds=int(overall_duration))}")
    print(f"✅ Successful: {success_count}")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")
    print(f"📁 Output directory: {output_dir}")
    
    if all_stats:
        print("\n" + "-"*60)
        print("📊 DETAILED STATISTICS")
        print("-"*60)
        
        total_size = 0
        total_chars = 0
        total_words = 0
        total_lines = 0
        total_duration = 0
        
        for stat in all_stats:
            if stat["success"]:
                print(f"\n📄 {stat['file_name']}")
                print(f"   Size: {stat['file_size_mb']:.2f} MB")
                print(f"   Time: {timedelta(seconds=int(stat['duration_seconds']))}")
                print(f"   Output: {stat['char_count']:,} chars, {stat['word_count']:,} words, {stat['line_count']} lines")
                
                total_size += stat['file_size_mb']
                total_chars += stat['char_count']
                total_words += stat['word_count']
                total_lines += stat['line_count']
                total_duration += stat['duration_seconds']
        
        if success_count > 0:
            print("\n" + "-"*60)
            print("📈 TOTALS")
            print("-"*60)
            print(f"Total input size: {total_size:.2f} MB")
            print(f"Total processing time: {timedelta(seconds=int(total_duration))}")
            print(f"Total output: {total_chars:,} characters")
            print(f"              {total_words:,} words")
            print(f"              {total_lines} lines")
            
            if total_duration > 0:
                avg_speed = total_size / (total_duration / 60)  # MB per minute
                print(f"\n⚡ Average speed: {avg_speed:.2f} MB/min")
    
    print("="*60)
    
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == "__main__":
    main()
