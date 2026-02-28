"""
scripts/regenerate.py
=====================
Regenerates the audio and video for an existing project folder using the
current code in voice.py and assembly.py.

Useful when you have tweaked code (e.g. caption styles, TTS logic) and
want to update an existing video without generating new images.

Usage:
  python scripts/regenerate.py output/2026-02-xx_Your_Project_Folder
"""

import json
import os
import sys
from pathlib import Path

# Setup paths to import modules from parent directory
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()

os.chdir(project_root)
sys.path.append(str(project_root))

import voice
import assembly

def regenerate(project_dir_path):
    project_dir = Path(project_dir_path)
    if not project_dir.exists():
        print(f"❌ Directory not found: {project_dir}")
        return

    print(f"🔄 Regenerating video in: {project_dir}")

    # 1. Load Script
    script_path = project_dir / "script.json"
    if not script_path.exists():
        print("❌ script.json not found.")
        return
    
    with open(script_path, "r") as f:
        data = json.load(f)
        narration = data.get("narration", "")
        scene_timing = data.get("scene_timing", None)

    # 2. Regenerate Voice (uses updated voice.py)
    print("🎙️  Regenerating audio & timestamps...")
    audio_path, chunks = voice.process_voice(narration, output_dir=project_dir)
    if not audio_path:
        print("❌ Voice generation failed.")
        return

    # 3. Find Images
    images = sorted(project_dir.glob("image_*.png"), key=lambda p: p.name)
    if not images:
        print("❌ No images found.")
        return
    print(f"🖼️  Found {len(images)} images.")

    # 4. Assemble Video (uses updated assembly.py)
    print("🎬 Assembling video...")
    output_path = project_dir / "final_video_regenerated.mp4"
    
    assembly.assemble_video(
        image_paths=images,
        audio_path=audio_path,
        caption_chunks=chunks,
        scene_timing=scene_timing,
        output_path=output_path
    )
    
    print(f"\n✅ Done! Output: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/regenerate.py <project_directory>")
        sys.exit(1)
    
    regenerate(sys.argv[1])