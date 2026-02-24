You are an Expert AI Systems Architect and Python Developer. Your task is to build a fully automated, 0-cost local video generation pipeline for YouTube Shorts, specifically optimized for an Apple Silicon M4 Mac. 

The pipeline will generate premium, documentary-style 60-second vertical videos focusing on deep, authentic Indian history and philosophy (e.g., analyzing actual Bhagavad Gita verses or the documented history of characters like Ravana). 

Do not use any paid APIs. Everything must run locally. Please operate in a "Plan & Act" loop, asking for my approval to install dependencies and create files.

### 1. The Tech Stack (M4 Optimized)
* **Orchestration:** Python 3.10+
* **Script Generation:** Local LLM via `ollama` (using Llama 3 or similar).
* **Voiceover:** `edge-tts` (Microsoft's free neural voices).
* **Transcription/Timestamps:** `whisper` or `mlx-whisper` (optimized to run on the Mac's Neural Engine/MPS).
* **Image Generation:** Python `diffusers` library running a lightweight Stable Diffusion model natively on Apple Silicon using the `mps` (Metal Performance Shaders) device. (Alternatively, write a placeholder function to hit a local `Draw Things` HTTP API).
* **Video Assembly:** `moviepy` (using `ffmpeg` under the hood) for rendering 1080x1920 vertical video.

### 2. The Content Strategy (System Prompt Logic)
In the script generation module, hardcode a system prompt for Ollama that forces the LLM to act as a deep historian and philosopher. 
* **Input:** A specific topic (e.g., "Bhagavad Gita Chapter 2, Verse 47" or "The rise of Ravana").
* **Output:** It must return a strict JSON object containing:
    1.  `title`: A click-worthy YouTube title.
    2.  `narration`: The spoken script. If a verse is included, it must provide the native language concept followed by a deep English translation and its philosophical/practical meaning for personal development.
    3.  `image_prompts`: An array of 5-6 highly descriptive prompts for generating majestic, realistic, ancient Indian artwork to match the narration segments.

### 3. Video Editing Requirements (The "Anti-Slop" Rules)
The `moviepy` assembly script must not just slap audio over static images. It must:
* Apply a slow zoom/pan (Ken Burns effect) to every image.
* Swap the background image every 8-10 seconds.
* Parse the Whisper word-level timestamps to burn dynamic, highly visible captions (white text, black outline, thick font) onto the center of the vertical video.

### 4. Your Execution Plan
Please propose a plan to execute the following steps, and ask for my approval before proceeding:
1.  **Environment Setup:** Generate a `requirements.txt` and a shell script to `brew install ffmpeg` and set up the Python environment.
2.  **Module 1 (`brain.py`):** The Ollama JSON generation logic.
3.  **Module 2 (`voice.py`):** The `edge-tts` and Whisper timestamp generation.
4.  **Module 3 (`vision.py`):** The local `mps`-optimized image generation script.
5.  **Module 4 (`assembly.py`):** The `moviepy` rendering logic with the Ken Burns effect and dynamic subtitles.
6.  **Module 5 (`main.py`):** The orchestrator that ties it all together into a single terminal command.

Review this architecture and give me your step-by-step plan.