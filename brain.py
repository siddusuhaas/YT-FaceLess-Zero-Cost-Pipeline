"""
brain.py — Module 1: LLM Script Generation
============================================
Uses local Ollama (llama3.2:3b) to generate a structured JSON script
for a documentary-style YouTube Short on Indian history/philosophy.

Output JSON schema:
{
    "title": str,           # Click-worthy YouTube title
    "narration": str,       # Full spoken script (~60 seconds)
    "image_prompts": list   # 5-6 descriptive art prompts
}
"""

import json
import time
import subprocess
import sys
from typing import Optional

import ollama

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_MODEL = "llama3.2:3b"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ── Art Style Suffix ──────────────────────────────────────────────────────────
# Appended to every image prompt for consistent visual style
ART_STYLE_SUFFIX = (
    "epic oil painting, ancient Indian art style, dramatic golden hour lighting, "
    "Mughal miniature meets photorealism, rich jewel tones, cinematic composition, "
    "8K resolution, hyper-detailed, no text, no watermarks, no modern elements"
)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a world-renowned scholar of ancient Indian history, Vedic philosophy, Sanskrit literature, and the Puranas. You have spent 40 years studying the Bhagavad Gita, Mahabharata, Ramayana, Upanishads, and the lives of legendary figures like Krishna, Arjuna, Ravana, Rama, and the great sages.

Your task is to create a deeply researched, emotionally resonant, documentary-style narration for a 60-second YouTube Short. The narration must be:
- Intellectually profound yet accessible to a modern audience
- Historically and philosophically accurate
- Emotionally engaging — it should give the viewer goosebumps
- Approximately 140-160 words (perfect for 60 seconds of speech)
- If a verse or shloka is referenced, provide: the concept in its original context, a deep English translation, and its practical meaning for personal development today

You MUST respond ONLY with a single valid JSON object. No preamble, no markdown code blocks, no explanation outside the JSON. The JSON must have exactly these three keys:

1. "title": A click-worthy, curiosity-driven YouTube title (max 60 characters). Use power words. Example: "The Secret Krishna Revealed Only to Arjuna"

2. "narration": The complete spoken script as a single string. Write it as a documentary narrator would speak — with gravitas, pauses implied by punctuation, and a sense of ancient wisdom being revealed.

3. "image_prompts": An array of exactly 5 strings. Each string is a highly descriptive visual prompt for generating a majestic, realistic ancient Indian artwork image. Each prompt must describe: the scene, the characters (if any), the mood, the lighting, and the setting. Make them cinematic and specific."""

# ── User Prompt Template ──────────────────────────────────────────────────────
USER_PROMPT_TEMPLATE = """Create a 60-second YouTube Short documentary script about: "{topic}"

