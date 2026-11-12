#!/usr/bin/env python3
"""Leonida Daily renderer.

Builds a 1080x1920 Short (or 1920x1080 when manifest "format" is "wide") from a manifest: scene clips + narration audio +
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

import cards

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
    stretch = ""
    try:
        cd = probe_duration(src) - seek
        if cd > 0.5 and dur > cd:
            stretch = f"setpts={min(dur / cd, 1.5):.4f}*PTS,"
    except Exception:
        pass
    vf = (f"{stretch}scale={W}:{H}:force_original_aspect_ratio=increase,"
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
    import numpy as np
    from faster_whisper import WhisperModel
    # Decode with FFmpeg (16 kHz mono float32) so we never depend on PyAV.
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", audio_path, "-f", "f32le",
         "-ac", "1", "-ar", "16000", "-"],
        check=True, capture_output=True).stdout
    samples = np.frombuffer(raw, dtype=np.float32)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(samples, word_timestamps=True, language="en")
    words = []
    for seg in segments:
        for w in seg.words:
            word = w.word.strip()
            if word:
                words.append({"w": word, "s": float(w.start), "e": float(w.end)})
    return words


def align_script(words, script):
    """Show the written script (correct spelling) on the whisper timings."""
    import difflib
    import re
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    st = script.split()
    if not words or not st:
        return words
    sm = difflib.SequenceMatcher(
        None, [norm(w["w"]) for w in words], [norm(t) for t in st], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                w = dict(words[i1 + k])
                w["w"] = st[j1 + k]
                out.append(w)
        elif tag == "replace":
            span, toks = words[i1:i2], st[j1:j2]
            a0, a1 = span[0]["s"], span[-1]["e"]
            step = (a1 - a0) / len(toks)
            for k, t in enumerate(toks):
                out.append({"w": t, "s": a0 + k * step, "e": a0 + (k + 1) * step})
        elif tag == "insert":
            base = out[-1]["e"] if out else 0.0
            for k, t in enumerate(st[j1:j2]):
                out.append({"w": t, "s": base + 0.05 * k, "e": base + 0.05 * (k + 1)})
    return out


def audio_fx(mf, audio, total, tmp):
    """Voice plus optional synthesized SFX and an opt-in music bed.

    manifest "audio_fx": {"sfx": true, "sfx_volume": 0.22, "music": "<url|path>", "music_volume": 0.07}
    SFX are tiny ffmpeg-synthesized ticks on card/scene changes, so there is no licensing to worry about.
    Music is only used when a URL/path is given (never by default).
    """
    fx = mf.get("audio_fx") or {}
    extra, parts, labels = [], [], ["[1:a]"]
    n = 2
    if fx.get("sfx"):
        vol = fx.get("sfx_volume", 0.22)
        t = 0.0
        for i, sc in enumerate(mf["scenes"]):
            if i > 0:
                ms = int(t * 1000)
                extra += ["-f", "lavfi", "-t", "0.16", "-i", "sine=frequency=620:sample_rate=48000"]
                parts.append(f"[{n}:a]afade=t=out:st=0.02:d=0.14,volume={vol},adelay={ms}|{ms}[s{n}]")
                labels.append(f"[s{n}]")
                n += 1
            t += sc["duration"]
    if fx.get("music"):
        src = fetch(fx["music"], os.path.join(tmp, "bed.mp3")) if str(fx["music"]).startswith("http") else fx["music"]
        extra += ["-stream_loop", "-1", "-i", src]
        parts.append(f"[{n}:a]volume={fx.get('music_volume', 0.07)},afade=t=in:d=1.5[m{n}]")
        labels.append(f"[m{n}]")
        n += 1
    if len(labels) == 1:
        return extra, "[1:a]anull[a]"
    graph = ";".join(parts) + (";" if parts else "")
    graph += "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,apad[a]"
    return extra, graph


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
    global W, H
    if mf.get("format") == "wide":
        W, H = 1920, 1080
        cap = dict(cap)
        cap.setdefault("font_size", 64)
        cap.setdefault("margin_v", 120)
    vid_id = mf.get("id") or os.path.splitext(os.path.basename(manifest_path))[0]
    theme = mf.get("card_theme")
    motif = mf.get("card_motif")
    card_log = []

    tmp = tempfile.mkdtemp(prefix="ld_")
    audio = fetch(mf["audio"], os.path.join(tmp, "voice.wav"))
    if mf.get("tighten_pauses"):
        # shorten every pause longer than ~0.5s down to 0.28s so the pace stays Shorts-tight
        tight = os.path.join(tmp, "voice_tight.wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio, "-af",
             "silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-38dB:stop_silence=0.28",
             tight])
        print(f"tightened pauses: {probe_duration(audio):.1f}s -> {probe_duration(tight):.1f}s", flush=True)
        audio = tight

    if mf.get("fit_audio"):
        # scene "duration" values are relative weights (e.g. word counts);
        # text "start"/"duration" are fractions of their scene.
        target = probe_duration(audio) + mf.get("tail", 0.5)
        total_w = sum(sc["duration"] for sc in mf["scenes"])
        for sc in mf["scenes"]:
            sc["duration"] = round(target * sc["duration"] / total_w, 2)
            for ov in sc.get("texts", []):
                f0 = ov.get("start", 0.0)
                f1 = ov.get("duration", 1.0 - f0)
                ov["start"] = round(f0 * sc["duration"], 2)
                ov["duration"] = round(f1 * sc["duration"], 2)
        print("scene durations:", [sc["duration"] for sc in mf["scenes"]], flush=True)

    segs = []
    for i, sc in enumerate(mf["scenes"]):
        seg = os.path.join(tmp, f"seg{i}.mp4")
        if sc.get("type") == "card":
            if str(sc.get("image", "")).startswith("http"):
                sc = dict(sc, image=fetch(sc["image"], os.path.join(tmp, f"art{i}.jpg")))
            info = cards.render_card_scene(sc, sc["duration"], seg, W, H, FPS, theme, motif, vid_id)
            card_log.append(info)
        else:
            src = fetch(sc["clip"], os.path.join(tmp, f"clip{i}.mp4"))
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

    if mf.get("script") and words:
        words = align_script(words, mf["script"])
    try:
        with open(out + ".words.json", "w") as f:
            json.dump(words, f)
    except Exception:
        pass
    events = overlay_events(mf["scenes"]) + caption_events(words, cap)
    ass_path = os.path.join(tmp, "subs.ass")
    with open(ass_path, "w") as f:
        f.write(ass_header(cap) + "\n".join(events) + "\n")

    total = sum(sc["duration"] for sc in mf["scenes"])
    extra_in, graph = audio_fx(mf, audio, total, tmp)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio] + extra_in +
        ["-filter_complex", f"[0:v]ass={ass_path}[v];{graph}", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}",
         "-movflags", "+faststart", out])
    print(f"done: {out} ({probe_duration(out):.1f}s)")


if __name__ == "__main__":
    main()
