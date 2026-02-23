#!/usr/bin/env python3
"""
main.py — YouTube Shorts Pipeline Orchestrator
===============================================
Ties all modules together into a single command:

    python main.py "Bhagavad Gita Chapter 2, Verse 47"

Modules invoked (in order):
  1. brain.py   → Script generation (Ollama/Llama 3)
  2. voice.py   → Audio + word timestamps (edge-tts + mlx-whisper)
  3. vision.py  → Image generation (Draw Things API)
  4. assembly.py → Final video assembly (moviepy)

Flags:
  --no-images   : Skip image generation, use colored placeholders
  --no-video    : Skip video rendering (stop after audio/images)
  -v, --verbose : Print detailed progress
  -h, --help    : Show this help message
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add current directory to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

# Import pipeline modules
import brain
import voice
import vision
import assembly


# ── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
SCRIPT_FILE = OUTPUT_DIR / "script.json"


# ── CLI Argument Parser ───────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a documentary-style YouTube Short on Indian history/philosophy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Bhagavad Gita Chapter 2, Verse 47"
  python main.py "The rise of Ravana"
  python main.py --no-images "Krishna's flute"    # Uses placeholder images
  
Required external services:
  • Ollama (llama3.2:3b)     - Run: ollama serve
  • Draw Things (port 7888)  - Enable: Settings → API Server → HTTP API
  • FFmpeg                   - Installed via setup.sh
        """
    )

    parser.add_argument(
        "topic",
        nargs="?",
        default="Bhagavad Gita Chapter 2, Verse 47",
        help="The historical/philosophical topic for the video (default: %(default)s)"
    )

    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip Draw Things image generation, use colored placeholders instead"
    )

    parser.add_argument(
        "--no-video",
        action="store_true",
        help="Stop after generating script + audio + images (skip final video render)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress messages"
    )

    return parser.parse_args()


# ── Pipeline Stage 1: Script Generation ───────────────────────────────────────

def stage_1_generate_script(topic: str, verbose: bool) -> dict | None:
    """Generate the documentary script using Ollama."""
    print("\n" + "═" * 70)
    print("  STAGE 1: Script Generation")
    print("═" * 70)

    result = brain.generate_script(topic, verbose=verbose)

    if result is None:
        print("\n❌ FAILED: Script generation failed.")
        return None

    # Save script to JSON for reference
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Script saved to: {SCRIPT_FILE}")
    return result


# ── Pipeline Stage 2: Voiceover + Timestamps ─────────────────────────────────

def stage_2_generate_voice(narration: str, verbose: bool) -> tuple[Path | None, list | None]:
    """Generate TTS audio and extract word-level timestamps."""
    print("\n" + "═" * 70)
    print("  STAGE 2: Voiceover + Timestamps")
    print("═" * 70)

    audio_path, caption_chunks = voice.process_voice(narration, verbose=verbose)

    if audio_path is None or caption_chunks is None:
        print("\n❌ FAILED: Voice processing failed.")
        return None, None

    print(f"\n✅ Voice pipeline complete.")
    print(f"   Audio: {audio_path}")
    print(f"   Captions: {len(caption_chunks)} chunks")
    return audio_path, caption_chunks


# ── Pipeline Stage 3: Image Generation ─────────────────────────────────────────

def stage_3_generate_images(image_prompts: list, use_placeholders: bool, verbose: bool) -> list[Path]:
    """Generate images from prompts (or use placeholders)."""
    print("\n" + "═" * 70)
    print("  STAGE 3: Image Generation")
    print("═" * 70)

    if use_placeholders:
        print("\n⚠️  --no-images flag detected: Using placeholder images.")
        image_paths = vision.generate_placeholder_images(
            count=len(image_prompts),
            verbose=verbose
        )
    else:
        image_paths = vision.generate_images(image_prompts, verbose=verbose)

    if not image_paths:
        print("\n❌ FAILED: No images could be generated.")
        print("   Try running with --no-images to use placeholders.")
        return []

    print(f"\n✅ Image generation complete: {len(image_paths)} images")
    return image_paths


# ── Pipeline Stage 4: Video Assembly ───────────────────────────────────────────

