# Leonida Daily visual style (read with BRAIN.md)

Data-explainer Shorts: original motion-graphic cards, no Rockstar footage.

- Cards (cards.py): stat, versus, flow, list, bars, timeline, cta. Themes ink/paper/slate/ember and motifs are picked per video from the video id, so Shorts do not all look the same. Override with card_theme / card_motif.
- Every data card carries a "source". Manifest needs 2+ "sources". Enforced by scripts/variety_check.py (no layout 3 times in a row, max 50% one layout, 3+ layouts when 4+ cards).
- 5-7 cards, 35-45 s. Hook card in the first 2 s must carry the surprise. End with a cta card.
- Keep content between y 180 and 1340. Captions sit at margin_v 360 (Montserrat 84, word colour C8B58A).
- Audio: Reid voice, `tighten_pauses: true`, `audio_fx: {"sfx": true}` (synthesized ticks on scene cuts). Music bed only if Altus approves a licensed track (not heard by me, so opt-in).
- Wide 16:9 long-form: manifest `"format": "wide"` (1920x1080). Not yet used.
- Do not make every Short the same shape. YouTube's July 2026 policy bars monetisation of repetitive, template-based content, so vary topic angle, layout order and theme.

## Scene art (added 2026-11-12, Altus wants a GTA 6 feel)
Cards can sit on an original illustration: add "image": "<url>" (and optional "image_dim", default 0.62) to a card scene. cards.py cover-fits it, pans/zooms slowly and darkens it so text stays readable. Use it on 3-4 of 6 cards per Short (hook card and payoff card always), plain card backgrounds for the rest.
- Generate with Higgsfield generate_image (gpt_image_2_6, 9:16, about 0.25 credits each). Prompt pattern: "original illustration, neon-lit Miami-style street at dusk, palm trees, retro convertible, pink and teal sky, cinematic, no text, no logos, no real people, not from any video game". Vary subject per card (beach strip, marina, swamp airboat, highway at night, rain storm over a skyline).
- The vibe is Florida neon, not a copy of the game. NEVER use Rockstar footage, screenshots, trailer frames, logos, or Jason/Lucia likenesses, and never describe an image as gameplay. Rockstar's fan-content policy is non-commercial and the channel is monetised; real footage also risks a "reused content" strike. Only Altus can accept that risk, in writing in ld_rules.
- The sandbox cannot download Higgsfield result URLs, so pass the CloudFront URL straight into the manifest; the GitHub runner downloads it.
