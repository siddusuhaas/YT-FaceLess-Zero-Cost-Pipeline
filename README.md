# 🎬 YouTube Shorts Pipeline — Indian History & Philosophy Generator

A fully automated, 0-cost local video generation pipeline for YouTube Shorts, optimized for Apple Silicon M4 Mac. Generates premium 60-second vertical documentary-style videos on deep Indian history and philosophy.

---

## 📋 What This Does

Given a topic like *"Bhagavad Gita Chapter 2, Verse 47"* or *"The rise of Ravana"*, the pipeline automatically generates:

1. **Script** — AI-generated documentary narration with historian/philosopher tone
2. **Voiceover** — Neural TTS audio using Microsoft Edge TTS
3. **Word Timestamps** — Whisper-powered transcription for sync captions
4. **Images** — AI-generated ancient Indian artwork (via Draw Things using FLUX.1 [schnell])
5. **Final Video** — 1080×1920 vertical video with Ken Burns effect + dynamic captions

---

## 🛠️ Prerequisites (What You Need)

### 1. System Requirements
- **Mac with Apple Silicon** (M1/M2/M3/M4) — Optimized for Neural Engine
- **macOS 12+** (Monterey or later)
- **Python 3.10+**

### 2. External Services Needed

| Service | Purpose | How to Install/Run |
|---------|---------|-------------------|
| **FFmpeg** | Video processing | `brew install ffmpeg` |
| **Ollama** | Local LLM (llama3.2:3b) | `brew install ollama` |
| **Draw Things** | AI image generation (FLUX.1 [schnell]) | Download from App Store, enable HTTP API on port 7888 |
| **ElevenLabs** | Premium Voiceover (Optional) | `pip install elevenlabs` + API Key |

---

## 🚀 Quick Start

### Step 1: Check What's Already Installed

Run these commands in Terminal to check if prerequisites are installed:

```bash
# Check Python version
python3 --version

# Check if FFmpeg is installed
ffmpeg -version 2>&1 | head -1

# Check if Ollama is installed
ollama --version

# Check if Draw Things is running (optional)
curl -s http://localhost:7888/sdapi/v1/sd-models | head -1
```

**Expected outputs if installed:**
- Python: `Python 3.10.x` or higher
- FFmpeg: `ffmpeg version ...`
- Ollama: `ollama version 0.x.x`
- Draw Things: JSON response (if running)

---

### Step 2: Run the Setup Script

```bash
cd /Users/siddus_mac/Documents/Personal/Projects/Automation

# Make setup script executable
chmod +x setup.sh

# Run the full setup
./setup.sh
```

**What `setup.sh` does:**
1. Installs `ffmpeg` and `ollama` via Homebrew
2. Creates a Python virtual environment
3. Installs all Python packages
4. Downloads the Llama 3.2 model (~2GB)
5. Creates the `output/` directory

⚠️ **First run takes 5-10 minutes** due to model downloads.

---

### Step 3: Activate the Environment

```bash
# Activate the virtual environment
source venv/bin/activate
```

You'll know it's active when you see `(venv)` at the beginning of your terminal prompt.

---

### Step 4: Generate Your First Video

```bash
# Full pipeline (requires Draw Things running)
python main.py "Bhagavad Gita Chapter 2, Verse 47"

# Review script before generating (prevents hallucinations)
python main.py "The rise of Ravana" --review

# Use your own pre-written script (bypassing AI generation)
python main.py "My Custom Topic" --script-file my_script.json

# With placeholder images (no Draw Things needed)
python main.py --no-images "The rise of Ravana"

# Skip video rendering (stop after audio/images)
python main.py --no-video "Krishna's wisdom"

# Verbose mode for debugging
python main.py -v "Ancient Vedic philosophy"
```

---

## 📖 Usage Examples

### Generate a Video on Any Topic

```bash
python main.py "The life of Ravana"
python main.py "Krishna's flute in Vrindavan"
python main.py "The philosophy of Karma Yoga"
python main.py "Mahabharata: The game of dice"
```

### Test Without AI Images

If Draw Things isn't running, use `--no-images` for colored placeholders:

```bash
python main.py --no-images "Bhagavad Gita Verse 47"
```

### Debug Mode

Use `-v` or `--verbose` to see detailed progress:

```bash
python main.py -v "Your topic here"
```

---

## 📁 Output Files

All output goes to the `output/` directory:

```
output/
├── final_video.mp4     # 🎬 Final 1080×1920 video (ready for upload)
├── narration.mp3       # 🎙️ Voiceover audio
├── timestamps.json     # ⏱️ Word-level caption timestamps
├── script.json        # 📝 Generated script (title, narration, prompts)
├── image_0.png        # 🖼️ Generated images
├── image_1.png
├── image_2.png
├── image_3.png
└── image_4.png
```

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'ollama'"

