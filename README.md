# Orma
**Your saves, connected.**

A local personal knowledge app that turns saved LinkedIn, Instagram, YouTube Watch Later and X content into a searchable FalkorDB graph. Built for Graph Hacks 2026, Track 01: Agents That Act on Connected Data.

## Recording mode
Open http://localhost:5173/?demo=1 for the prepared walkthrough. This is the default view. Select sources, click Connect sources and Ingest selected platforms, then explore the graph and ask a question. The seven-second import animation replays the existing indexed library. Search uses real FalkorDB retrieval without a new Gemini call. No invented posts or graph connections are added.

The current library contains **240 real indexed saves**: LinkedIn 100, Instagram 40, YouTube Watch Later 50 and X 50. Instagram returned 40 available saves. A verified query about software engineering career retrieves references and evidence paths from all four platforms.

Use http://localhost:5173/?live=1 for live Linkosh ingestion and Gemini question interpretation. Per-resource coverage distinguishes metadata, image-preview analysis and direct video analysis. Background YouTube enrichment is disabled for the recording.

The six-slide presentation and narrated walkthrough are in output/. See DEMO.md for the recording steps.
## Run in WSL Ubuntu
Requires Node.js 20.19+ and Python 3.12+. The bundled FalkorDBLite database runs in Linux/WSL; Docker is optional.

~~~bash
git clone https://github.com/ShibuJoseph18/orma.git
cd orma
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm install
cp backend/.env.example backend/.env  # only if .env does not already exist
# Set GEMINI_API_KEY in backend/.env
bash scripts/start.sh
~~~

Open **http://localhost:5173** in Windows Chrome. The API and interactive API docs are at http://localhost:8000/docs. The existing configured key is private and ignored by Git.

For separate terminals:
~~~bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm run dev
~~~

## Ingest your saves
1. Keep your accounts signed in in Windows Chrome.
2. Reload the existing unpacked Linkosh extension at chrome://extensions. Its local folder is tools/linkosh-test/extension.
3. Open http://localhost:5173/?live=1 in Chrome, choose **Connections**, click **Connect Linkosh**, select platforms, then **Ingest selected platforms**.
4. Requested limits: LinkedIn 100, Instagram 50, YouTube Watch Later 50, X 50. The backend enforces the caps again and deduplicates canonical source URLs.
5. Capture results show platform failures explicitly. An expired session or changed internal API can prevent capture; there is no fabricated connection status or synthetic content.
6. Alternatively use **Import saves → Import a Linkosh capture** with a JSON export, or add a URL and text/transcript through **My library → Add a resource**.

Chrome extension ID defaults to the existing local installation in src/main.tsx. If loading the unpacked extension gives a different ID, replace EXTENSION there.

The modified Linkosh remains memory-only. Its original provider fetchers handle signed-in sessions; cookies never leave Chrome. The app bridge accepts only localhost/127.0.0.1 on ports 5173 or 8000. YouTube walks Watch Later only, in the order supplied by YouTube. LinkedIn resolves ordered saved-list references. Internal platform APIs are prototypes, not official OAuth integrations.

### Reproduce the extension
Download the original Linkosh v0.1.1 release from https://github.com/sabyasachi/linkosh/releases/tag/v0.1.1 and extract it into tools/linkosh-test/extension. From that directory apply the patches in order:

~~~bash
git apply ../linkosh-memory-ingestion.patch
git apply ../linkosh-orma-app.patch
~~~

Existing extension changes and exports are preserved. Reloading the memory-only extension clears its temporary in-memory capture; export first if needed.

## What the graph retains
- Resource URL, author, platform, format and source order
- A concise **derived** title and summary
- Model-derived topics, entities, goals and grounded topic relationships
- User search questions, grounded answers and links to retrieved resources

**Orma does not persist original post bodies, raw API responses, downloaded media, transcripts, images or cookies.** Content enters the classification pipeline in request/job memory and is discarded when processing ends. Existing historical Linkosh captures in tools/linkosh-test/reports and exports are user-owned inputs from earlier work; Orma does not make another raw archive or erase those files.

Derived summaries and metadata still contain personal knowledge. The local FalkorDB snapshot is in ignored .data/orma.rdb. Gemini receives content for classification. This is a local single-user prototype with no login/tenant isolation; use it on loopback.

## Why FalkorDB is central
The primary database is genuine FalkorDB, running embedded through the official FalkorDBLite package. There is no SQLite or JSON fallback knowledge store.

~~~text
(User)-[:SAVED]->(Resource)-[:FROM_PLATFORM]->(Platform)
(Author)-[:CREATED]->(Resource)
(Resource)-[:ABOUT]->(Concept: topic)
(Resource)-[:MENTIONS]->(Concept: entity)
(Resource)-[:HELPS_WITH]->(Concept: goal)
(Concept)-[:RELATED_TO {reason, resource_id}]->(Concept)
(Search)-[:RETRIEVED]->(Resource)
~~~

Gemini derives concepts from actual incoming content and sees the growing graph vocabulary to reuse concepts across platforms. There are no seeded topic lists or pre-labeled runtime examples.

For a question, the agent resolves the intent against the graph vocabulary, executes parameterized Cypher concept matching, expands across RELATED_TO relationships to find additional resources, ranks the graph evidence, and synthesizes an answer from retrieved summaries. Every result retains its original URL and its actual graph path. The UI exposes the retrieval trace. Search memory also persists in FalkorDB across sessions.

The agent uses bounded retrieval tools, rather than executing arbitrary model-generated Cypher.

## Media coverage
- Text posts: available captured text is classified.
- YouTube: Gemini is sent a supported direct YouTube video URL, with no local video download. Access and model limits apply; analysis can take time and consume quota. Failed/private/unavailable videos fall back to captured metadata and display **metadata-only**.
- Instagram/LinkedIn/X videos and images: currently use available captions and metadata. Attached Instagram/X image previews can be sent temporarily to Gemini for visual classification when text is insufficient. Full video downloading, audio transcription, and complete carousel/PDF reading are not implemented. Supplied transcript/OCR text in JSON can be classified.
- Profile avatars are never treated as attached source images.
- Coverage is visible on every resource. A derived summary from metadata is never presented as full video understanding.

## Optional Docker database
~~~bash
docker compose up -d
# In backend/.env set:
# FALKORDB_URL=redis://localhost:6379
~~~
Restart FastAPI. This selects a separate server graph; the embedded graph is not silently migrated. Browser: http://localhost:3000. Persistent data uses the orma_graph Docker volume.

For cloud use, set a password-protected redis:// or rediss:// connection in FALKORDB_URL. Never commit connection strings or API keys.

## Validation
~~~bash
npm run build
.venv/bin/python -m pytest backend/test_core.py -q
node --test tools/linkosh-test/memory-ingestion.test.mjs
~~~
Tests exercise real FalkorDB two-hop retrieval across platforms, parameterized query safety, no retained raw text, URL deduplication, exact per-platform limits, Watch Later selection and existing Linkosh ingestion behavior.

A local Windows headless Chrome QA helper, tools/qa.cjs, verifies library filtering, source details, graph view, platform selection, real graph search, source traces and mobile overflow. It uses this machine's bundled Playwright installation; adjust its runtime paths on another machine.

## Honest demo status
100 real LinkedIn posts from the October 16 capture were classified with Gemini and persisted in FalkorDB. Fresh Instagram, YouTube and X results depend on the user's active Chrome sessions and the Linkosh capture results. No fake cross-platform saves are preloaded.

See DEMO.md for a short recording outline.
