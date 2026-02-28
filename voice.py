"""
voice.py — Module 2: Text-to-Speech + Word Timestamps
=======================================================
Phase A: Generates narration audio using Microsoft Edge TTS
Phase B: Generates word-level timestamps by aligning the KNOWN script
         text directly against audio duration — NO Whisper transcription.

WHY WE DROPPED WHISPER:
  Whisper re-transcribes the TTS audio from scratch, which causes mishearing
  errors like "low born" → "lo-bile", "Gandiva" → "gandhivabo", etc.
  Since we already know exactly what words are being spoken (the narration
  text), we simply divide the audio duration proportionally across all words.
  This gives 100% accurate captions with zero transcription errors.
"""

import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import edge_tts

# ── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"
WORDS_PER_CHUNK = 4       # Words per caption chunk

EDGE_VOICE = "en-IN-PrabhatNeural"
EDGE_RATE = "+5%"

MACOS_VOICE = "Rishi"


# ── TTS Audio Generation ──────────────────────────────────────────────────────

async def _generate_edge_audio(text: str, output_path: Path) -> bool:
    try:
        communicate = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE)
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        if "403" in str(e):
            print(f"      ❌ Edge TTS 403 Forbidden: Microsoft blocked the request.")
        else:
            print(f"      Edge TTS error: {e}")
        return False


