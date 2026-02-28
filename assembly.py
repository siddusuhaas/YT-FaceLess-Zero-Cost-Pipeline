"""
assembly.py — Module 4: Video Assembly with Ken Burns Effect + Dynamic Captions
=================================================================================
Assembles the final YouTube Short (1080×1920, 9:16) from:
  - Audio: output/narration.mp3
  - Images: output/image_0.png ... image_N.png
  - Timestamps: output/timestamps.json

Features:
  - Ken Burns effect (slow zoom/pan) on every image
  - Image swap driven by scene_timing[] from script.json
  - Word-level dynamic captions burned into video center
  - White text with thick black stroke (anti-slop style)
  - Final render: output/final_video.mp4 (H.264, AAC audio)

CHANGES FROM v1:
  - scene_timing[] from script.json is now respected per-image
  - Ken Burns zoom increased from 1.12 → 1.20 (more visible motion)
  - Pan range increased for more dynamic feel
  - Crossfade duration increased from 0.6s → 1.2s (smoother transitions)
"""

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import fadein, fadeout
from moviepy.audio.fx.all import audio_loop, audio_fadeout

# ── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"
FINAL_VIDEO = OUTPUT_DIR / "final_video.mp4"
MUSIC_DIR = Path("assets/music")

# Video specs — YouTube Shorts standard
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Ken Burns settings — increased for visible motion
ZOOM_FACTOR = 1.20        # ✅ FIX: Was 1.12 (12%). Now 1.20 (20% zoom) — much more visible
PAN_RANGE_X = 60          # ✅ FIX: Was 40px. Now 60px
PAN_RANGE_Y = 40          # ✅ FIX: Was 25px. Now 40px

# Image display timing — used only as fallback if no scene_timing provided
MIN_IMAGE_DURATION = 4.0   # seconds
MAX_IMAGE_DURATION = 14.0  # seconds
CROSSFADE_DURATION = 1.2   # ✅ FIX: Was 0.6s. Now 1.2s — smoother crossfades

# Caption styling
CAPTION_FONT_SIZE = 72
CAPTION_Y_POSITION = 0.75  # 75% from top (bottom-center area)
CAPTION_STROKE_WIDTH = 6
CAPTION_COLOR = (255, 255, 255)       # White
CAPTION_STROKE_COLOR = (0, 0, 0)      # Black
CAPTION_BG_ALPHA = 140                # Semi-transparent background (0-255)
CAPTION_BG_PADDING = 20              # Pixels of padding around text


