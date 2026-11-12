#!/usr/bin/env python3
"""Email a rendered Short to the owner (free, via Gmail SMTP + app password).

Usage: python email_video.py VIDEO_ID path/to.mp4 release_url
Env:   MAIL_USER, MAIL_APP_PASSWORD, MAIL_TO (optional, defaults to MAIL_USER)
Makes a smaller copy (~4 Mbps) so the message stays under Gmail's 25 MB cap.
"""
import os
import smtplib
import subprocess
import sys
from email.message import EmailMessage

vid, path, url = sys.argv[1], sys.argv[2], sys.argv[3]
user = os.environ.get("MAIL_USER", "").strip()
pw = os.environ.get("MAIL_APP_PASSWORD", "").replace(" ", "").strip()
to = os.environ.get("MAIL_TO", "").strip() or user
if not user or not pw:
    print("MAIL_USER / MAIL_APP_PASSWORD not set - skipping email")
    sys.exit(0)

small = f"{vid}_email.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path,
                "-c:v", "libx264", "-b:v", "4000k", "-maxrate", "4500k",
                "-bufsize", "8000k", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", small],
               check=True)
size_mb = os.path.getsize(small) / 1e6
print(f"email copy: {size_mb:.1f} MB")

msg = EmailMessage()
msg["From"] = user
msg["To"] = to
msg["Subject"] = f"Leonida Daily - {vid} video ready"
msg.set_content(
    f"{vid} has finished rendering and is attached ({size_mb:.1f} MB).\n\n"
    f"Full-quality file: {url}\n\n"
    "Thumbnail attached too (9:16). YouTube only lets you add a custom Shorts thumbnail in\n"
    "YouTube Studio on a computer (Content > Shorts > edit > Upload file).\n\n"
    "Watch it, verify the facts in the approval pack email, then upload.\n")
with open(small, "rb") as f:
    msg.add_attachment(f.read(), maintype="video", subtype="mp4",
                       filename=f"{vid}.mp4")
thumb = f"thumbs/{vid}.jpg"
if os.path.exists(thumb):
    with open(thumb, "rb") as f:
        msg.add_attachment(f.read(), maintype="image", subtype="jpeg", filename=f"{vid}_thumbnail.jpg")
    print("thumbnail attached")
with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=120) as s:
    s.login(user, pw)
    s.send_message(msg)
print("emailed", to)
