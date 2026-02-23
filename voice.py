"""
voice.py — Module 2: Text-to-Speech + Word Timestamps
=======================================================
Phase A: Generates narration audio using edge-tts (en-IN-NeerjaNeural)
Phase B: Transcribes the audio with mlx-whisper to get word-level timestamps

Output files:
    output/narration.mp3       — The spoken audio
    output/timestamps.json     — Word-level timestamps [{word, start, end}, ...]
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import edge_tts
import mlx_whisper

# ── Configuration ─────────────────────────────────────────────────────────────
TTS_VOICE = "en-IN-NeerjaNeural"          # Indian English, female, warm & clear
WHISPER_MODEL = "mlx-community/whisper-base-mlx"  # Fast on Apple Neural Engine
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"

# Words per caption chunk (for subtitle grouping)
WORDS_PER_CHUNK = 4


# ── Phase A: Text-to-Speech ───────────────────────────────────────────────────

async def _generate_tts_async(text: str, output_path: Path) -> bool:
    """Generate MP3 audio from text using edge-tts."""
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(output_path))
    return True


def generate_audio(narration: str, verbose: bool = True) -> Optional[Path]:
    """
    Convert narration text to speech using Microsoft edge-tts.

    Args:
        narration: The full spoken script text
        verbose: Whether to print progress messages

    Returns:
        Path to the generated MP3 file, or None on failure
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if verbose:
        print(f"\n🎙️  [voice.py] Generating TTS audio...")
        print(f"   Voice: {TTS_VOICE}")
        word_count = len(narration.split())
        print(f"   Text: {word_count} words (~{word_count // 2.5:.0f} seconds)")

    try:
        asyncio.run(_generate_tts_async(narration, AUDIO_FILE))

        if AUDIO_FILE.exists() and AUDIO_FILE.stat().st_size > 0:
            size_kb = AUDIO_FILE.stat().st_size / 1024
            if verbose:
                print(f"   ✅ Audio saved: {AUDIO_FILE} ({size_kb:.1f} KB)")
            return AUDIO_FILE
        else:
            print("   ❌ Audio file was not created or is empty.")
            return None

    except Exception as e:
        print(f"   ❌ TTS generation failed: {e}")
        return None


# ── Phase B: Whisper Transcription for Word Timestamps ───────────────────────

def _group_words_into_chunks(words: list, chunk_size: int = WORDS_PER_CHUNK) -> list:
    """
    Group word-level timestamps into caption chunks.

    Each chunk: {"text": "...", "start": float, "end": float}
    """
    chunks = []
    for i in range(0, len(words), chunk_size):
        group = words[i:i + chunk_size]
        if not group:
            continue

        chunk_text = " ".join(w["word"].strip() for w in group)
        chunk_start = group[0]["start"]
        chunk_end = group[-1]["end"]

        chunks.append({
            "text": chunk_text,
            "start": round(chunk_start, 3),
            "end": round(chunk_end, 3)
        })

    return chunks


def generate_timestamps(audio_path: Path, verbose: bool = True) -> Optional[list]:
    """
    Transcribe audio with mlx-whisper to extract word-level timestamps.

    Args:
        audio_path: Path to the MP3/WAV audio file
        verbose: Whether to print progress messages

    Returns:
        List of caption chunks: [{"text": str, "start": float, "end": float}, ...]
        None on failure
    """
    if verbose:
        print(f"\n⏱️  [voice.py] Extracting word timestamps with mlx-whisper...")
        print(f"   Model: {WHISPER_MODEL}")
        print(f"   Audio: {audio_path}")
        print(f"   (Running on Apple Neural Engine — this is fast!)")

    try:
        start_time = time.time()

        # Run mlx-whisper with word-level timestamps
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=WHISPER_MODEL,
            word_timestamps=True,
            language="en",
            verbose=False,
        )

        elapsed = time.time() - start_time

        # Extract word-level data from segments
        all_words = []
        for segment in result.get("segments", []):
            for word_data in segment.get("words", []):
                word = word_data.get("word", "").strip()
                if word:  # Skip empty words
                    all_words.append({
                        "word": word,
                        "start": word_data.get("start", 0.0),
                        "end": word_data.get("end", 0.0),
                    })

        if not all_words:
            print("   ⚠️  No word timestamps found in transcription.")
            # Fallback: use segment-level timestamps
            all_words = []
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

        # Group into caption chunks
        chunks = _group_words_into_chunks(all_words, WORDS_PER_CHUNK)

        # Save to JSON
        with open(TIMESTAMPS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"   ✅ Timestamps extracted in {elapsed:.1f}s")
            print(f"   📊 {len(all_words)} words → {len(chunks)} caption chunks")
            print(f"   💾 Saved: {TIMESTAMPS_FILE}")

        return chunks

    except Exception as e:
        print(f"   ❌ Whisper transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ── Main Pipeline Function ────────────────────────────────────────────────────

def process_voice(narration: str, verbose: bool = True) -> tuple[Optional[Path], Optional[list]]:
    """
    Full voice pipeline: TTS → Audio → Timestamps.

    Args:
        narration: The spoken script text
        verbose: Whether to print progress messages

    Returns:
        Tuple of (audio_path, caption_chunks)
        Either may be None on failure
    """
    # Phase A: Generate audio
    audio_path = generate_audio(narration, verbose=verbose)
    if audio_path is None:
        return None, None

    # Phase B: Extract timestamps
    chunks = generate_timestamps(audio_path, verbose=verbose)

    return audio_path, chunks


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Demo text for testing
        test_narration = (
            "In the battlefield of Kurukshetra, as Arjuna's bow slipped from his hands, "
            "Krishna spoke words that would echo through eternity. "
            "You have a right to perform your prescribed duties, but you are not entitled "
            "to the fruits of your actions. This single verse, the forty-seventh of the "
            "second chapter, contains the entire philosophy of karma yoga. "
            "It teaches us to act with complete dedication, without attachment to outcomes. "
            "In our modern world of anxiety and expectation, this ancient wisdom becomes "
            "a revolutionary act of liberation. Do your work. Do it well. Release the result."
        )
        print("No text provided. Using demo narration...")
    else:
        test_narration = " ".join(sys.argv[1:])

    audio, chunks = process_voice(test_narration)

    if audio and chunks:
        print("\n" + "─" * 60)
        print("CAPTION CHUNKS (first 5):")
        print("─" * 60)
        for chunk in chunks[:5]:
            print(f"  [{chunk['start']:.2f}s → {chunk['end']:.2f}s] \"{chunk['text']}\"")
        print(f"  ... ({len(chunks)} total chunks)")
    else:
        print("❌ Voice processing failed.")
        sys.exit(1)