Remember:
- The narration must be 140-160 words
- The image_prompts array must have exactly 5 elements
- Each image prompt should visually represent a different segment of the narration
- Respond ONLY with the JSON object, nothing else"""


def _ensure_ollama_running() -> bool:
    """Check if Ollama server is running; attempt to start it if not."""
    try:
        client = ollama.Client()
        client.list()  # Simple ping
        return True
    except Exception:
        print("   ⚠️  Ollama server not running. Attempting to start...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(4)  # Give it time to start
            return True
        except FileNotFoundError:
            print("   ❌ ERROR: 'ollama' not found. Run setup.sh first.")
            return False


def _validate_script(data: dict) -> tuple[bool, str]:
    """Validate the JSON structure returned by the LLM."""
    required_keys = ["title", "narration", "image_prompts"]

    for key in required_keys:
        if key not in data:
            return False, f"Missing required key: '{key}'"

    if not isinstance(data["title"], str) or len(data["title"].strip()) == 0:
        return False, "Field 'title' must be a non-empty string"

    if not isinstance(data["narration"], str) or len(data["narration"].strip()) < 50:
        return False, "Field 'narration' must be a string with at least 50 characters"

    if not isinstance(data["image_prompts"], list):
        return False, "Field 'image_prompts' must be an array"

    if len(data["image_prompts"]) < 3:
        return False, f"Field 'image_prompts' must have at least 3 items (got {len(data['image_prompts'])})"

    return True, "OK"


def _enrich_image_prompts(prompts: list) -> list:
    """Append the art style suffix to each image prompt."""
    enriched = []
    for prompt in prompts:
        if ART_STYLE_SUFFIX.lower() not in prompt.lower():
            enriched.append(f"{prompt.rstrip('. ')}, {ART_STYLE_SUFFIX}")
        else:
            enriched.append(prompt)
    return enriched


def generate_script(topic: str, verbose: bool = True) -> Optional[dict]:
    """
    Generate a documentary script for the given topic using Ollama.

    Args:
        topic: The historical/philosophical topic (e.g., "Bhagavad Gita Chapter 2, Verse 47")
        verbose: Whether to print progress messages

    Returns:
        dict with keys: title, narration, image_prompts
        None if generation fails after all retries
    """
    if verbose:
        print(f"\n🧠 [brain.py] Generating script for: \"{topic}\"")
        print(f"   Model: {OLLAMA_MODEL}")

    # Ensure Ollama is running
    if not _ensure_ollama_running():
        return None

    user_prompt = USER_PROMPT_TEMPLATE.format(topic=topic)

    for attempt in range(1, MAX_RETRIES + 1):
        if verbose:
            print(f"   Attempt {attempt}/{MAX_RETRIES}...")

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
                options={
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 1024,
                }
            )

            raw_content = response["message"]["content"].strip()

            # Strip markdown code fences if the model added them anyway
            if raw_content.startswith("```"):
                lines = raw_content.split("\n")
                raw_content = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )

            # Parse JSON
            data = json.loads(raw_content)

            # Validate structure
            is_valid, error_msg = _validate_script(data)
            if not is_valid:
                if verbose:
                    print(f"   ⚠️  Invalid structure: {error_msg}. Retrying...")
                time.sleep(RETRY_DELAY)
                continue

            # Enrich image prompts with art style
            data["image_prompts"] = _enrich_image_prompts(data["image_prompts"])

            # Ensure we have exactly 5 prompts (pad or trim)
            while len(data["image_prompts"]) < 5:
                data["image_prompts"].append(
                    f"Ancient Indian temple at golden hour, dramatic atmosphere, "
                    f"sacred geometry, divine light rays, {ART_STYLE_SUFFIX}"
                )
            data["image_prompts"] = data["image_prompts"][:5]

            if verbose:
                word_count = len(data["narration"].split())
                print(f"   ✅ Script generated successfully!")
                print(f"   📋 Title: {data['title']}")
                print(f"   📝 Narration: {word_count} words")
                print(f"   🎨 Image prompts: {len(data['image_prompts'])}")

            return data

        except json.JSONDecodeError as e:
            if verbose:
                print(f"   ⚠️  JSON parse error: {e}. Retrying...")
            time.sleep(RETRY_DELAY)

        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                print(f"\n   ❌ Model '{OLLAMA_MODEL}' not found.")
                print(f"   Run: ollama pull {OLLAMA_MODEL}")
                return None
            if verbose:
                print(f"   ⚠️  Ollama error: {e}. Retrying...")
            time.sleep(RETRY_DELAY)

        except Exception as e:
            if verbose:
                print(f"   ⚠️  Unexpected error: {e}. Retrying...")
            time.sleep(RETRY_DELAY)

    print(f"\n   ❌ Failed to generate script after {MAX_RETRIES} attempts.")
    return None


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python brain.py \"<topic>\"")
        print("Example: python brain.py \"Bhagavad Gita Chapter 2, Verse 47\"")
        sys.exit(1)

    topic = " ".join(sys.argv[1:])
    result = generate_script(topic)

    if result:
        print("\n" + "─" * 60)
        print("GENERATED SCRIPT (JSON):")
        print("─" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        sys.exit(1)
