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
    txt_file = output_dir / f"{media_file.stem}.md"
    return txt_file.exists()

def get_media_duration(media_file: Path) -> float:
    """
    Get duration of media file in seconds using ffprobe
    Returns 0 if unable to determine duration
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_file)
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (ValueError, FileNotFoundError):
        pass
    return 0

def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def transcribe_file(
    media_file: Path, 
    output_dir: Path,
    model: str = "turbo",
    language: str = "en",
    avg_processing_speed: float = 0
) -> tuple[bool, dict]:
    """
    Transcribe a single file using Whisper
    Returns (success: bool, stats: dict with processing info)
    
    avg_processing_speed: seconds per MB (for estimation)
    """
    # Get file size and duration
    file_size_bytes = media_file.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    media_duration = get_media_duration(media_file)
    
    print(f"\n🎙️  Transcribing: {media_file.name}")
    print(f"    📦 Size: {file_size_mb:.2f} MB")
    if media_duration > 0:
        print(f"    🎬 Duration: {format_time(media_duration)}")
    
    # Estimate time if we have speed data
    if avg_processing_speed > 0:
        estimated_time = file_size_mb * avg_processing_speed
        print(f"    ⏳ Estimated time: ~{format_time(estimated_time)}")
    
    # Determine output filename (add index if file exists)
    base_output = output_dir / f"{media_file.stem}.md"
    output_file = base_output
    index = 1
    while output_file.exists():
        output_file = output_dir / f"{media_file.stem}-{index}.md"
        index += 1
    
    if output_file != base_output:
        print(f"    📝 Output will be: {output_file.name}")
    
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
        # Run whisper and show live progress
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Show progress animation while processing
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_idx = 0
        
        while process.poll() is None:
            elapsed = time.time() - start_time
            if avg_processing_speed > 0:
                estimated_total = file_size_mb * avg_processing_speed
                remaining = max(0, estimated_total - elapsed)
                progress_msg = f"    {spinner[spinner_idx]} Processing... {format_time(elapsed)} elapsed / ~{format_time(remaining)} remaining"
            else:
                progress_msg = f"    {spinner[spinner_idx]} Processing... {format_time(elapsed)} elapsed"
            
            print(f"\r{progress_msg}", end='', flush=True)
            spinner_idx = (spinner_idx + 1) % len(spinner)
            time.sleep(0.1)
        
        # Get the result
        stdout, stderr = process.communicate()
        result = process
        
        # Calculate duration
        duration = time.time() - start_time
        
        stats = {
            "file_name": media_file.name,
            "file_size_mb": file_size_mb,
            "media_duration_seconds": media_duration,
            "duration_seconds": duration,
            "success": False,
            "char_count": 0,
            "word_count": 0,
            "line_count": 0
        }
        
        if result.returncode == 0:
            # Whisper creates .txt file, we need to read it and convert to .md
            whisper_output = output_dir / f"{media_file.stem}.txt"
            
            if whisper_output.exists():
                content = whisper_output.read_text(encoding='utf-8')
                stats["char_count"] = len(content)
                stats["word_count"] = len(content.split())
                stats["line_count"] = len(content.splitlines())
                stats["success"] = True
                
                # Clear the "Processing..." line and show result
                print(f"\r    ⏱️  Processing time: {format_time(duration)}" + " " * 20)
                
                # Prepend statistics to the output file
                stats_header = f""" Transcription Statistics
* File: {media_file.name}
* Size: {file_size_mb:.2f} MB
"""
                if media_duration > 0:
                    stats_header += f"* Media duration: {format_time(media_duration)}\n"
                
                stats_header += f"""* Processing time: {format_time(duration)}
* Output: {stats['char_count']:,} characters, {stats['word_count']:,} words, {stats['line_count']} lines
* Model: {model}
* Language: {language}


