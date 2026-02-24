# Project Context: YouTube Shorts Automation Pipeline
**Date:** February 23, 2026

## 1. Project Overview
A local, automated pipeline to generate 60-second vertical YouTube Shorts on Indian history and philosophy.
**Stack:** Python 3.10, Ollama (Llama 3.2), Edge TTS, Draw Things (Stable Diffusion), MoviePy, FFmpeg.
**Hardware:** Optimized for Apple Silicon (M4).

## 2. Current Status
The pipeline is **fully functional**.

### Recent Major Updates
1.  **Voice Engine Upgrade:**
    *   Switched from macOS `say` to **Microsoft Edge TTS** (Default: `en-IN-PrabhatNeural`, Rate: `+5%`).
    *   Added robust **fallback** to macOS system voice (`Rishi`) if Edge TTS fails (403 errors).
2.  **Scripting Improvements:**
    *   Updated `brain.py` system prompt to a **"Storyteller" persona** (cinematic, non-academic tone).
    *   Added **Series Mode** (`scripts/create_series.py`) to generate multi-part videos with context awareness.
    *   Added **Review Mode** (`--review`) to pause and edit scripts manually before generation.
    *   Added **Manual Script Load** (`--script-file`) to bypass AI generation entirely.
3.  **Video Assembly:**
    *   Fixed caption cutting issues by implementing **word wrapping**.
    *   Moved captions to **bottom-center (75% down)**.
    *   Images now zoom/pan (Ken Burns) with a 5-12s duration.
4.  **Utilities:**
    *   `scripts/change_voice.py`: Regenerate audio/video for an existing project with a new voice.
    *   `scripts/quick_test.py`: Run pipeline with placeholder images for fast iteration.
    *   `scripts/update_audio.py`: Update narration text for an existing run.

## 3. Key Modules
*   **`main.py`**: Orchestrator. Handles CLI args (`--no-images`, `--review`, etc.) and pipeline stages.
*   **`brain.py`**: Generates scripts using local Ollama. Handles single scripts and series outlines.
*   **`voice.py`**: Generates audio (Edge TTS -> MP3) and timestamps (Whisper -> JSON). Handles fallbacks.
*   **`vision.py`**: Generates images via Draw Things API (HTTP port 7888).
*   **`assembly.py`**: Combines assets into `final_video.mp4` using MoviePy.

## 4. Common Commands
```bash
# Standard Run
python main.py "Topic Name"

# Review Script Before Generating (Prevents Hallucinations)
python main.py "Topic Name" --review

# Create a Multi-Part Series (e.g., 5 parts)
python scripts/create_series.py "The Mahabharata" 5

# Quick Test (No AI Images - Fast)
python scripts/quick_test.py "Topic Name"

# Change Voice of Latest Project
python scripts/change_voice.py "en-IN-NeerjaNeural"

# Use Your Own Script File
python main.py "Topic" --script-file my_script.json
```

## 5. Configuration
*   **Voice:** `voice.py` -> `EDGE_VOICE`, `EDGE_RATE`.
*   **Images:** `vision.py` -> `IMAGE_WIDTH` (768), `IMAGE_HEIGHT` (1344).
*   **Video:** `assembly.py` -> `ZOOM_FACTOR` (1.12), `CAPTION_Y_POSITION` (0.75).

## 6. Known Issues / Future Ideas
*   **Edge TTS Reliability:** Occasionally returns 403. Fallback is implemented.
*   **Background Music:** Not yet implemented.
*   **ElevenLabs:** Discussed as a potential upgrade for better voice quality (paid).

---
*Use this file to restore context in a new chat session.*