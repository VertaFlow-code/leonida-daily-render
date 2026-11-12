#!/usr/bin/env bash
# Usage: scripts/qc.sh VIDEO_ID video.mp4
# Writes qc/<id>_sheet.jpg (frame contact sheet), qc/<id>_report.json (technical checks)
# and qc/<id>_words.json (what the narration actually says, with timings).
set -euo pipefail
id="$1"; mp4="$2"
mkdir -p qc
ffmpeg -y -loglevel error -i "$mp4" -vf "fps=1/1.5,scale=360:-2,tile=4x4" -frames:v 1 -q:v 3 "qc/${id}_sheet.jpg"
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$mp4")
size=$(stat -c %s "$mp4")
black=$(ffmpeg -nostats -i "$mp4" -vf blackdetect=d=0.2:pix_th=0.10 -an -f null - 2>&1 | grep -c black_start || true)
silence=$(ffmpeg -nostats -i "$mp4" -af silencedetect=n=-35dB:d=1.0 -vn -f null - 2>&1 | grep -c silence_start || true)
cat > "qc/${id}_report.json" <<JSON
{"video_id":"$id","duration_sec":$dur,"size_bytes":$size,"black_segments":$black,"long_silences":$silence}
JSON
[ -f "${mp4}.words.json" ] && cp "${mp4}.words.json" "qc/${id}_words.json" || true
echo "QC written for $id"
