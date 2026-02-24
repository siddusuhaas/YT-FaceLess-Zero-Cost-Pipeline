"""
scripts/change_voice.py
=======================
Regenerates the narration using a different Edge TTS voice,
then re-assembles the video with the new audio and timestamps.

Usage:
  python scripts/change_voice.py "VoiceName" [ProjectDir]
  
Example:
  python scripts/change_voice.py "en-IN-PrabhatNeural"
  python scripts/change_voice.py "Daniel" output/2026-02-23_My_Project
"""
import json
import os
import sys
from pathlib import Path

# 1. Setup paths
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()

os.chdir(project_root)
sys.path.append(str(project_root))

import assembly
import voice

def get_latest_project_dir():
    """Find the most recently created project directory in output/."""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    # Filter for directories that look like timestamps (start with digit)
    dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name[0].isdigit()]
    if not dirs:
        return None
    # Sort by name (which is timestamped) and take the last one
    return sorted(dirs)[-1]

def change_voice(voice_name, project_dir_path=None):
    # 2. Load existing narration from script.json
    project_dir = Path(project_dir_path) if project_dir_path else get_latest_project_dir()
    
    if not project_dir or not project_dir.exists():
        print("❌ No project directory found. Run the main pipeline first.")
        return

    script_path = project_dir / "script.json"
    if not script_path.exists():
        print(f"❌ Script not found at: {script_path}")
        return

    with open(script_path, "r") as f:
        data = json.load(f)
        narration = data.get("narration", "")

    if not narration:
        print("❌ No narration text found in script.json.")
        return

    print(f"\n📂 Project: {project_dir}")
    print(f"\n️  Changing voice to: {voice_name}")
    print(f"📜 Text: \"{narration[:50]}...\"")

    # 3. Monkey-patch the voice module settings
    voice.EDGE_VOICE = voice_name
    voice.MACOS_VOICE = voice_name
    
    # 4. Regenerate Audio & Timestamps
    audio_path, chunks = voice.process_voice(narration, output_dir=project_dir)
    
    if not audio_path or not chunks:
        print("❌ Failed to generate audio.")
        return

    # 5. Find existing images
    images = sorted(project_dir.glob("image_*.png"), key=lambda p: p.name)
    
    if not images:
        print(f"❌ No images found in {project_dir}.")
        return

    # 6. Re-assemble video
    output_filename = f"final_video_{voice_name.replace(' ', '_')}.mp4"
    print(f"🔄 Re-assembling video to {output_filename}...")
    
    assembly.assemble_video(
        image_paths=images,
        audio_path=audio_path,
        caption_chunks=chunks,
        output_path=project_dir / output_filename
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/change_voice.py \"Voice Name\" [Optional: Project Path]")
        print("\nCommon Edge TTS Voices:")
        print("  en-IN-NeerjaNeural (Female, Indian)")
        print("  en-IN-PrabhatNeural (Male, Indian)")
        print("  en-US-ChristopherNeural (Male, US)")
        print("  en-GB-SoniaNeural (Female, UK)")
        sys.exit(1)
        
    project_path = sys.argv[2] if len(sys.argv) > 2 else None
    change_voice(sys.argv[1], project_path)