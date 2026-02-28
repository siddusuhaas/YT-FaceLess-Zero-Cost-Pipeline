"""
brain.py — Module 1: LLM Script Generation
============================================
Uses local Ollama (llama3.2:3b) to generate a structured JSON script
for a documentary-style YouTube Short on Indian history/philosophy.

Output JSON schema:
{
    "title": str,           # Click-worthy YouTube title
    "narration": str,       # Full spoken script (~60 seconds)
    "image_prompts": list   # 8 descriptive art prompts
    "scene_timing": list    # 8 per-image durations in seconds
}

CHANGES FROM v1:
  - enrich_image_prompts() now uses keyword detection instead of exact string match.
    This prevents double-appending style suffixes when prompts come from Gemini,
    which already adds "Amar Chitra Katha" style text.
"""

import json
import time
import subprocess
import sys
import re
from typing import Optional

import ollama

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_MODEL = "llama3.2:3b"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ── Art Style Suffix ──────────────────────────────────────────────────────────
# Appended to every image prompt ONLY IF the prompt doesn't already contain
# comic/style keywords. This prevents double-styling Gemini-generated prompts.
ART_STYLE_SUFFIX = (
    "Amar Chitra Katha comic book style, vibrant digital illustration, "
    "bold black outlines, cel shaded, 2D animation, flat colors, "
    "hindu mythology art, expressive characters, "
    "no photorealism, no shading, no 3d render"
)

# ✅ FIX: Keywords used to detect if a prompt already has a style instruction.
# If ANY of these are found in the prompt, we skip appending the suffix.
STYLE_DETECTION_KEYWORDS = [
    "amar chitra",
    "comic style",
    "comic book",
    "flat colors",
    "bold black outlines",
    "cel shad",
    "2d animation",
    "vibrant flat",
    "vibrant digital",
]

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a master storyteller of ancient Indian history and philosophy. You do not lecture; you transport the listener to the scene.

Your task is to create a cinematic, emotionally resonant YouTube Short script.
- **NO Academic Jargon:** Do not say "In Chapter X, Verse Y" or "The translation is".
- **NO Bookish Tone:** Do not sound like you are reading a textbook.
- **Storytelling First:** Start with a hook. Use active voice. Speak directly to the viewer ("You").
- **Flow:** Use short, punchy sentences. Mix rhythm.
- **Content:** If explaining a verse, weave the meaning naturally into the narrative.

You MUST respond ONLY with a single valid JSON object. No preamble, no markdown code blocks, no explanation outside the JSON. The JSON must have exactly these three keys:

1. "title": A click-worthy, curiosity-driven YouTube title (max 60 characters). Use power words. Example: "The Secret Krishna Revealed Only to Arjuna"

2. "narration": The complete spoken script as a single string. Write it as a documentary narrator would speak — with gravitas, pauses implied by punctuation, and a sense of ancient wisdom being revealed.

3. "image_prompts": An array of exactly 8 strings. Each string is a highly descriptive visual prompt for generating a cartoon-style ancient Indian illustration. Rules: \n   - **FIRST IMAGE MUST BE A HOOK:** An extreme close-up of eyes, a weapon, or intense action. No wide static shots for the first image.\n   - DESCRIBE PIXELS, NOT CONCEPTS. Don't say "symbolizing peace", say "a man sitting under a tree".\n   - Keep it literal. \n   - Focus on characters and action.

4. "scene_timing": An array of exactly 8 integers. Each value represents seconds each corresponding image_prompt should remain on screen.
   - Array length must equal image_prompts length.
   - Total duration must be between 55 and 60 seconds.
   - First scene duration must be 2–3 seconds (fast hook).
   - Middle scenes longer (teaching phase).
   - Final scene 5–7 seconds to enable looping."""

# ── Series Outline Prompt ─────────────────────────────────────────────────────
OUTLINE_SYSTEM_PROMPT = """You are an expert documentary showrunner.
Your task is to break down a broad topic into a compelling {num_parts}-part series.

Return ONLY a JSON object with this structure:
{{ "series_title": "Main Title", "parts": [ {{ "part_number": 1, "title": "Part Title", "summary": "Plot points to cover..." }}, ... ] }}
"""

# ── User Prompt Template ──────────────────────────────────────────────────────
USER_PROMPT_TEMPLATE = """Create a 60-second YouTube Short documentary script about: "{topic}"

Remember:
- The narration must be 140-160 words
- The image_prompts array must have exactly 8 elements
- The scene_timing array must match image_prompts length
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

    if "scene_timing" in data:
        if not isinstance(data["scene_timing"], list):
            return False, "Field 'scene_timing' must be an array"
        if not all(isinstance(x, (int, float)) for x in data["scene_timing"]):
            return False, "Field 'scene_timing' must contain numbers"

    return True, "OK"