"""
                
                # Write to the final output file (may have index suffix)
                output_file.write_text(stats_header + content, encoding='utf-8')
                
                # Remove the original whisper output if it's different from our target
                if whisper_output != output_file:
                    whisper_output.unlink()
                
                print(f"    ✅ Done: {output_file.name}")
                print(f"    📊 Stats: {stats['char_count']:,} chars, {stats['word_count']:,} words, {stats['line_count']} lines")
            else:
                print(f"\r    ❌ Output file not found" + " " * 40)
            return True, stats
        else:
            print(f"\r    ❌ Error: {stderr.strip()}" + " " * 40)
            return False, stats
    except Exception as e:
        duration = time.time() - start_time
        stats = {
            "file_name": media_file.name,
            "file_size_mb": file_size_mb,
            "media_duration_seconds": media_duration,
            "duration_seconds": duration,
            "success": False,
            "char_count": 0,
            "word_count": 0,
            "line_count": 0
        }
        print(f"\r    ❌ Exception: {e}" + " " * 40)
        return False, stats

def show_file_menu(files: list[Path], output_dir: Path, current_language: str, current_subdir: str) -> tuple[list[int], str, str]:
    """
    Show file selection menu for transcription
    Returns (list of selected file indices, language code, subdirectory)
    """
    print("\n" + "="*60)
    print("🎬 Whisper Transcription Tool")
    print("="*60)
    print(f"🌐 Current language: {current_language}")
    if current_subdir:
        print(f"📂 Subdirectory: {current_subdir}")
    print("="*60)
    print("0) All files")
    
    for idx, file in enumerate(files, start=1):
        status = "✓" if file_already_transcribed(file, output_dir) else " "
        print(f"{idx}) [{status}] {file.name}")
    
    print("="*60)
    print("Enter numbers separated by space (e.g.: 1 3 5) or 0 for all")
    print("Or type 2-3 letter code (e.g.: en, ru) to change language")
    print("Or type word/phrase (e.g.: lectures, my-notes) for subdirectory")
    print("Press Enter without input to exit")
    
    while True:
        try:
            choice = input("\nChoice: ").strip()
            
            if not choice:
                return [], current_language, current_subdir
            
            # Check if it's a language code (2-3 letters only, all alpha)
            if choice.isalpha() and 2 <= len(choice) <= 3:
                print(f"🌐 Language changed to: {choice}")
                return None, choice, current_subdir  # Return None to indicate language change
            
            # Check if it's a subdirectory name (word/phrase, not a number)
            if choice.isalnum() or '-' in choice or '_' in choice:
                # If it contains digits or is longer than 3 chars and not purely digits
                if not choice.isdigit() and (len(choice) > 3 or any(c in choice for c in ['-', '_']) or any(c.isdigit() for c in choice)):
                    print(f"📂 Subdirectory set to: {choice}")
                    return None, current_language, choice  # Return None to indicate subdir change
            
            if choice == "0":
                return list(range(len(files))), current_language, current_subdir
            
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
                    print(f"❌ '{num}' is not a number or valid language code")
            
            if selected:
                return selected, current_language, current_subdir
            else:
                print("❌ No files selected. Try again.")
                
        except (EOFError, KeyboardInterrupt):
            print("\n\n❌ Cancelled by user")
            return [], current_language, current_subdir

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
    
    # Transcription settings
    model = "turbo"  # can be changed to "base", "small", "medium", "large"
    language = "en"  # default language
    subdir = ""  # subdirectory for output files
    
    # Show menu and get selection (loop to allow language/subdir changes)
    selected_indices = None
    while selected_indices is None:
        selected_indices, language, subdir = show_file_menu(media_files, output_dir, language, subdir)
        
        if not selected_indices and selected_indices != []:
            # Language or subdirectory was changed, show menu again
            selected_indices = None
            continue
    
    if not selected_indices:
        print("\n👋 Exit")
        sys.exit(0)
    
    # Create subdirectory if specified
    final_output_dir = output_dir
    if subdir:
        final_output_dir = output_dir / subdir
        final_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 Starting transcription")
    print(f"📊 Model: {model}")
    print(f"🌐 Language: {language}")
    print(f"📁 Output: {final_output_dir}")
    print(f"📝 Files to process: {len(selected_indices)}\n")
    
    # Transcribe selected files
    success_count = 0
    failed_count = 0
    all_stats = []
    overall_start_time = time.time()
    
    # Calculate average processing speed (seconds per MB)
    avg_processing_speed = 0.0
    total_processed_mb = 0.0
    total_processed_time = 0.0
    
    for file_num, idx in enumerate(selected_indices, start=1):
        media_file = media_files[idx]
        
        # Show progress
        print(f"\n{'='*60}")
        print(f"📊 Progress: {file_num}/{len(selected_indices)} files")
        
        # Calculate remaining files stats
        if avg_processing_speed > 0 and file_num > 1:
            remaining_files = len(selected_indices) - file_num + 1
            # Estimate remaining time based on average file size
            remaining_mb = sum(media_files[i].stat().st_size / (1024 * 1024) 
                             for i in selected_indices[file_num-1:])
            estimated_remaining = remaining_mb * avg_processing_speed
            
            overall_elapsed = time.time() - overall_start_time
            estimated_total = overall_elapsed + estimated_remaining
            
            print(f"⏳ Estimated remaining: ~{format_time(estimated_remaining)}")
            print(f"🏁 Estimated completion: ~{format_time(estimated_total)} total")
        print(f"{'='*60}")
        
        # Transcribe file (will create indexed file if already exists)
        success, stats = transcribe_file(media_file, final_output_dir, model, language, avg_processing_speed)
        all_stats.append(stats)
        
        # Update average processing speed
        if stats["success"]:
            total_processed_mb += stats["file_size_mb"]
            total_processed_time += stats["duration_seconds"]
            if total_processed_mb > 0:
                avg_processing_speed = total_processed_time / total_processed_mb
        
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    overall_duration = time.time() - overall_start_time
    
    # Print detailed summary report
    print("\n" + "="*60)
    print("🏁 TRANSCRIPTION REPORT")
    print("="*60)
    print(f"⏱️  Total time: {format_time(overall_duration)}")
    print(f"✅ Successful: {success_count}")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")
    print(f"📁 Output directory: {final_output_dir}")
    
    if all_stats:
        print("\n" + "-"*60)
        print("📊 DETAILED STATISTICS")
        print("-"*60)
        
        total_size = 0
        total_media_duration = 0
        total_chars = 0
        total_words = 0
        total_lines = 0
        total_duration = 0
        
        for stat in all_stats:
            if stat["success"]:
                print(f"\n📄 {stat['file_name']}")
                print(f"   Size: {stat['file_size_mb']:.2f} MB")
                if stat['media_duration_seconds'] > 0:
                    print(f"   Media duration: {format_time(stat['media_duration_seconds'])}")
                print(f"   Processing time: {format_time(stat['duration_seconds'])}")
                print(f"   Output: {stat['char_count']:,} chars, {stat['word_count']:,} words, {stat['line_count']} lines")
                
                total_size += stat['file_size_mb']
                total_media_duration += stat['media_duration_seconds']
                total_chars += stat['char_count']
                total_words += stat['word_count']
                total_lines += stat['line_count']
                total_duration += stat['duration_seconds']
        
        if success_count > 0:
            print("\n" + "-"*60)
            print("📈 TOTALS")
            print("-"*60)
            print(f"Total input size: {total_size:.2f} MB")
            if total_media_duration > 0:
                print(f"Total media duration: {format_time(total_media_duration)}")
            print(f"Total processing time: {format_time(total_duration)}")
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
