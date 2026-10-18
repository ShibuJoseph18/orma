# Orma LinkedIn capture

Independent, ingestion-only Chrome extension, informed by Linkosh's LinkedIn provider and observations from our saved-list captures: https://github.com/sabyasachi/linkosh . Original Linkosh remains untouched. No third-party code or packages bundled.

## Run

Use Windows Chrome, signed into LinkedIn. Open chrome://extensions, enable Developer mode, choose Load unpacked, and select:

`\\wsl$\Ubuntu\home\shibu\cs\hackathons\orma\tools\orma-capture`

Click the extension icon to open a full tab. Choose a positive post count, leave post-page inspection enabled for media discovery, and click Capture latest saved posts. Expand a result to inspect the fields, or Export JSON. Stop preserves partial results. Keep the tab open during capture. No database, embedding model, server, or package installation is needed.

## Ordering and limits

Uses ordered `*entityResult` references, never the unordered `included` array. Starts at offset zero every run. Deduplicates across pages and truncates precisely to the chosen count. Continues beyond the old 100-post limit until requested count, empty results, repeated page, cancellation or error. Empty/repeated pages do not prove all saves were returned. Missing ordered references cause an error instead of guessed ordering. Exact saved timestamps are unavailable. The order reflects LinkedIn's saved-list API: concurrent saves/unsaves can shift pagination, so it is not an atomic snapshot. Do not sort by publication dates or author.

## What is captured

Source URL, author, saved-list text, source page, saved-list position, embedded attachment titles, image variants and playable-preview indicators. Optional post-page inspection collects available Open Graph and JSON-LD metadata and media references. It does not execute the fetched page's scripts. Login walls and failed requests are reported per item.

Photos, videos and document posts remain in the results even when their attachment payloads are unavailable. A preview is not original media; a video URL may be a player rather than a downloadable stream. Full video/audio, transcript, OCR, carousel pages and PDF extraction are NOT implemented. Extraction fields make these gaps explicit. Future enrichment must obtain usable assets and process them temporarily before sending derived knowledge/evidence to FalkorDB.

## Data handling

Only LinkedIn host access and cookies permissions. Reads the CSRF cookie in memory; browser sends its own authenticated cookies. No session cookies are exported or sent to an Orma server. Results exist in tab memory; JSON export is an explicit local file. No third-party requests, SQLite or embeddings. Existing Linkosh exports are not modified. LinkedIn internal API query IDs can change; this is a prototype, not an official integration.

## Verification

Run `node --test tools/orma-capture/parser.test.mjs`. Replay historical response fixtures with `python3 tools/orma-capture/replay.py`; this reads the previous Linkosh SQLite export solely as a test fixture, not runtime storage, and writes a JSON preview. Live capture requires loading this extension into Windows Chrome; fixture replay does not verify fresh network access or media downloads.
