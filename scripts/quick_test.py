"""
scripts/quick_test.py
=====================
Fast pipeline run: Generates Script + Audio + Video (with Placeholder Images).
Skips the slow AI image generation step.

Usage:
  python scripts/quick_test.py "Topic Name"
"""
import sys
import os
from pathlib import Path

# 1. Setup paths to ensure we can import modules from the parent directory
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()

# Change working directory to project root so 'output/' is created in the right place
os.chdir(project_root)
sys.path.insert(0, str(project_root))

import main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/quick_test.py \"Topic Name\"")
        sys.exit(1)

    topic = sys.argv[1]
    print(f"🚀 Starting Quick Test (Placeholders) for: {topic}")

    # Run the pipeline with use_placeholders=True
    # This generates the script and audio normally, but uses
    # simple colored gradients instead of calling Draw Things.
    main.run_pipeline(
        topic=topic,
        use_placeholders=True,
        skip_video=False,
        verbose=True
    )