# ── Font Loading ──────────────────────────────────────────────────────────────

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold font, falling back through common system fonts."""
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/SFNSDisplay-Bold.otf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Image Preprocessing ───────────────────────────────────────────────────────

def _prepare_image(image_path: Path) -> np.ndarray:
    """
    Load and resize image to fill the video canvas (cover mode).
    Returns numpy array of shape (VIDEO_HEIGHT, VIDEO_WIDTH, 3).
    """
    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size

    target_w = int(VIDEO_WIDTH * ZOOM_FACTOR) + PAN_RANGE_X * 2
    target_h = int(VIDEO_HEIGHT * ZOOM_FACTOR) + PAN_RANGE_Y * 2

    scale = max(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    img_array = np.array(img)
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    return img_array


# ── Ken Burns Effect ──────────────────────────────────────────────────────────

class KenBurnsClip(VideoClip):
    """
    Custom VideoClip that applies Ken Burns (slow zoom + pan) effect.
    """
    def __init__(self, img_array: np.ndarray, duration: float, direction: int = 0):
        super().__init__()
        self.img = img_array
        self.duration = duration
        self.fps = VIDEO_FPS

        self.src_h, self.src_w = img_array.shape[:2]

        directions = [
            (1.0, ZOOM_FACTOR, 0, PAN_RANGE_X, 0, PAN_RANGE_Y),        # zoom in, pan right+down
            (ZOOM_FACTOR, 1.0, PAN_RANGE_X, 0, PAN_RANGE_Y, 0),        # zoom out, pan left+up
            (1.0, ZOOM_FACTOR, PAN_RANGE_X, 0, 0, PAN_RANGE_Y),        # zoom in, pan left+down
            (ZOOM_FACTOR, 1.0, 0, PAN_RANGE_X, PAN_RANGE_Y, 0),        # zoom out, pan right+up
            (1.0, ZOOM_FACTOR, 0, 0, PAN_RANGE_Y, 0),                   # zoom in, pan up only
            (ZOOM_FACTOR, 1.0, 0, 0, 0, PAN_RANGE_Y),                   # zoom out, pan down only
            (1.0, ZOOM_FACTOR, PAN_RANGE_X // 2, PAN_RANGE_X, 0, PAN_RANGE_Y),  # diagonal
            (ZOOM_FACTOR, 1.0, PAN_RANGE_X, PAN_RANGE_X // 2, PAN_RANGE_Y, 0),  # diagonal reverse
        ]
        self.start_z, self.end_z, self.spx, self.epx, self.spy, self.epy = directions[direction % len(directions)]

    def make_frame(self, t: float) -> np.ndarray:
        """Generate a single frame at time t with Ken Burns transform."""
        progress = t / self.duration

        zoom = self.start_z + (self.end_z - self.start_z) * progress
        pan_x = int(self.spx + (self.epx - self.spx) * progress)
        pan_y = int(self.spy + (self.epy - self.spy) * progress)

        crop_w = int(VIDEO_WIDTH / zoom)
        crop_h = int(VIDEO_HEIGHT / zoom)

        center_x = self.src_w // 2 + pan_x
        center_y = self.src_h // 2 + pan_y

        x1 = max(0, center_x - crop_w // 2)
        y1 = max(0, center_y - crop_h // 2)
        x2 = min(self.src_w, x1 + crop_w)
        y2 = min(self.src_h, y1 + crop_h)

        if x2 - x1 < crop_w:
            x1 = max(0, x2 - crop_w)
        if y2 - y1 < crop_h:
            y1 = max(0, y2 - crop_h)

        cropped = self.img[y1:y2, x1:x2]
        frame_img = Image.fromarray(cropped).resize(
            (VIDEO_WIDTH, VIDEO_HEIGHT), Image.BILINEAR
        )
        return np.array(frame_img)


def _make_ken_burns_clip(
    image_path: Path,
    duration: float,
    direction: int = 0,
) -> KenBurnsClip:
    img_array = _prepare_image(image_path)
    return KenBurnsClip(img_array, duration, direction)


# ── scene_timing Helper ───────────────────────────────────────────────────────

def _resolve_image_durations(
    num_images: int,
    audio_duration: float,
    scene_timing: list = None,
) -> list:
    """
    ✅ FIX: Compute per-image durations from scene_timing[] if available.
    Falls back to equal distribution if scene_timing is missing or wrong length.

    Args:
        num_images: Number of images to display
        audio_duration: Total audio duration in seconds
        scene_timing: List of relative weights from script.json (e.g. [3,7,8,10,10,8,7,7])

    Returns:
        List of floats, one duration per image, summing to ~audio_duration
    """
    if scene_timing and len(scene_timing) == num_images and all(t > 0 for t in scene_timing):
        total_weight = sum(scene_timing)
        durations = [
            max(MIN_IMAGE_DURATION, (t / total_weight) * audio_duration)
            for t in scene_timing
        ]
        # Scale to exactly fit audio_duration
        scale = audio_duration / sum(durations)
        durations = [d * scale for d in durations]
        return durations
    else:
        # Fallback: equal distribution
        base = audio_duration / num_images
        clamped = max(MIN_IMAGE_DURATION, min(MAX_IMAGE_DURATION, base))
        return [clamped] * num_images


# ── Caption Frame Renderer ────────────────────────────────────────────────────

def _render_caption_frame(
    text: str,
    frame_size: tuple = (VIDEO_WIDTH, VIDEO_HEIGHT),
) -> np.ndarray:
    """Render a single caption frame as a transparent RGBA numpy array."""
    font = _get_font(CAPTION_FONT_SIZE)

    canvas = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    max_width = int(frame_size[0] * 0.85)
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]

        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    if not lines:
        return np.array(canvas)

    line_metrics = []
    total_h = 0
    max_w = 0
    line_spacing = 10

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_metrics.append((line, w, h))
        max_w = max(max_w, w)
        total_h += h

    total_h += (len(lines) - 1) * line_spacing

    center_x = frame_size[0] // 2
    center_y = int(frame_size[1] * CAPTION_Y_POSITION)
    start_y = center_y - total_h // 2

    bg_x1 = center_x - max_w // 2 - CAPTION_BG_PADDING
    bg_y1 = start_y - CAPTION_BG_PADDING
    bg_x2 = center_x + max_w // 2 + CAPTION_BG_PADDING
    bg_y2 = start_y + total_h + CAPTION_BG_PADDING

    draw.rounded_rectangle(
        [bg_x1, bg_y1, bg_x2, bg_y2],
        radius=15,
        fill=(0, 0, 0, CAPTION_BG_ALPHA)
    )

    stroke_offsets = [
        (-CAPTION_STROKE_WIDTH, -CAPTION_STROKE_WIDTH),
        (0, -CAPTION_STROKE_WIDTH),
        (CAPTION_STROKE_WIDTH, -CAPTION_STROKE_WIDTH),
        (-CAPTION_STROKE_WIDTH, 0),
        (CAPTION_STROKE_WIDTH, 0),
        (-CAPTION_STROKE_WIDTH, CAPTION_STROKE_WIDTH),
        (0, CAPTION_STROKE_WIDTH),
        (CAPTION_STROKE_WIDTH, CAPTION_STROKE_WIDTH),
    ]

    current_y = start_y
    for line, w, h in line_metrics:
        x = center_x - w // 2

        for ox, oy in stroke_offsets:
            draw.text(
                (x + ox, current_y + oy),
                line,
                font=font,
                fill=(*CAPTION_STROKE_COLOR, 255)
            )

        draw.text((x, current_y), line, font=font, fill=(*CAPTION_COLOR, 255))
        current_y += h + line_spacing

    return np.array(canvas)


# ── Caption Clip Builder ──────────────────────────────────────────────────────

def _build_caption_clips(
    caption_chunks: list,
    total_duration: float,
) -> list:
    """Build a list of MoviePy ImageClips for each caption chunk."""
    caption_clips = []

    for chunk in caption_chunks:
        text = chunk["text"].strip()
        start = chunk["start"]
        end = min(chunk["end"], total_duration)
        duration = end - start

        if duration <= 0 or not text:
            continue

        frame_rgba = _render_caption_frame(text)
        frame_rgb = frame_rgba[:, :, :3]
        frame_alpha = frame_rgba[:, :, 3] / 255.0

        caption_clip = (
            ImageClip(frame_rgb, ismask=False)
            .set_start(start)
            .set_duration(duration)
            .set_opacity(1.0)
        )

        mask_clip = ImageClip(frame_alpha, ismask=True).set_duration(duration)
        caption_clip = caption_clip.set_mask(mask_clip).set_start(start)

        caption_clips.append(caption_clip)

    return caption_clips


# ── Main Assembly Function ────────────────────────────────────────────────────

def assemble_video(
    image_paths: list,
    audio_path: Path,
    caption_chunks: list,
    scene_timing: list = None,       # ✅ FIX: New parameter — accepts scene_timing from script
    output_path: Path = FINAL_VIDEO,
    verbose: bool = True,
) -> Optional[Path]:
    """Assemble the final YouTube Short video."""
    if verbose:
        print(f"\n🎬 [assembly.py] Assembling final video...")
        print(f"   Canvas: {VIDEO_WIDTH}×{VIDEO_HEIGHT} @ {VIDEO_FPS}fps")
        print(f"   Images: {len(image_paths)}")
        print(f"   Captions: {len(caption_chunks)} chunks")
        if scene_timing:
            print(f"   Scene timing: {scene_timing} (from script)")
        else:
            print(f"   Scene timing: equal distribution (no scene_timing in script)")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load Audio
    if verbose:
        print(f"\n   📻 Loading audio: {audio_path}")
    try:
        audio_clip = AudioFileClip(str(audio_path))
        total_duration = audio_clip.duration
        if verbose:
            print(f"   ✅ Audio duration: {total_duration:.1f}s")
    except Exception as e:
        print(f"   ❌ Failed to load audio: {e}")
        return None

    if not image_paths:
        print("   ❌ No images provided for assembly.")
        return None

    num_images = len(image_paths)

    # ✅ FIX: Use scene_timing to compute per-image durations
    image_durations = _resolve_image_durations(num_images, total_duration, scene_timing)

    if verbose:
        print(f"\n   🖼️  Building {num_images} Ken Burns clips...")
        for i, d in enumerate(image_durations):
            print(f"      Image {i+1}: {d:.1f}s")

    # Build Ken Burns Clips
    kb_clips = []
    current_time = 0.0

    for i, img_path in enumerate(image_paths):
        clip_duration = image_durations[i] + CROSSFADE_DURATION

        if verbose:
            print(f"   [{i+1}/{num_images}] Ken Burns on {img_path.name} ({clip_duration:.1f}s, dir={i%8})...")

        try:
            kb_clip = _make_ken_burns_clip(
                image_path=img_path,
                duration=clip_duration,
                direction=i,
            )
            kb_clip = kb_clip.set_fps(VIDEO_FPS)

            if i > 0:
                kb_clip = fadein(kb_clip, CROSSFADE_DURATION)
            if i < num_images - 1:
                kb_clip = fadeout(kb_clip, CROSSFADE_DURATION)

            kb_clip = kb_clip.set_start(current_time)
            kb_clips.append(kb_clip)

        except Exception as e:
            print(f"   ⚠️  Ken Burns failed for image {i+1}: {e}")
            try:
                img_array = _prepare_image(img_path)
                static_clip = (
                    ImageClip(img_array[:VIDEO_HEIGHT, :VIDEO_WIDTH])
                    .set_duration(clip_duration)
                    .set_start(current_time)
                )
                kb_clips.append(static_clip)
            except Exception as e2:
                print(f"   ❌ Static fallback also failed: {e2}")

        current_time += image_durations[i]

    if not kb_clips:
        print("   ❌ No video clips could be created.")
        return None

    if verbose:
        print(f"\n   🎞️  Compositing background clips...")

    background = CompositeVideoClip(kb_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    background = background.set_duration(total_duration)

    if verbose:
        print(f"   💬 Building {len(caption_chunks)} caption overlays...")

    caption_clips = _build_caption_clips(caption_chunks, total_duration)

    if verbose:
        print(f"   ✅ {len(caption_clips)} caption clips created")

    all_clips = [background] + caption_clips
    final_video = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

    # ── Background Music Mixing ───────────────────────────────────────────────
    final_audio = audio_clip

    if MUSIC_DIR.exists():
        import random
        music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))

        if music_files:
            music_path = random.choice(music_files)
            if verbose:
                print(f"   🎵 Adding background music: {music_path.name}")

            try:
                bg_music = AudioFileClip(str(music_path))

                if bg_music.duration < total_duration:
                    bg_music = audio_loop(bg_music, duration=total_duration)
                else:
                    bg_music = bg_music.subclip(0, total_duration)

                bg_music = bg_music.volumex(0.15)
                bg_music = audio_fadeout(bg_music, 2.0)

                final_audio = CompositeAudioClip([audio_clip, bg_music])
            except Exception as e:
                print(f"   ⚠️  Failed to mix background music: {e}")

    final_video = final_video.set_audio(final_audio)
    final_video = final_video.set_duration(total_duration)

    # Render to File
    if verbose:
        print(f"\n   🔄 Rendering final video to {output_path}...")
        print(f"   ⏳ This may take 2-5 minutes depending on video length...")

    render_start = time.time()
    try:
        final_video.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            ffmpeg_params=[
                "-crf", "18",
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
            ],
            threads=4,
            logger=None if not verbose else "bar",
        )

        render_elapsed = time.time() - render_start

        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            if verbose:
                print(f"\n   ✅ Video rendered in {render_elapsed:.1f}s")
                print(f"   📁 Output: {output_path} ({size_mb:.1f} MB)")
                print(f"   📐 Specs: {VIDEO_WIDTH}×{VIDEO_HEIGHT}, {VIDEO_FPS}fps, {total_duration:.1f}s")
            return output_path
        else:
            print("   ❌ Output file was not created.")
            return None

    except Exception as e:
        print(f"   ❌ Video rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        try:
            audio_clip.close()
            final_video.close()
        except Exception:
            pass


if __name__ == "__main__":
    print("🎬 assembly.py — Testing with existing output files...")

    missing = []
    if not AUDIO_FILE.exists():
        missing.append(str(AUDIO_FILE))
    if not TIMESTAMPS_FILE.exists():
        missing.append(str(TIMESTAMPS_FILE))

    image_files = sorted(OUTPUT_DIR.glob("image_*.png")) if OUTPUT_DIR.exists() else []
    if not image_files:
        missing.append("output/image_*.png")

    if missing:
        print(f"❌ Missing required files: {', '.join(missing)}")
        sys.exit(1)

    with open(TIMESTAMPS_FILE, "r") as f:
        chunks = json.load(f)

    # Load scene_timing from script.json if present
    script_file = OUTPUT_DIR / "script.json"
    scene_timing = None
    if script_file.exists():
        with open(script_file, "r") as f:
            script_data = json.load(f)
        scene_timing = script_data.get("scene_timing")

    print(f"   Found {len(image_files)} images, {len(chunks)} caption chunks")

    result = assemble_video(
        image_paths=image_files,
        audio_path=AUDIO_FILE,
        caption_chunks=chunks,
        scene_timing=scene_timing,
    )

    if result:
        print(f"\n✅ Video ready: {result}")
    else:
        print("❌ Assembly failed.")
        sys.exit(1)