def stage_4_assemble_video(
    image_paths: list,
    audio_path: Path,
    caption_chunks: list,
    verbose: bool
) -> Path | None:
    """Assemble the final video with Ken Burns effect and captions."""
    print("\n" + "═" * 70)
    print("  STAGE 4: Video Assembly")
    print("═" * 70)

    output_path = assembly.assemble_video(
        image_paths=image_paths,
        audio_path=audio_path,
        caption_chunks=caption_chunks,
        verbose=verbose
    )

    if output_path is None:
        print("\n❌ FAILED: Video assembly failed.")
        return None

    return output_path


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    topic: str,
    use_placeholders: bool = False,
    skip_video: bool = False,
    verbose: bool = True
) -> bool:
    """
    Execute the full video generation pipeline.

    Returns:
        True if pipeline completed successfully, False otherwise
    """
    overall_start = time.time()

    # Welcome banner
    print("")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "🎬 YouTube Shorts Pipeline" + " " * 26 + "║")
    print("║" + " " * 12 + "Indian History & Philosophy Generator" + " " * 17 + "║")
    print("╚" + "═" * 68 + "╝")
    print("")
    print(f"📝 Topic: \"{topic}\"")
    print(f"🔧 Mode:  {'Placeholder images' if use_placeholders else 'AI-generated images'}")
    print(f"📦 Output: {OUTPUT_DIR.absolute()}")
    print("")

    # ── Stage 1: Script ───────────────────────────────────────────────────────
    script = stage_1_generate_script(topic, verbose)
    if script is None:
        return False

    title = script.get("title", "Untitled")
    narration = script["narration"]
    image_prompts = script["image_prompts"]

    print(f"\n📋 Generated Title: {title}")
    print(f"📝 Narration: {len(narration.split())} words")
    print(f"🖼️  Image Prompts: {len(image_prompts)}")

    # ── Stage 2: Voice ─────────────────────────────────────────────────────────
    audio_path, caption_chunks = stage_2_generate_voice(narration, verbose)
    if audio_path is None or caption_chunks is None:
        return False

    # ── Stage 3: Images ─────────────────────────────────────────────────────────
    image_paths = stage_3_generate_images(image_prompts, use_placeholders, verbose)
    if not image_paths:
        return False

    # ── Stage 4: Video ─────────────────────────────────────────────────────────
    if skip_video:
        print("\n" + "═" * 70)
        print("  SKIPPED: Video Assembly (--no-video flag)")
        print("═" * 70)
        print("\n✅ Pipeline stopped after Stage 3.")
        print(f"   Audio:   {audio_path}")
        print(f"   Images: {len(image_paths)} files in {OUTPUT_DIR}")
        print(f"   Script: {SCRIPT_FILE}")
        return True

    final_video = stage_4_assemble_video(image_paths, audio_path, caption_chunks, verbose)
    if final_video is None:
        return False

    # ── Success Summary ────────────────────────────────────────────────────────
    elapsed = time.time() - overall_start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "═" * 70)
    print("  ✅ PIPELINE COMPLETE!")
    print("═" * 70)
    print("")
    print(f"   🎬 Final Video: {final_video}")
    print(f"   📐 Resolution:  1080×1920 (9:16 vertical)")
    print(f"   ⏱️  Duration:   ~{minutes}m {seconds}s total")
    print("")
    print("   📁 All output files:")
    print(f"      • {OUTPUT_DIR / 'final_video.mp4'}")
    print(f"      • {OUTPUT_DIR / 'narration.mp3'}")
    print(f"      • {OUTPUT_DIR / 'timestamps.json'}")
    print(f"      • {OUTPUT_DIR / 'script.json'}")
    for i, img in enumerate(sorted(OUTPUT_DIR.glob("image_*.png"))):
        print(f"      • {img.name}")
    print("")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "🎉 Ready for Upload!" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")
    print("")

    return True


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    success = run_pipeline(
        topic=args.topic,
        use_placeholders=args.no_images,
        skip_video=args.no_video,
        verbose=args.verbose
    )

    sys.exit(0 if success else 1)
