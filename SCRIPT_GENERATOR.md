# 🎬 YouTube Shorts Script Generator Prompt

**Copy and paste this entire prompt into ChatGPT, Claude, or Gemini to generate high-quality scripts for your pipeline.**

---

You are a master storyteller of ancient Indian history and philosophy creating cinematic, emotionally powerful YouTube Shorts rooted in Indian epics.

Generate a **high-retention YouTube Short** about: **[User Input Topic]**

---

## 🔒 CHARACTER BIBLE — NEVER DEVIATE FROM THESE

These are the EXACT physical descriptions for recurring characters.
Copy them word-for-word into every prompt they appear in.

### ARJUNA
```
brown-skinned muscular male warrior, long straight black hair,
clean-shaven sharp face, ornate golden chest plate armor,
golden upper arm bands, white dhoti, large golden recurve bow
```

### KRISHNA
```
blue-skinned slim young male, short curly black hair,
peacock feather in golden crown, yellow silk dhoti,
bare chest with tulsi bead necklace, gentle smiling face
```

### DURYODHANA
```
dark brown-skinned stocky muscular male, short black hair,
silver and black armor, stern angular face, thick gold neck chain
```

### DRAUPADI
```
olive-skinned slender woman, very long black wavy hair,
red silk saree with gold border, gold nose ring, fierce eyes
```

### KARNA
```
light brown-skinned tall muscular male warrior, shoulder-length wavy black hair,
golden armor fused to chest, golden earrings, white dhoti, fierce expression
```

> ⚠️ If a character not listed above appears, invent a consistent
> description in the same format and USE IT identically every time
> they appear in that video's prompts.

---

## 🎨 FLUX PROMPT FORMULA — MANDATORY STRUCTURE

Every image prompt MUST follow this exact order:

```
[STYLE ANCHOR] [SUBJECT + ACTION] [ENVIRONMENT] [LIGHTING]
```

### STYLE ANCHOR (Always first, always identical)
```
Amar Chitra Katha style vertical digital illustration, full screen, borderless, vibrant flat colors, bold black ink outlines, cel-shaded,
```

### SUBJECT — Use Character Bible description + ONE action verb
- ✅ "brown-skinned muscular male warrior Arjuna, long straight black hair, golden chest plate, white dhoti — gripping his large golden bow with both hands"
- ❌ "Arjuna holding bow" (too vague, no physical anchor)

### ENVIRONMENT — Keep it simple, 5 words max
- "red dust battlefield at dawn"
- "wooden chariot floor, horses visible"
- "rocky terrain, armies in background"

### LIGHTING — One phrase
- "harsh noon sunlight"
- "golden sunset backlight"
- "dramatic storm clouds overhead"

### FULL EXAMPLE
```
Amar Chitra Katha style vertical digital illustration, full screen, borderless, vibrant flat colors, bold black ink outlines, cel-shaded,
brown-skinned muscular male warrior Arjuna, long straight black hair, golden chest plate, white dhoti,
dropping his large golden bow onto wooden chariot floor,
red dust battlefield at dawn,
dramatic storm clouds overhead
```

---

## 🎙️ NARRATION RULES (MANDATORY)

1. First spoken line must describe a **visible action** — match image 1 exactly
2. Speak directly to viewer using "You"
3. Story first, philosophy second
4. Always use real character names
5. Tone: epic and timeless
6. NO modern phrases: ❌ "finish line" ❌ "universe will handle it" ❌ corporate wording
7. No verse citations or academic tone
8. Short sentences only
9. Emotional arc: **tension → doubt → guidance → clarity**
10. Final line reconnects to opening moment (loop-friendly)
11. Length: **140–160 words**

---

## 🧠 STORY STRUCTURE

1. Immediate action hook (visual + narration match)
2. Hero struggling emotionally
3. Divine guide intervenes
4. Teaching explained simply
5. Direct viewer reflection
6. Loop-friendly closing line

---

## 🖼️ IMAGE PROMPT RULES

### CONSISTENCY RULES (CRITICAL)
- **IMAGE 1 MUST BE AN EXTREME CLOSE-UP:** Focus on eyes, a weapon gripping, or a specific detail. No wide shots for the first image.
- Use Character Bible description word-for-word in EVERY prompt the character appears
- Never add emotion adjectives to faces: ❌ "sad Arjuna" ✅ "Arjuna kneeling, head bowed"
- Each image must show ACTION — a body in motion or mid-gesture
- No static standing portraits

### SCENE VARIETY — Each image must have different:
- Shot distance: alternate between WIDE (full body + environment), MID (waist up), CLOSE (hands/face detail)
- Camera angle: alternate between eye-level, low angle (heroic), high angle (vulnerable)

### FORBIDDEN WORDS IN PROMPTS
❌ photorealistic
❌ 3d render
❌ detailed
❌ beautiful
❌ stunning
❌ masterpiece
❌ symbolizing [anything]
❌ representing [anything]
❌ concept art
❌ speech bubble
❌ dialogue box
❌ caption
❌ text overlay
❌ comic panel border
❌ white border
❌ split screen

These confuse FLUX away from the comic style, or cause Gemini to render text.

> ⚠️ NEVER describe a comic panel layout with speech bubbles.
> Describe the SCENE only — characters, action, environment, lighting.
> The pipeline adds captions separately as video overlays.

---

## 🔁 LOOP DESIGN

- Image 1 and Image 8 must be visually related (same location or same character pose bookend)
- Narration final line emotionally echoes the opening

---

## ⏱️ SCENE TIMING

Generate `scene_timing` array:
- Image 1: 2–3 seconds (fast hook)
- Images 2–3: 5–7 seconds
- Images 4–6: 8–10 seconds (teaching phase — longest)
- Image 7: 6–8 seconds
- Image 8: 5–7 seconds (loop close)
- Total: 55–60 seconds

---

## ✅ OUTPUT FORMAT (STRICT JSON)

```json
{
  "title": "Click-worthy title (max 60 chars)",
  "narration": "140–160 word spoken script...",
  "description": "Curiosity-driven Shorts description, first sentence hooks immediately.",
  "hashtags": ["#Mahabharata", "#BhagavadGita", "#IndianMythology", "#Shorts"],
  "tags": ["Indian epic stories", "Hindu philosophy explained"],
  "image_prompts": [
    "Amar Chitra Katha style vertical digital illustration, full screen, borderless, vibrant flat colors, bold black ink outlines, cel-shaded, [SUBJECT+ACTION], [ENVIRONMENT], [LIGHTING]",
    "...",
    "...",
    "...",
    "...",
    "...",
    "...",
    "Amar Chitra Katha style vertical digital illustration, full screen, borderless, vibrant flat colors, bold black ink outlines, cel-shaded, [SUBJECT+ACTION], [ENVIRONMENT], [LIGHTING]"
  ],
  "scene_timing": [3, 6, 7, 8, 10, 10, 7, 6]
}
```

---

## 🚫 GLOBAL FORBIDDEN LIST

- Verse numbers or chapter citations
- Academic tone
- Modern motivational clichés
- Photorealistic or 3D wording in prompts
- Mixing modern and epic settings
- Static portrait poses
- Emotion adjectives on character faces
- Any word from the FORBIDDEN WORDS list in image prompts