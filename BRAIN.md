# Leonida Daily: BRAIN (read this first in every new chat or scheduled run)

Last updated: 2026-11-12 (evening). Update this file whenever something durable changes.

## Mission
Faceless, AI-run YouTube channel "Leonida Daily" (@leonidaDaily-o3w) about GTA / GTA 6 (launch Nov 19, 2026).
Owner: Altus (Pretoria, SAST). Goal: passive, scalable income. YouTube only, 2 Shorts/day, ~10 min/day human approval, budget under $50/month, monetise ASAP. Narrator voice: Reid (Higgsfield seed_audio, voice_id 66469f5a-10db-586a-bab1-72f6ee66ba69). No Rockstar footage (their policy is non-commercial fan use only).

## Altus's standing rules
- Videos are emailed to him, never "go download from GitHub".
- Verify every fact against primary sources before posting. No obvious or outdated facts (V002 "no disc" was rejected as useless).
- Content must be informative, about interesting GTA topics, creative hook, NOT AI slop.
- Nothing reaches him until the QC analyst gate passes. Do not waste credits.
- Visual direction: DATA EXPLAINER (original motion-graphic cards showing real numbers, comparisons, flows; few topic-specific AI images; no Rockstar/GTA footage).
- Always use current website steps. Only make requested changes. Mobile-friendly docs. Direct, honest critique. He will leave for ChatGPT if quality is bad.

## Daily pipeline
1. Research (Firecrawl + web search; check ld_questions bank) 2. Pick topic with a surprising, verified angle 3. Script + hook 4. Reid voiceover 5. Manifest in manifests/<ID>.json 6. Push, GitHub Action renders 7. QC analyst reads qc/<ID>_sheet.jpg, report and words; fix and re-render up to 2 loops 8. Pass: write approved/<ID>.txt, which emails the video 9. Email Altus title, description with sources, pinned comment, hashtags, thumbnail, facts to verify, post time 10. Altus uploads manually (~17:00 and a second slot) 11. Next day: review stats, update ld_videos / ld_rules / this file.

## Infrastructure
- Repo: VertaFlow-code/leonida-daily-render (main). render.py (FFmpeg + libass + faster-whisper base.en), cards.py (Pillow card scenes), scripts/qc.sh, email_video.py.
- Workflows: render.yml (push manifests/*.json or manual -> render -> pre-release -> QC files committed). email.yml (push approved/*.txt -> emails latest release asset, compressed ~4 Mbps, via Gmail SMTP secrets MAIL_USER, MAIL_APP_PASSWORD).
- Manifest: scenes with clip URL or {"type":"card","layout":stat|versus|flow|list|cta,...}; `fit_audio:true` makes scene `duration` relative weights (word counts) and text start/duration fractions of the scene; `script` = correct caption text aligned onto whisper timings.
- Git proxy quirk: `git fetch origin main` only updates FETCH_HEAD; poll with `git ls-tree -r FETCH_HEAD --name-only`.
- n8n data tables (project xjrP1PEnZuz1gS6w): ld_videos w2UlIfmWIURizsTO, ld_rules qPqo6QH1L71ifiLi, ld_questions tvy5NmD0cl8dZtG2. No row-update tool: add new rows.
- Higgsfield Plus: ~900 credits left. seed_audio for Reid; gpt_image_2_6 ~0.25 cr/image; grok_video_v15_lite 5 cr per 5 s (avoid, data-explainer needs little video). Sandbox can't download CloudFront result URLs.
- Scheduled task trig_018ZSMnycvgxaJ6GKEc733uP daily 07:31 SAST (cloud, auto approval). It reads VISUAL_STYLE.md and this file.
- Gmail connector sends from Altusbantjes@vertaflows.com to altusbantjes16@gmail.com. YouTube uploads stay manual.

## Status
- V001: posted (https://youtube.com/shorts/8f5-NEXPZjk).
- V002 ("no disc"): rejected. Do not post.
- V003 "An Xbox One can't install GTA 6, it's getting it day one anyway": rendered (42 s), QC gate passed after 1 loop, video and approval pack emailed 2026-11-12. Awaiting Altus upload (post tonight ~20:00 SAST). Sources: Xbox Wire 10 Nov, Rockstar Newswire 10 Nov and 3 Nov. After posting: log in ld_videos, check stats next day.
- cards.py (7 layouts) and variety_check.py are in the repo and used by render.yml. Montserrat only exists on the runner, so local previews use DejaVu.

## Upgrades added 2026-11-12 (all 8 picked by Altus)
1. DONE: layout-variety + sourcing guardrail (scripts/variety_check.py, runs before render, writes qc/<id>_variety.json).
2. PARTLY: hook rules. A real teardown of top GTA 6 Shorts needs outlier mining (item 5); vendor blogs (vidIQ, faceless.so) are weak sources. Provisional rules: lead with a rule/question/contrast, first spoken line short, title makes the same promise as the hook.
3. DONE in renderer, not used yet: weekly long-form via manifest "format":"wide". Check seed_audio cost per minute before the first one (V003's 90 words cost 4.1 credits).
4. BLOCKED on Altus: analytics feedback loop needs YouTube Analytics API OAuth. Until then he sends a stats screenshot next day.
5. SCRIPT READY, untested: scripts/yt_outliers.py needs a free YT_API_KEY. Do not add search-heavy use: quota default is 10,000 units/day with a 100 search.list/day cap per the Data API page (verify on the Quotas page).
6. Batch + scheduled uploads: Altus uploads the day's 2 Shorts in one sitting and uses the Schedule card in YouTube Studio (Create > Upload videos > Schedule). Uploads stay manual.
7. DONE: audio_fx in manifest (synthesized SFX ticks on cuts), tighten_pauses to cut sentence gaps to 0.28 s. Music bed is opt-in only.
8. TODO Altus: confirm the channel sits on its own Brand Account/Google account, separate from his personal/business accounts.

## YouTube policy facts (press sources, re-verify on YouTube pages before relying)
YPP: 1,000 subs + 4,000 watch hours or 10M Shorts views in 90 days. From 1 Feb 2027 new applicants need 8,000 hours or 20M Shorts views. Fan-funding tier (500 subs, 3 uploads, 3,000 hours or 3M Shorts views). Shorts hours do not count toward long-form hours. July 2026: no monetisation for generic, repetitive, template-based content. Realistic: apply before 1 Feb 2027 if thresholds are near, otherwise plan for the higher bar.

## Daily schedule (SAST)
07:31 scheduled task researches, builds and QC-gates Short(s), emails video + approval pack. Altus: approve in the morning (about 3 min each), upload both in one sitting using Schedule (e.g. 17:00 and 20:00). Next day: send stats screenshot (or automatic once item 4 is done).

## Topic backlog (verify each before use)
Map size vs earlier games; file size smaller in Australia/Japan; Miami IRL event; Rockstar recreated viral Miami clip; 30 FPS debate; Q-bank (ld_questions) has the ~50 most-asked questions.

## Rules learned (R017-R023 summary)
Primary sources beat SEO sites (they conflict on preload dates). Single-source claims are not allowed. Hook must carry a surprise within 2 seconds. No stock/AI filler visuals. Captions use the written script, not raw whisper. Keep content out of caption/UI zones (y about 180-1350).

## Open items
Narrow Claude GitHub app access to selected repos; analytics screenshot routine; day-14 checkpoint; day-60 shutdown/pivot review; YPP application when eligible.