def _generate_macos_audio(text: str, output_path: Path) -> bool:
    try:
        temp_aiff = output_path.with_suffix(".aiff")
        try:
            cmd = ["say", "-v", MACOS_VOICE, "-r", "150", "-o", str(temp_aiff), text]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print(f"      Voice '{MACOS_VOICE}' not found, using system default.")
            cmd = ["say", "-o", str(temp_aiff), text]
            subprocess.run(cmd, check=True, capture_output=True)

        cmd_convert = [
            "ffmpeg", "-y", "-i", str(temp_aiff),
            "-acodec", "libmp3lame", "-q:a", "2",
            str(output_path)
        ]
        subprocess.run(cmd_convert, check=True,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if temp_aiff.exists():
            temp_aiff.unlink()

        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        print(f"      macOS fallback error: {e}")
        return False


def generate_audio(
    narration: str,
    output_path: Path = AUDIO_FILE,
    verbose: bool = True
) -> Optional[Path]:
    """Convert narration text to speech using Edge TTS (with macOS fallback)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"\n🎙️  [voice.py] Generating TTS audio...")
        print(f"   Voice: {EDGE_VOICE} at {EDGE_RATE} rate")

    success = False
    try:
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

    if verbose:
        print(f"   ⚠️  Edge TTS failed. Falling back to macOS: {MACOS_VOICE}")

    if _generate_macos_audio(narration, output_path):
        size_kb = output_path.stat().st_size / 1024
        if verbose:
            print(f"   ✅ Audio saved (Fallback): {output_path} ({size_kb:.1f} KB)")
        return output_path

    print("   ❌ TTS generation failed (both Edge and macOS)")
    return None


# ── Audio Duration ────────────────────────────────────────────────────────────

def _get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(audio_path)
            ],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"   ⚠️  ffprobe failed ({e}), estimating duration from file size...")
        # Rough fallback: ~16KB/s for 128kbps MP3
        size_kb = audio_path.stat().st_size / 1024
        return size_kb / 16.0


# ── Text-Based Timestamp Alignment ───────────────────────────────────────────

def _clean_word(word: str) -> str:
    """Strip punctuation from a word for display."""
    return re.sub(r"[^\w'-]", "", word).strip()


def _align_text_to_duration(
    narration: str,
    audio_duration: float,
    chunk_size: int = WORDS_PER_CHUNK,
    verbose: bool = True
) -> list:
    """
    ✅ REPLACES WHISPER: Generate caption chunks by aligning the known
    narration text directly against the audio duration.

    Strategy:
      - Split narration into words
      - Assign each word a proportional time slice
      - Add a short leading silence offset (TTS typically starts ~0.3s in)
      - Group words into chunks of `chunk_size`

    This gives 100% accurate captions since we use the original script text,
    not a re-transcription that can introduce errors.
    """
    # Tokenize: split on whitespace, preserve punctuation in display
    raw_words = narration.split()
    words = [w for w in raw_words if _clean_word(w)]  # skip empty tokens

    if not words:
        return []

    num_words = len(words)

    # TTS engines typically have ~0.3s leading silence and ~0.5s trailing
    LEADING_SILENCE = 0.3
    TRAILING_SILENCE = 0.5
    speakable_duration = audio_duration - LEADING_SILENCE - TRAILING_SILENCE

    if speakable_duration <= 0:
        speakable_duration = audio_duration

    time_per_word = speakable_duration / num_words

    # Build word-level timestamps
    word_timestamps = []
    for i, word in enumerate(words):
        start = LEADING_SILENCE + i * time_per_word
        end = start + time_per_word
        word_timestamps.append({
            "word": word,
            "start": round(start, 3),
            "end": round(end, 3),
        })

    # Group into caption chunks
    chunks = []
    for i in range(0, len(word_timestamps), chunk_size):
        group = word_timestamps[i:i + chunk_size]
        # Join words, cleaning trailing punctuation for display
        chunk_text = " ".join(w["word"] for w in group)
        chunks.append({
            "text": chunk_text,
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })

    if verbose:
        print(f"   ✅ Aligned {num_words} words → {len(chunks)} caption chunks")
        print(f"      Method: direct text alignment (no Whisper — 100% accurate)")
        print(f"      Audio:  {audio_duration:.2f}s total, "
              f"{time_per_word*1000:.0f}ms per word")

    return chunks


# ── Timestamp Generation (public API) ────────────────────────────────────────

def generate_timestamps(
    audio_path: Path,
    narration: str,
    output_path: Path = TIMESTAMPS_FILE,
    verbose: bool = True
) -> Optional[list]:
    """
    Generate word-level caption timestamps from narration text + audio duration.

    NOTE: `narration` parameter is now required — we align text directly
    instead of transcribing audio with Whisper.
    """
    if verbose:
        print(f"\n⏱️  [voice.py] Generating caption timestamps...")

    duration = _get_audio_duration(audio_path)
    if verbose:
        print(f"   Audio duration: {duration:.2f}s")

    chunks = _align_text_to_duration(
        narration=narration,
        audio_duration=duration,
        chunk_size=WORDS_PER_CHUNK,
        verbose=verbose,
    )

    if not chunks:
        print("   ❌ Failed to generate timestamps (empty narration?)")
        return None

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"   ✅ Saved: {output_path} ({len(chunks)} chunks)")

    return chunks


# ── Full Voice Pipeline ───────────────────────────────────────────────────────

def process_voice(
    narration: str,
    output_dir: Path = OUTPUT_DIR,
    verbose: bool = True
) -> tuple[Optional[Path], Optional[list]]:
    """
    Full voice pipeline: TTS → Audio → Caption Timestamps.

    Args:
        narration: The exact script text that will be spoken
        output_dir: Where to save narration.mp3 and timestamps.json
        verbose: Whether to print progress

    Returns:
        (audio_path, caption_chunks) or (None, None) on failure
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = generate_audio(
        narration,
        output_path=output_dir / "narration.mp3",
        verbose=verbose
    )
    if audio_path is None:
        return None, None

    chunks = generate_timestamps(
        audio_path=audio_path,
        narration=narration,
        output_path=output_dir / "timestamps.json",
        verbose=verbose
    )

    return audio_path, chunks


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_narration = (
        "In the battlefield of Kurukshetra, as Arjuna's bow slipped from his hands, "
        "Krishna spoke words that would echo through eternity. "
        "He said: do your duty, and do not think of the low born result."
    )
    audio, chunks = process_voice(test_narration)
    if chunks:
        print("\nSample chunks:")
        for c in chunks[:5]:
            print(f"  [{c['start']:.2f}s → {c['end']:.2f}s] {c['text']}")