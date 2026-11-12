# leonida-daily-render

Free renderer for the Leonida Daily Shorts. A GitHub Actions workflow turns a JSON
manifest (scene clips, narration audio, text overlays) into a 1080x1920 MP4 with
word-by-word captions, using only FFmpeg and faster-whisper.

Run it: Actions -> "Render Short" -> Run workflow -> paste a manifest (see
`examples/v001.json`). The MP4 is published as a pre-release on this repo.

Never commit secrets. Rendered videos are published in this public repo, so only
render content that is safe to be public.
