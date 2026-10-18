# Linkosh: Orma ingestion modification

The existing Linkosh extension at `tools/linkosh-test/extension` is now the active implementation. The separate `tools/orma-capture` experiment is superseded; do not load it for this workflow.

## Use the existing UI

1. In Windows Chrome open `chrome://extensions` and click Reload on the existing unpacked Linkosh extension. Its folder remains `\\wsl$\Ubuntu\home\shibu\cs\hackathons\orma\tools\linkosh-test\extension`.
2. Keep your platform accounts signed into that Chrome profile. No Linux browser is needed.
3. Open Linkosh Options. Enable whichever services you want. Under Developer, choose Maximum items per service (default 100; 0 uses the provider's full walk). This is a per-run limit, not a limit on the accumulated library.
4. Turn Capture mode OFF to see parsed items immediately after Sync. With Capture mode ON, Sync collects responses first; use Ingest raw to populate the same original library UI.
5. Use Sync for the selected service, or Full sync for enabled services. Every run starts from the beginning. Provider-specific safety caps and platform availability still apply; LinkedIn's former 100-page cap was removed.
6. Options → Developer → Export JSON downloads `linkosh-capture.json`. It contains `items` (normalized results) and `rawPages` (original response bodies, selected IDs, context and ingest status). Expand the JSON in an editor to inspect attachment data. Raw responses are whole API pages and may include extra entities beyond the selected item count.

Results live only in an offscreen worker's memory. They survive closing/reopening the popup and background service-worker restarts while that worker remains alive. Closing Chrome, reloading/disabling the extension, or loss of the offscreen document clears them. Export before doing so. Preferences/provider caches still use Chrome storage. Old SQLite files/exports are preserved, but are not read, migrated or written by this build.

## Preserved

Original popup/full-page/options layout and CSS; seven original provider fetchers and parsers (LinkedIn, Instagram, YouTube, X, Facebook, Hacker News, Substack); service selection/login checks; progress/stop; raw capture/ingest/reingest/clear; collections; stars; trash/restore; browsing and text filtering. Reddit was not supported by this version of Linkosh and was not added.

## Changed

No active SQLite/OPFS path or AI/model runtime. Existing UI RPC names such as `db`/`exportDb` are compatibility names for memory operations, not a database. Semantic/Hybrid search, More like this, and embedding rebuilding are disabled. Text filtering supports words, phrases, fields, AND/OR/NOT/groups and is:starred using JavaScript substring matching; it does not reproduce SQLite FTS5 ranking/tokenization/proximity semantics. NEAR queries report an error.

LinkedIn parsing follows ordered result references rather than unordered included entities. Repeated syncs update encountered items' order while retaining stars/deletes. Distinct-item count limits stop multi-list walks too. Repeated collection memberships merge into one item. Other platforms retain their own API ordering; a universal newest-saved order is not claimed. Pagination during concurrent save/unsave activity is not an atomic snapshot; exact LinkedIn save timestamps remain unavailable.

## Media scope

All response payloads fetched by the original providers are retained in memory/export, including media metadata those responses expose. LinkedIn normalized items additionally expose `attachmentPreview` and explicit extraction status. A playable-preview flag or thumbnail is not a downloaded video, transcript, OCR result, original photo, or carousel/PDF extraction. This change does not implement new media download/transcription/OCR pipelines. The separate prototype's post-page enrichment is not integrated into this build. Nothing is sent to FalkorDB yet.

## Validation and restoration

Run `node --test tools/linkosh-test/memory-ingestion.test.mjs` from the project root. 11 tests cover order, exact count, >100 items, raw replay, duplicates, collections/account identity, text filtering, stars/trash, provider registrations and background APIs without AI. Historical fixture replay validated 102 LinkedIn posts, beginning Marcelo Trylesinski, Richa Sharma, Aayush Saini, and eight playable previews. SQLite is read only by a development fixture test, never by extension runtime.

A fresh Windows Chrome UI/network run and live captures from the other providers have not been performed. Internal platform APIs can change independently of this modification.

The original release ZIP and a pre-change ZIP remain in downloads/. Reviewable source changes are saved in `linkosh-memory-ingestion.patch` because extension/ is ignored. Apply the patch to a clean extraction of the original release to reproduce the modified runtime. The generated patch contains source code only, not private captured posts. `reports/linkosh-memory-preview.json` is a private historical replay using the modified memory runtime.
