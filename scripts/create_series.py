"""
scripts/create_series.py
========================
Generates a multi-part video series on a single topic.
1. Generates an outline (e.g., 5 parts).
2. Creates a Series folder.
3. Runs the full pipeline for each part, passing context from previous parts.

Usage:
  python scripts/create_series.py "Topic Name" [NumParts]
  python scripts/create_series.py "path/to/series_script.json"
"""
import sys
import os
import json
import re
from pathlib import Path

# Setup paths
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()
os.chdir(project_root)
sys.path.insert(0, str(project_root))

import main
import brain

def sanitize_name(name):
    safe = re.sub(r'[^\w\s-]', '', name).strip()
    return re.sub(r'[-\s]+', '_', safe)

def create_series(topic, num_parts=5):
    print(f"\n📚 Starting Series Generation: \"{topic}\" ({num_parts} parts)")
    
    # 1. Generate Outline
    outline = brain.generate_series_outline(topic, num_parts)
    if not outline:
        print("❌ Failed to generate series outline.")
        return

    series_title = outline.get("series_title", topic)
    safe_series_title = sanitize_name(series_title)
    
    # Create Series Directory
    series_dir = Path("output") / f"SERIES_{safe_series_title}"
    series_dir.mkdir(parents=True, exist_ok=True)
    
    # Save Outline
    with open(series_dir / "outline.json", "w") as f:
        json.dump(outline, f, indent=2)
    
    print(f"📂 Series Directory: {series_dir}")
    print(f"📝 Outline saved. Starting production of {len(outline['parts'])} parts...\n")

    # 2. Loop through parts
    previous_context = ""
    
    for part in outline['parts']:
        p_num = part['part_number']
        p_title = part['title']
        p_summary = part.get('summary', '')
        
        print(f"\n" + "█" * 60)
        print(f"   PRODUCING PART {p_num}/{num_parts}: {p_title}")
        print("█" * 60)
        
        # Define specific folder for this part
        part_folder_name = f"Part_{p_num:02d}_{sanitize_name(p_title)}"
        part_dir = series_dir / part_folder_name
        
        # Run Pipeline
        # We pass the specific part title as the topic, but include the series name for context
        full_topic = f"{series_title} - Part {p_num}: {p_title}"
        
        success = main.run_pipeline(
            topic=full_topic,
            script_context=f"This is Part {p_num} of {num_parts}. Summary: {p_summary}. Previous events: {previous_context}",
            custom_output_dir=part_dir,
            verbose=True
        )
        
        # Update context for next iteration
        previous_context = p_summary

def create_series_from_file(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    series_title = data.get("series_title", "Untitled Series")
    parts = data.get("parts", [])
    
    if not parts:
        print("❌ No 'parts' found in the series JSON.")
        return

    print(f"\n📚 Starting Series Generation from File: \"{series_title}\" ({len(parts)} parts)")
    
    safe_series_title = sanitize_name(series_title)
    series_dir = Path("output") / f"SERIES_{safe_series_title}"
    series_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the source file for reference
    with open(series_dir / "source_series.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"📂 Series Directory: {series_dir}\n")

    for i, part in enumerate(parts):
        p_num = part.get('part_number', i + 1)
        p_title = part.get('title', f"Part {p_num}")
        
        print(f"\n" + "█" * 60)
        print(f"   PRODUCING PART {p_num}/{len(parts)}: {p_title}")
        print("█" * 60)
        
        part_folder_name = f"Part_{p_num:02d}_{sanitize_name(p_title)}"
        part_dir = series_dir / part_folder_name
        part_dir.mkdir(parents=True, exist_ok=True)
        
        full_topic = f"{series_title} - Part {p_num}: {p_title}"
        
        # Create a temporary script file for main.py to consume
        # We ensure the structure matches what main.py expects
        script_obj = {
            "title": p_title,
            "narration": part.get("narration", ""),
            "image_prompts": part.get("image_prompts", [])
        }
        
        temp_script = part_dir / "manual_source.json"
        with open(temp_script, "w", encoding='utf-8') as f:
            json.dump(script_obj, f, indent=2, ensure_ascii=False)
        
        # Run pipeline using the manual script file
        main.run_pipeline(
            topic=full_topic,
            custom_output_dir=part_dir,
            script_file=temp_script,
            verbose=True
        )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/create_series.py \"Topic\" [NumParts]")
        print("  python scripts/create_series.py \"path/to/series.json\"")
        sys.exit(1)
        
    arg1 = sys.argv[1]
    
    if arg1.endswith(".json"):
        create_series_from_file(arg1)
    else:
        count_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        create_series(arg1, count_arg)