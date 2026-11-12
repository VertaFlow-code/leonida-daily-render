# Leonida Daily visual style (read with BRAIN.md)

Data-explainer Shorts: original motion-graphic cards, no Rockstar footage.

- Cards (cards.py): stat, versus, flow, list, bars, timeline, cta. Themes ink/paper/slate/ember and motifs are picked per video from the video id, so Shorts do not all look the same. Override with card_theme / card_motif.
- Every data card carries a "source". Manifest needs 2+ "sources". Enforced by scripts/variety_check.py (no layout 3 times in a row, max 50% one layout, 3+ layouts when 4+ cards).
- 5-7 cards, 35-45 s. Hook card in the first 2 s must carry the surprise. End with a cta card.
- Keep content between y 180 and 1340. Captions sit at margin_v 360 (Montserrat 84, word colour C8B58A).
- Audio: Reid voice, `tighten_pauses: true`, `audio_fx: {"sfx": true}` (synthesized ticks on scene cuts). Music bed only if Altus approves a licensed track (not heard by me, so opt-in).
- Wide 16:9 long-form: manifest `"format": "wide"` (1920x1080). Not yet used.
- Do not make every Short the same shape. YouTube's July 2026 policy bars monetisation of repetitive, template-based content, so vary topic angle, layout order and theme.
