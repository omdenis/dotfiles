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
import subprocess
from pathlib import Path

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
) -> bool:
    """
    Transcribe a single file using Whisper
    Returns True if successful, False on error
    """
    print(f"\n🎙️  Transcribing: {media_file.name}")
    
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
        
        if result.returncode == 0:
            print(f"   ✅ Done: {media_file.stem}.txt")
            return True
        else:
            print(f"   ❌ Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

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

def main():
    # Check if whisper is installed
    if not check_whisper():
        print("❌ Whisper not found in the system!")
        print("Install it: pip install openai-whisper")
        sys.exit(1)
    
    # Current directory
    root = Path(".").resolve()
    
    # Output directory
    output_dir = root / "out"
    output_dir.mkdir(exist_ok=True)
    
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
    
    for idx in selected_indices:
        media_file = media_files[idx]
        
        # Skip already transcribed files
        if file_already_transcribed(media_file, output_dir):
            print(f"\n⏭️  Skipping (already done): {media_file.name}")
            continue
        
        if transcribe_file(media_file, output_dir, model, language):
            success_count += 1
        else:
            failed_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("🏁 Completed!")
    print(f"✅ Success: {success_count}")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")
    print(f"📁 Results in: {output_dir}")
    print("="*60)
    
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == "__main__":
    main()