def _prompt_already_styled(prompt: str) -> bool:
    """
    ✅ FIX: Check if a prompt already contains style instructions.
    Uses keyword detection instead of exact string match, so it correctly
    identifies Gemini-generated prompts that use slightly different wording.
    """
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in STYLE_DETECTION_KEYWORDS)


def enrich_image_prompts(prompts: list) -> list:
    """
    Append the art style suffix to each image prompt — but ONLY if the prompt
    doesn't already contain style keywords.

    ✅ FIX: Previously used exact string match which always failed for Gemini prompts,
    causing every prompt to get the suffix appended twice with conflicting wording.
    Now uses keyword detection so Gemini prompts are left untouched.
    """
    enriched = []
    for prompt in prompts:
        if _prompt_already_styled(prompt):
            # Already has style instructions (e.g. from Gemini) — leave as-is
            enriched.append(prompt)
        else:
            # No style detected — append our suffix
            enriched.append(f"{prompt.rstrip('. ')}, {ART_STYLE_SUFFIX}")
    return enriched


def generate_script(topic: str, previous_context: str = None, verbose: bool = True) -> Optional[dict]:
    """
    Generate a documentary script for the given topic using Ollama.

    Args:
        topic: The historical/philosophical topic (e.g., "Bhagavad Gita Chapter 2, Verse 47")
        previous_context: Summary of the previous part (for series continuity)
        verbose: Whether to print progress messages

    Returns:
        dict with keys: title, narration, image_prompts, scene_timing
        None if generation fails after all retries
    """
    if verbose:
        print(f"\n🧠 [brain.py] Generating script for: \"{topic}\"")
        print(f"   Model: {OLLAMA_MODEL}")

    if not _ensure_ollama_running():
        return None

    user_prompt = USER_PROMPT_TEMPLATE.format(topic=topic)

    if previous_context:
        user_prompt += f"\n\nCONTEXT FROM PREVIOUS PART (CONTINUE THE STORY): {previous_context}"

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

            if raw_content.startswith("```"):
                lines = raw_content.split("\n")
                raw_content = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )

            data = json.loads(raw_content)

            is_valid, error_msg = _validate_script(data)
            if not is_valid:
                if verbose:
                    print(f"   ⚠️  Invalid structure: {error_msg}. Retrying...")
                time.sleep(RETRY_DELAY)
                continue

            # Enrich image prompts with art style (smart — won't double-apply)
            data["image_prompts"] = enrich_image_prompts(data["image_prompts"])

            # Ensure we have exactly 8 prompts (pad or trim)
            while len(data["image_prompts"]) < 8:
                data["image_prompts"].append(
                    f"Ancient Indian temple, comic book style, vibrant colors, "
                    f"bold lines, {ART_STYLE_SUFFIX}"
                )
            data["image_prompts"] = data["image_prompts"][:8]

            # Sync scene_timing if present
            if "scene_timing" in data and isinstance(data["scene_timing"], list):
                while len(data["scene_timing"]) < 8:
                    data["scene_timing"].append(5)
                data["scene_timing"] = data["scene_timing"][:8]

            if verbose:
                word_count = len(data["narration"].split())
                print(f"   ✅ Script generated successfully!")
                print(f"   📋 Title: {data['title']}")
                print(f"   📝 Narration: {word_count} words")
                print(f"   🎨 Image prompts: {len(data['image_prompts'])}")
                if "scene_timing" in data:
                    print(f"   ⏱️  Scene timing: {data['scene_timing']} (total: {sum(data['scene_timing'])}s)")

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


def generate_series_outline(topic: str, num_parts: int, verbose: bool = True) -> Optional[dict]:
    """Generate a structured outline for a multi-part series."""
    if verbose:
        print(f"\n🧠 [brain.py] Generating outline for {num_parts}-part series: \"{topic}\"")

    if not _ensure_ollama_running():
        return None

    system_prompt = OUTLINE_SYSTEM_PROMPT.format(num_parts=num_parts)
    user_prompt = f"Create a {num_parts}-part outline for: {topic}"

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format="json",
            options={"temperature": 0.7}
        )

        raw_content = response["message"]["content"].strip()

        if raw_content.startswith("```"):
            lines = raw_content.split("\n")
            raw_content = "\n".join(line for line in lines if not line.strip().startswith("```"))

        data = json.loads(raw_content)

        if "parts" not in data or not isinstance(data["parts"], list):
            print("   ❌ Invalid outline format received.")
            return None

        if verbose:
            print(f"   ✅ Outline generated: {len(data['parts'])} parts")

        return data

    except Exception as e:
        print(f"   ❌ Failed to generate outline: {e}")
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