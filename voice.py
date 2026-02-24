"""
voice.py — Module 2: Text-to-Speech + Word Timestamps
=======================================================
Phase A: Generates narration audio using Microsoft Edge TTS
Phase B: Transcribes the audio with mlx-whisper to get word-level timestamps
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import edge_tts
import mlx_whisper

# Configuration
WHISPER_MODEL = "mlx-community/whisper-base-mlx"
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"
WORDS_PER_CHUNK = 4

# --- UPDATED VOICE SETTINGS ---
# Prabhat is more grounded/authoritative for Bhagavad Gita narration
EDGE_VOICE = "en-IN-PrabhatNeural" 
EDGE_RATE = "+5%"  # Slightly faster for engaging storytelling flow

# Fallback Voice settings (macOS built-in)
MACOS_VOICE = "Rishi"


async def _generate_edge_audio(text: str, output_path: Path) -> bool:
    """Generate audio using Microsoft Edge TTS with improved error catching."""
    try:
        communicate = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE)
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        # Catching the 403 Forbidden specifically
        if "403" in str(e):
            print(f"      ❌ Edge TTS 403 Forbidden: Microsoft blocked the request.")
        else:
            print(f"      Edge TTS error: {e}")
        return False


def _generate_macos_audio(text: str, output_path: Path) -> bool:
    """Fallback: Generate audio using macOS 'say' command."""
    try:
        temp_aiff = output_path.with_suffix(".aiff")
        
        # 1. Generate AIFF using 'say'
        try:
            # Using -r (rate) to match the slower speed for the fallback as well
            cmd = ["say", "-v", MACOS_VOICE, "-r", "150", "-o", str(temp_aiff), text]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print(f"      Voice '{MACOS_VOICE}' not found, using system default.")
            cmd = ["say", "-o", str(temp_aiff), text]
            subprocess.run(cmd, check=True, capture_output=True)
        
        # 2. Convert to MP3 using ffmpeg
        cmd_convert = [
            "ffmpeg", "-y", "-i", str(temp_aiff),
            "-acodec", "libmp3lame", "-q:a", "2",
            str(output_path)
        ]
        subprocess.run(cmd_convert, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if temp_aiff.exists():
            temp_aiff.unlink()
            
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        print(f"      macOS fallback error: {e}")
        return False


def generate_audio(narration: str, output_path: Path = AUDIO_FILE, verbose: bool = True) -> Optional[Path]:
    """Convert narration text to speech using Edge TTS (with macOS fallback)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"\n🎙️  [voice.py] Generating TTS audio...")
        print(f"   Using: {EDGE_VOICE} at {EDGE_RATE} rate")

    # Run async generation
    success = False
    try:
        # Use a new event loop to avoid issues with existing ones
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(_generate_edge_audio(narration, output_path))
        loop.close()
    except Exception as e:
        print(f"   ❌ Async execution failed: {e}")

    if success:
        size_kb = output_path.stat().st_size / 1024
        if verbose:
            print(f"   ✅ Audio saved: {output_path} ({size_kb:.1f} KB)")
        return output_path
    
    # Fallback to macOS 'say'
    if verbose:
        print(f"   ⚠️  Edge TTS failed. Falling back to macOS: {MACOS_VOICE}")
    
    if _generate_macos_audio(narration, output_path):
        size_kb = output_path.stat().st_size / 1024
        if verbose:
            print(f"   ✅ Audio saved (Fallback): {output_path} ({size_kb:.1f} KB)")
        return output_path

    print("   ❌ TTS generation failed (both Edge and macOS)")
    return None

# ... [Rest of your timestamp and process_voice functions remain the same] ...

def _group_words_into_chunks(words: list, chunk_size: int = WORDS_PER_CHUNK) -> list:
    """Group word-level timestamps into caption chunks."""
    chunks = []
    for i in range(0, len(words), chunk_size):
        group = words[i:i + chunk_size]
        if not group:
            continue
        chunk_text = " ".join(w["word"].strip() for w in group)
        chunks.append({
            "text": chunk_text,
            "start": round(group[0]["start"], 3),
            "end": round(group[-1]["end"], 3)
        })
    return chunks

def generate_timestamps(audio_path: Path, output_path: Path = TIMESTAMPS_FILE, verbose: bool = True) -> Optional[list]:
    """Transcribe audio with mlx-whisper to extract word-level timestamps."""
    if verbose:
        print(f"\n⏱️  [voice.py] Extracting word timestamps...")

    try:
        start_time = time.time()
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=WHISPER_MODEL,
            word_timestamps=True,
            language="en",
            verbose=False,
        )
        elapsed = time.time() - start_time

        all_words = []
        for segment in result.get("segments", []):
            for word_data in segment.get("words", []):
                word = word_data.get("word", "").strip()
                if word:
                    all_words.append({
                        "word": word,
                        "start": word_data.get("start", 0.0),
                        "end": word_data.get("end", 0.0),
                    })

        chunks = _group_words_into_chunks(all_words, WORDS_PER_CHUNK)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)

        if verbose:
            print(f"   ✅ Timestamps: {len(all_words)} words → {len(chunks)} chunks ({elapsed:.1f}s)")
        return chunks
    except Exception as e:
        print(f"   ❌ Whisper failed: {e}")
        return None

def process_voice(narration: str, output_dir: Path = OUTPUT_DIR, verbose: bool = True) -> tuple[Optional[Path], Optional[list]]:
    """Full voice pipeline: TTS → Audio → Timestamps."""
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = generate_audio(narration, output_path=output_dir / "narration.mp3", verbose=verbose)
    if audio_path is None:
        return None, None
    chunks = generate_timestamps(audio_path, output_path=output_dir / "timestamps.json", verbose=verbose)
    return audio_path, chunks

if __name__ == "__main__":
    test_narration = (
        "In the battlefield of Kurukshetra, as Arjuna's bow slipped from his hands, "
        "Krishna spoke words that would echo through eternity."
    )
    process_voice(test_narration)