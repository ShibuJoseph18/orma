import asyncio,json,re,time
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .graph import GraphStore,ROOT
from .ingest import Ingestor,select_items,LIMITS
from .llm import Gemini,LLMError
store=None; llm=Gemini(); ingestor=None
@asynccontextmanager
async def lifespan(app):
    global store,ingestor
    store=GraphStore(); ingestor=Ingestor(store,llm)
    yield
    if ingestor.tasks: await asyncio.gather(*ingestor.tasks,return_exceptions=True)
    store.save()
app=FastAPI(title="Orma",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:8000","http://127.0.0.1:8000"],allow_origin_regex=r"chrome-extension://[a-z]{32}",allow_methods=["GET","POST"],allow_headers=["Content-Type"])
@app.get("/api/health")
def health():
    return {"ok":store is not None,"database":"FalkorDB","mode":store.mode if store else "starting","llm_configured":llm.configured,"model":llm.model,"limits":LIMITS,"single_user":True}
@app.get("/api/stats")
def stats(): return store.stats()
@app.get("/api/resources")
def resources(platform:str="",concept:str=""): return {"items":store.resources(platform=platform,concept=concept)}
@app.get("/api/graph")
def graph(): return store.snapshot()
@app.get("/api/history")
def history(): return {"items":store.history()}
@app.get("/api/jobs")
def jobs(): return {"items":list(ingestor.jobs.values())[-10:]}
@app.get("/api/jobs/{jid}")
def job(jid:str):
    if jid not in ingestor.jobs: raise HTTPException(404,"Import not found.")
    return ingestor.jobs[jid]
@app.post("/api/import")
async def import_items(request:Request):
    if not llm.configured: raise HTTPException(400,"Set GEMINI_API_KEY in backend/.env first.")
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>25_000_000: raise HTTPException(413,"Import exceeds 25 MB.")
    try:
        payload=json.loads(data); items,skipped=select_items(payload)
        if not items: raise ValueError("No supported saved items with valid source URLs.")
        return ingestor.launch(items,skipped)
    except (ValueError,AttributeError,TypeError) as exc: raise HTTPException(400,str(exc))
@app.post("/api/import/existing")
async def import_existing():
    if not llm.configured: raise HTTPException(400,"Set GEMINI_API_KEY in backend/.env first.")
    path=ROOT/"tools/linkosh-test/reports/linkosh-memory-preview.json"
    if not path.exists(): raise HTTPException(404,"Import a Linkosh JSON export to begin.")
    try:
        items,skipped=select_items(json.loads(path.read_text()),origin="LinkedIn capture · October 16")
        return ingestor.launch(items,skipped)
    except ValueError as exc: raise HTTPException(409,str(exc))
class SearchRequest(BaseModel):
    question:str=Field(min_length=2,max_length=2000)
    platform:str=""
    replay:bool=False
@app.post("/api/search")
async def search(body:SearchRequest):
    start=time.perf_counter(); terms=[]; warnings=[]; answer=""; suggestions=[]
    if llm.configured and not body.replay:
        try: terms=await llm.intent(body.question,store.vocabulary())
        except LLMError as exc: warnings.append(str(exc))
    if not terms:
        stop={"find","show","give","what","which","saved","posts","videos","resources","about","have","from","with","that","this","some","need","want","please","help","tomorrow"}
        terms=[w for w in re.findall(r"[\w+#.]+",body.question.lower()) if len(w)>2 and w not in stop][:16]
    results=store.search(terms,platform=body.platform)
    if results and llm.configured and not body.replay:
        try:
            synthesis=await llm.answer(body.question,results[:8]); answer=str(synthesis.get("answer","")); suggestions=synthesis.get("suggestions",[])[:3]
        except LLMError as exc: warnings.append(str(exc))
    if not results: answer="I couldn't find a supported connection in your saved library yet. Try a specific topic, or import more saves."
    elif not answer: answer=f"I found {len(results)} resources connected to your question. Here are the closest connections from your library:\n\n"+"\n\n".join(f"- **{r['title']}** — {r['summary']} [{i+1}]" for i,r in enumerate(results[:5]))
    sid=store.remember(body.question,answer,results)
    return {"id":sid,"question":body.question,"answer":answer,"resources":results,"terms":terms,"warnings":warnings,"suggestions":suggestions,
        "elapsed_ms":round((time.perf_counter()-start)*1000),"trace":[
        {"step":"Understand your question","detail":", ".join(terms)},{"step":"Resolve concepts in FalkorDB","detail":"Match topics, entities and goals"},
        {"step":"Follow relationships","detail":"Concept → RELATED_TO → concept → ABOUT → resource"},{"step":"Ground the answer","detail":f"{len(results)} source links · no raw posts retained"}]}
capture_control={"id":"","platforms":[]}
capture_diagnostics={}
@app.get("/api/capture/control")
def capture_task(): return capture_control
@app.post("/api/capture/control")
async def request_capture(request:Request):
    data=await request.json()
    platforms=[p for p in data.get("platforms",[]) if p in LIMITS]
    if not platforms: raise HTTPException(400,"Choose supported platforms.")
    capture_control.update(id=str(time.time_ns()),platforms=platforms,mode="import" if data.get("mode")=="import" else "capture")
    return capture_control
@app.get("/api/capture/diagnostics")
def capture_state(): return capture_diagnostics
@app.post("/api/capture/diagnostics")
async def capture_report(request:Request):
    data=await request.json()
    capture_diagnostics[str(data.get("browser","unknown"))[:80]]={
        "at":time.time(),"runtime":bool(data.get("runtime")),"status":str(data.get("status",""))[:500],
        "reports":data.get("reports",[])[:4]}
    return {"ok":True}

if (ROOT/"dist").exists(): app.mount("/",StaticFiles(directory=str(ROOT/"dist"),html=True),name="frontend")
