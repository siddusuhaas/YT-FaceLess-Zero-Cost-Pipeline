"""
scripts/change_voice.py
=======================
Regenerates the narration using a different macOS system voice,
then re-assembles the video with the new audio and timestamps.

Usage:
  python scripts/change_voice.py "VoiceName"
  
Example:
  python scripts/change_voice.py "Daniel"
  python scripts/change_voice.py "Rishi"
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

def change_voice(voice_name):
    # 2. Load existing narration from script.json
    script_path = Path("output/script.json")
    if not script_path.exists():
        print("❌ output/script.json not found. Run the main pipeline first.")
        return

    with open(script_path, "r") as f:
        data = json.load(f)
        narration = data.get("narration", "")

    if not narration:
        print("❌ No narration text found in script.json.")
        return

    print(f"\n🗣️  Changing voice to: {voice_name}")
    print(f"📜 Text: \"{narration[:50]}...\"")

    # 3. Monkey-patch the voice module settings
    voice.SAY_VOICE = voice_name
    
    # 4. Regenerate Audio & Timestamps
    audio_path, chunks = voice.process_voice(narration)
    
    if not audio_path or not chunks:
        print("❌ Failed to generate audio.")
        return

    # 5. Find existing images
    output_dir = Path("output")
    images = sorted(output_dir.glob("image_*.png"), key=lambda p: p.name)
    
    if not images:
        print("❌ No images found in output/.")
        return

    # 6. Re-assemble video
    output_filename = f"final_video_{voice_name.replace(' ', '_')}.mp4"
    print(f"🔄 Re-assembling video to {output_filename}...")
    
    assembly.assemble_video(
        image_paths=images,
        audio_path=audio_path,
        caption_chunks=chunks,
        output_path=output_dir / output_filename
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/change_voice.py \"Voice Name\"")
        print("\nAvailable voices on your Mac (sample):")
        os.system("say -v ? | head -n 5")
        print("... (run 'say -v ?' in terminal to see all)")
        sys.exit(1)
        
    change_voice(sys.argv[1])