**Cause:** Python environment not activated.

**Fix:**
```bash
source venv/bin/activate
python main.py "Your topic"
```

### "Cannot connect to Draw Things"

**Cause:** Draw Things app not running or HTTP API not enabled.

**Fix:**
1. Open Draw Things app
2. Go to **Settings → API Server**
3. Enable **"HTTP API Server"** on port 7888
4. Or use `--no-images` flag to skip image generation

### "Ollama model not found"

**Cause:** Llama model not downloaded.

**Fix:**
```bash
ollama serve
ollama pull llama3.2:3b
```

### "FFmpeg not found"

**Cause:** FFmpeg not installed.

**Fix:**
```bash
brew install ffmpeg
```

---

## 🔨 Manual Installation (If You Prefer)

If you want to install things manually instead of using `setup.sh`:

```bash
# 1. Install system dependencies
brew install ffmpeg ollama

# 2. Create virtual environment
python3.10 -m venv venv

# 3. Activate it
source venv/bin/activate

# 4. Install Python packages
pip install -r requirements.txt

# 5. Download Ollama model
ollama serve &
ollama pull llama3.2:3b

# 6. Create output folder
mkdir -p output
```

---

## 📊 Pipeline Stages

When you run `python main.py "Your Topic"`, here's what happens:

```
┌─────────────────────────────────────────────────────┐
│  STAGE 1: Script Generation                         │
│  (brain.py - Ollama/Llama 3.2)                      │
│  → Generates title, narration, image prompts       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 2: Voiceover + Timestamps                    │
│  (voice.py - Edge TTS + mlx-whisper)                │
│  → Creates MP3 audio + word-level captions          │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 3: Image Generation                          │
│  (vision.py - Draw Things API or placeholders)      │
│  → Creates 5 AI-generated images                     │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 4: Video Assembly                            │
│  (assembly.py - MoviePy)                            │
│  → Compiles final video with Ken Burns + captions   │
└─────────────────────────────────────────────────────┘
```

---

## 🎨 Features

| Feature | Implementation |
|---------|----------------|
| **Script Generation** | Ollama with custom historian/philosopher system prompt |
| **Voiceover** | ElevenLabs (Premium) or Edge TTS (Free fallback) |
| **Timestamps** | mlx-whisper (Apple Neural Engine optimized) |
| **Image Generation** | Draw Things API (port 7888) with FLUX.1 [schnell] |
| **Video Effects** | Ken Burns (slow zoom/pan), crossfades |
| **Captions** | Word-synced, white text with black outline |
| **Output Format** | 1080×1920 (9:16 vertical), H.264, AAC audio |

---

## ⚡ Performance Notes

- **Script generation:** ~10-30 seconds (depends on Ollama)
- **Voiceover:** ~5-10 seconds
- **Image generation:** ~30-60 seconds per image (Draw Things)
- **Video rendering:** ~2-5 minutes (MoviePy)

**Total time:** ~5-10 minutes for full pipeline with AI images

---

## 📝 Customization

### Change the Ollama Model

Edit `brain.py` and change:
```python
OLLAMA_MODEL = "llama3.2:3b"  # Or use "llama3.1:8b" for better quality
```

### Switch Voice Provider (Edge vs ElevenLabs)

Edit `voice.py`:
```python
TTS_PROVIDER = "elevenlabs"  # Set to "edge" for free mode
```

### Change the Voice

Edit `voice.py`:
```python
EDGE_VOICE = "en-IN-PrabhatNeural"  # Options: en-US-Jenny, en-GB-Sonia, etc.
```

### Change Video Resolution

Edit `assembly.py`:
```python
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
```

---

## 🐛 Known Issues

1. **Draw Things timeout** — Complex prompts may take >5 minutes. Increase `API_TIMEOUT` in `vision.py` if needed.

2. **Whisper transcription fails** — If audio is too long or unclear, timestamps may be imprecise.

3. **Memory issues** — If Mac runs out of RAM, reduce image resolution in `vision.py`.

---

## 📄 License

This project is for educational and personal use. Generated content should comply with YouTube's community guidelines.

---

## 🙏 Credits

- **Ollama** — Local LLM (https://ollama.ai)
- **Edge TTS** — Microsoft Neural TTS
- **mlx-whisper** — Apple Silicon optimized whisper
- **Draw Things** — FLUX.1 [schnell] on Mac
- **MoviePy** — Video processing

---

## ❓ Help

For issues or questions, check:
1. This README
2. Error messages in terminal
3. Log files in `output/` directory

---

**Made with ❤️ for Indian history enthusiasts**
