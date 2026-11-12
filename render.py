#!/usr/bin/env python3
"""Leonida Daily renderer.

Builds a 1080x1920 Short from a manifest: scene clips + narration audio +
text overlays + word-by-word captions. Everything is free software (FFmpeg,
faster-whisper) so it can run on GitHub Actions at no cost.

Usage: python render.py manifest.json [--out out.mp4] [--words words.json]

--words skips transcription and uses a prepared word-timing file
(list of {"w": "word", "s": start_sec, "e": end_sec}); used for tests.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

W, H, FPS = 1080, 1920, 30


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def fetch(src, dest):
    """Download http(s) URLs; pass local paths through unchanged."""
    if src.startswith("http://") or src.startswith("https://"):
        req = urllib.request.Request(src, headers={"User-Agent": "leonida-render"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
        return dest
    return src


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def build_segment(src, dur, seek, dest):
    """Crop/scale to 1080x1920 @30fps, trim to dur, hold last frame if short."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},fps={FPS},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration={dur}")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(seek), "-i", src,
         "-vf", vf, "-t", str(dur), "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "17", "-pix_fmt", "yuv420p", dest])


def ass_time(t):
    t = max(t, 0)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def bgr(hex_rgb, alpha=0):
    """RRGGBB -> ASS &HAABBGGRR."""
    hex_rgb = hex_rgb.lstrip("#")
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_header(cap):
    font = cap.get("font", "Montserrat")
    line = bgr(cap.get("line_color", "F2EFE9"))
    outline = bgr(cap.get("outline_color", "1A1A1A"))
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{cap.get('font_size', 84)},{line},{line},{outline},&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,60,60,{cap.get('margin_v', 360)},1
Style: Overlay,{font},100,{line},{line},{outline},&H00000000,-1,0,0,0,100,100,0,0,1,6,2,8,40,40,0,1
Style: Box,{font},72,{line},{line},{outline},&H00000000,-1,0,0,0,100,100,0,0,3,18,0,8,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def caption_events(words, cap):
    """Group words into short lines; highlight the active word."""
    per_line = cap.get("words_per_line", 3)
    word_col = bgr(cap.get("word_color", "C8B58A"))
    line_col = bgr(cap.get("line_color", "F2EFE9"))
    events = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        for j, cur in enumerate(chunk):
            start = cur["s"]
            end = chunk[j + 1]["s"] if j + 1 < len(chunk) else cur["e"]
            parts = []
            for k, w in enumerate(chunk):
                txt = w["w"].upper().replace("{", "(").replace("}", ")")
                col = word_col if k == j else line_col
                parts.append("{\\c" + col + "}" + txt)
            events.append(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,"
                + " ".join(parts))
    return events


def overlay_events(scenes):
    """Text overlays from the manifest, positioned in absolute frame time."""
    events = []
    t0 = 0.0
    for sc in scenes:
        for ov in sc.get("texts", []):
            start = t0 + ov.get("start", 0)
            end = start + ov.get("duration", sc["duration"] - ov.get("start", 0))
            style = "Box" if ov.get("box") else "Overlay"
            x = ov.get("x", W // 2)
            y = ov.get("y", 200)
            size = ov.get("size", 100)
            col = bgr(ov.get("color", "F2EFE9"))
            tags = [f"\\an8", f"\\pos({x},{y})", f"\\fs{size}", f"\\c{col}"]
            if ov.get("box"):
                tags.append("\\3c" + bgr(ov["box"]))      # box colour (BorderStyle 3)
                tags.append("\\bord18")
            if ov.get("fade", 0.3):
                f = int(ov.get("fade", 0.3) * 1000)
                tags.append(f"\\fad({f},{f})")
            text = ov["text"].replace("{", "(").replace("}", ")").replace("\n", "\\N")
            events.append(
                f"Dialogue: 1,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
                "{" + "".join(tags) + "}" + text)
        t0 += sc["duration"]
    return events


def transcribe(audio_path, model_name="base.en"):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True, language="en")
    words = []
    for seg in segments:
        for w in seg.words:
            word = w.word.strip()
            if word:
                words.append({"w": word, "s": float(w.start), "e": float(w.end)})
    return words


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    manifest_path = args[0]
    out = "short.mp4"
    words_file = None
    if "--out" in args:
        out = args[args.index("--out") + 1]
    if "--words" in args:
        words_file = args[args.index("--words") + 1]

    with open(manifest_path) as f:
        mf = json.load(f)
    cap = mf.get("captions", {})

    tmp = tempfile.mkdtemp(prefix="ld_")
    audio = fetch(mf["audio"], os.path.join(tmp, "voice.wav"))

    segs = []
    for i, sc in enumerate(mf["scenes"]):
        src = fetch(sc["clip"], os.path.join(tmp, f"clip{i}.mp4"))
        seg = os.path.join(tmp, f"seg{i}.mp4")
        build_segment(src, sc["duration"], sc.get("seek", 0), seg)
        segs.append(seg)

    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    video = os.path.join(tmp, "video.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing, "-c", "copy", video])

    if words_file:
        with open(words_file) as f:
            words = json.load(f)
    elif cap.get("enabled", True):
        words = transcribe(audio, cap.get("model", "base.en"))
    else:
        words = []

    events = overlay_events(mf["scenes"]) + caption_events(words, cap)
    ass_path = os.path.join(tmp, "subs.ass")
    with open(ass_path, "w") as f:
        f.write(ass_header(cap) + "\n".join(events) + "\n")

    total = sum(sc["duration"] for sc in mf["scenes"])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio,
         "-vf", f"ass={ass_path}", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}",
         "-movflags", "+faststart", out])
    print(f"done: {out} ({probe_duration(out):.1f}s)")


if __name__ == "__main__":
    main()
