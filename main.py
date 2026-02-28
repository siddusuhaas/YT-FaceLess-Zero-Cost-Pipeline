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
import re
import shutil
import sys
import time
from datetime import datetime
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
ASSETS_DIR = Path("assets/music")

def get_project_dir(topic: str) -> Path:
    """Create a sanitized directory name based on the topic."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Remove non-alphanumeric characters (except spaces and hyphens)
    safe_name = re.sub(r'[^\w\s-]', '', topic).strip()
    # Replace spaces with underscores
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    return OUTPUT_DIR / f"{timestamp}_{safe_name}"


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

    parser.add_argument(
        "--review",
        action="store_true",
        help="Pause after script generation to allow manual editing of the JSON file"
    )

    parser.add_argument(
        "--script-file",
        type=Path,
        help="Path to an existing JSON script file (skips AI generation step)"
    )

    return parser.parse_args()


# ── Pipeline Stage 1: Script Generation ───────────────────────────────────────

def stage_1_generate_script(topic: str, project_dir: Path, context: str, verbose: bool) -> dict | None:
    """Generate the documentary script using Ollama."""
    print("\n" + "═" * 70)
    print("  STAGE 1: Script Generation")
    print("═" * 70)

    project_dir.mkdir(parents=True, exist_ok=True)
    result = brain.generate_script(topic, previous_context=context, verbose=verbose)

    if result is None:
        print("\n❌ FAILED: Script generation failed.")
        return None

    # Save script to JSON for reference
    script_file = project_dir / "script.json"
    with open(script_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Script saved to: {script_file}")
    return result


# ── Pipeline Stage 2: Voiceover + Timestamps ─────────────────────────────────

def stage_2_generate_voice(narration: str, project_dir: Path, verbose: bool) -> tuple[Path | None, list | None]:
    """Generate TTS audio and extract word-level timestamps."""
    print("\n" + "═" * 70)
    print("  STAGE 2: Voiceover + Timestamps")
    print("═" * 70)

    audio_path, caption_chunks = voice.process_voice(narration, output_dir=project_dir, verbose=verbose)

    if audio_path is None or caption_chunks is None:
        print("\n❌ FAILED: Voice processing failed.")
        return None, None

    print(f"\n✅ Voice pipeline complete.")
    print(f"   Audio: {audio_path}")
    print(f"   Captions: {len(caption_chunks)} chunks")
    return audio_path, caption_chunks


# ── Pipeline Stage 3: Image Generation ─────────────────────────────────────────

def stage_3_generate_images(image_prompts: list, project_dir: Path, use_placeholders: bool, verbose: bool) -> list[Path]:
    """Generate images from prompts (or use placeholders)."""
    print("\n" + "═" * 70)
    print("  STAGE 3: Image Generation")
    print("═" * 70)

    if use_placeholders:
        print("\n⚠️  --no-images flag detected: Using placeholder images.")
        image_paths = vision.generate_placeholder_images(
            count=len(image_prompts),
            output_dir=project_dir,
            verbose=verbose
        )
    else:
        image_paths = vision.generate_images(image_prompts, output_dir=project_dir, verbose=verbose)

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
    project_dir: Path,
    verbose: bool,
    scene_timing: list = None
) -> Path | None:
    """Assemble the final video with Ken Burns effect and captions."""
    print("\n" + "═" * 70)
    print("  STAGE 4: Video Assembly")
    print("═" * 70)

    output_video_path = project_dir / "final_video.mp4"

    output_path = assembly.assemble_video(
        image_paths=image_paths,
        audio_path=audio_path,
        caption_chunks=caption_chunks,
        scene_timing=scene_timing,
        output_path=output_video_path,
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
    verbose: bool = True,
    script_context: str = None,
    custom_output_dir: Path = None,
    review_mode: bool = False,
    script_file: Path = None
) -> bool:
    """
    Execute the full video generation pipeline.

    Returns:
        True if pipeline completed successfully, False otherwise
    """
    overall_start = time.time()

    if custom_output_dir:
        project_dir = custom_output_dir
    else:
        project_dir = get_project_dir(topic)

    # Ensure assets directory exists
    if not ASSETS_DIR.exists():
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Welcome banner
    print("")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "🎬 YouTube Shorts Pipeline" + " " * 26 + "║")
    print("║" + " " * 12 + "Indian History & Philosophy Generator" + " " * 17 + "║")
    print("╚" + "═" * 68 + "╝")
    print("")
    print(f"📝 Topic: \"{topic}\"")
    print(f"🔧 Mode:  {'Placeholder images' if use_placeholders else 'AI-generated images'}")
    print(f"📦 Output: {project_dir.absolute()}")
    
    # Check for music
    music_count = len(list(ASSETS_DIR.glob("*.mp3"))) + len(list(ASSETS_DIR.glob("*.wav")))
    print(f"🎵 Music:  {music_count} tracks found in {ASSETS_DIR}")
    print("")

    # ── Stage 1: Script ───────────────────────────────────────────────────────
    if script_file:
        print("\n" + "═" * 70)
        print("  STAGE 1: Script Loading (Manual Input)")
        print("═" * 70)
        
        project_dir.mkdir(parents=True, exist_ok=True)
        target_script = project_dir / "script.json"
        
        try:
            shutil.copy(script_file, target_script)
            with open(target_script, "r", encoding="utf-8") as f:
                script = json.load(f)
            
            # Automatically apply the cartoon art style to manual scripts
            if "image_prompts" in script:
                script["image_prompts"] = brain.enrich_image_prompts(script["image_prompts"])
                
            print(f"✅ Loaded manual script from: {script_file}")
        except Exception as e:
            print(f"❌ Failed to load script file: {e}")
            return False
    else:
        script = stage_1_generate_script(topic, project_dir, script_context, verbose)
    
    if script is None:
        return False

    # ── Review Mode Pause ─────────────────────────────────────────────────────
    if review_mode:
        print("\n" + "─" * 70)
        print("  ⏸️  REVIEW MODE: Pipeline paused for manual editing.")
        print("" + "─" * 70)
        print(f"  The script is saved at: {project_dir / 'script.json'}")
        print("  1. Open this file in your text editor.")
        print("  2. Fix any hallucinations in 'narration'.")
        print("  3. Adjust 'image_prompts' if needed.")
        print("  4. Save the file.")
        input("\n  Press [Enter] to reload the script and continue...")
        
        try:
            with open(project_dir / "script.json", "r", encoding="utf-8") as f:
                script = json.load(f)
            print("  ✅ Script reloaded with your changes.")
        except Exception as e:
            print(f"  ❌ Failed to reload script: {e}")
            return False

    title = script.get("title", "Untitled")
    narration = script["narration"]
    image_prompts = script["image_prompts"]
    scene_timing = script.get("scene_timing")

    print(f"\n📋 Generated Title: {title}")
    print(f"📝 Narration: {len(narration.split())} words")
    print(f"🖼️  Image Prompts: {len(image_prompts)}")
    if scene_timing:
        print(f"⏱️  Scene Timing: {scene_timing}")

    # ── Stage 2: Voice ─────────────────────────────────────────────────────────
    audio_path, caption_chunks = stage_2_generate_voice(narration, project_dir, verbose)
    if audio_path is None or caption_chunks is None:
        return False

    # ── Stage 3: Images ─────────────────────────────────────────────────────────
    image_paths = stage_3_generate_images(image_prompts, project_dir, use_placeholders, verbose)
    if not image_paths:
        return False

    # ── Stage 4: Video ─────────────────────────────────────────────────────────
    if skip_video:
        print("\n" + "═" * 70)
        print("  SKIPPED: Video Assembly (--no-video flag)")
        print("═" * 70)
        print("\n✅ Pipeline stopped after Stage 3.")
        print(f"   Audio:   {audio_path}")
        print(f"   Images: {len(image_paths)} files in {project_dir}")
        print(f"   Script: {project_dir / 'script.json'}")
        return True

    final_video = stage_4_assemble_video(image_paths, audio_path, caption_chunks, project_dir, verbose, scene_timing=scene_timing)
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
    print(f"      • {project_dir / 'final_video.mp4'}")
    print(f"      • {project_dir / 'narration.mp3'}")
    print(f"      • {project_dir / 'timestamps.json'}")
    print(f"      • {project_dir / 'script.json'}")
    for i, img in enumerate(sorted(project_dir.glob("image_*.png"))):
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
        verbose=args.verbose,
        review_mode=args.review,
        script_file=args.script_file
    )

    sys.exit(0 if success else 1)
