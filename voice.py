"""
voice.py — Module 2: Text-to-Speech + Word Timestamps
=======================================================
Phase A: Generates narration audio using macOS 'say' command
Phase B: Transcribes the audio with mlx-whisper to get word-level timestamps
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import mlx_whisper

# Configuration
WHISPER_MODEL = "mlx-community/whisper-base-mlx"
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"
WORDS_PER_CHUNK = 4

# Voice settings for 'say' command
SAY_VOICE = "Aman"  # High quality voice
SAY_RATE = 170  # Words per minute


def _generate_say_audio(text: str, output_path: Path) -> bool:
    """Generate audio using macOS 'say' command - best quality voices."""
    try:
        temp_aiff = "/tmp/narration.aiff"
        
        # Use say command
        result = subprocess.run(
            ["say", "-v", SAY_VOICE, "-r", str(SAY_RATE), "-o", temp_aiff, text],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"      say command failed: {result.stderr}")
            return False
        
        # Convert AIFF to MP3 using ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-i", temp_aiff, "-acodec", "libmp3lame", "-ab", "192k", str(output_path)],
            capture_output=True
        )
        
        # Clean up temp file
        if os.path.exists(temp_aiff):
            os.remove(temp_aiff)
        
        return output_path.exists() and output_path.stat().st_size > 0
        
    except Exception as e:
        print(f"      say error: {e}")
        return False


def generate_audio(narration: str, verbose: bool = True) -> Optional[Path]:
    """Convert narration text to speech using macOS 'say' command."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    if verbose:
        print(f"\n🎙️  [voice.py] Generating TTS audio...")
        print(f"   Using: macOS 'say' with voice: {SAY_VOICE}")
        word_count = len(narration.split())
        print(f"   Text: {word_count} words")

    if _generate_say_audio(narration, AUDIO_FILE):
        size_kb = AUDIO_FILE.stat().st_size / 1024
        if verbose:
            print(f"   ✅ Audio saved: {AUDIO_FILE} ({size_kb:.1f} KB)")
        return AUDIO_FILE
    
    print("   ❌ TTS generation failed")
    return None


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


def generate_timestamps(audio_path: Path, verbose: bool = True) -> Optional[list]:
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

        if not all_words:
            for segment in result.get("segments", []):
                seg_text = segment.get("text", "").strip()
                seg_words = seg_text.split()
                seg_start = segment.get("start", 0.0)
                seg_end = segment.get("end", 0.0)
                if seg_words:
                    duration_per_word = (seg_end - seg_start) / len(seg_words)
                    for j, w in enumerate(seg_words):
                        all_words.append({
                            "word": w,
                            "start": seg_start + j * duration_per_word,
                            "end": seg_start + (j + 1) * duration_per_word,
                        })

        chunks = _group_words_into_chunks(all_words, WORDS_PER_CHUNK)

        with open(TIMESTAMPS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)

        if verbose:
            print(f"   ✅ Timestamps: {len(all_words)} words → {len(chunks)} chunks ({elapsed:.1f}s)")
            print(f"   💾 Saved: {TIMESTAMPS_FILE}")

        return chunks

    except Exception as e:
        print(f"   ❌ Whisper failed: {e}")
        return None


def process_voice(narration: str, verbose: bool = True) -> tuple[Optional[Path], Optional[list]]:
    """Full voice pipeline: TTS → Audio → Timestamps."""
    audio_path = generate_audio(narration, verbose=verbose)
    if audio_path is None:
        return None, None
    chunks = generate_timestamps(audio_path, verbose=verbose)
    return audio_path, chunks


if __name__ == "__main__":
    test_narration = (
        "In the battlefield of Kurukshetra, as Arjuna's bow slipped from his hands, "
        "Krishna spoke words that would echo through eternity."
    )
    audio, chunks = process_voice(test_narration)
    if audio and chunks:
        print(f"✅ Generated {len(chunks)} caption chunks")
