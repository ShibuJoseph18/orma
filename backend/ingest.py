import asyncio, uuid, httpx
from collections import Counter
from urllib.parse import urlsplit,urlunsplit,parse_qs
from .graph import key,now
from .llm import settings
LIMITS={"linkedin":100,"instagram":50,"youtube":50,"x":50}
def normalize(raw,position=0,origin="import"):
    parts=urlsplit(str(raw.get("url") or raw.get("sourceUrl") or raw.get("source_url") or ""))
    if parts.scheme not in ("http","https") or not parts.hostname: raise ValueError("Missing valid source URL")
    host=parts.hostname.lower().removeprefix("www.").removeprefix("m.")
    platform=next((v for h,v in {"linkedin.com":"linkedin","instagram.com":"instagram","youtube.com":"youtube","youtu.be":"youtube","x.com":"x","twitter.com":"x"}.items() if host==h or host.endswith("."+h)),"web")
    url=urlunsplit((parts.scheme,parts.netloc.lower(),parts.path.rstrip("/"),"" if platform!="web" else parts.query,""))
    if platform=="youtube":
        video=parts.path.strip("/") if host=="youtu.be" else (parse_qs(parts.query).get("v") or [""])[0]
        if parts.path.startswith("/shorts/"): video=parts.path.split("/")[2]
        if video: url="https://www.youtube.com/watch?v="+video
    author=raw.get("author") or raw.get("posterName") or ""
    if isinstance(author,dict): author=author.get("name","")
    preview=raw.get("attachmentPreview") or {}
    kind=str(raw.get("kind") or raw.get("format") or "text").lower()
    if platform=="youtube" or preview.get("showPlayButton") or preview.get("playablePreview") or kind in ("reel","short"): kind="video"
    if kind in ("photo","carousel"): kind="image"
    if kind not in ("text","image","video"): kind="text"
    transcript=raw.get("transcript") or raw.get("ocr") or ""
    return {"id":key(url),"url":url,"platform":platform,"author":str(author)[:160],"title":str(raw.get("title") or "")[:200],
        "text":str(raw.get("text") or raw.get("summary") or raw.get("description") or "")[:18000],"transcript":str(transcript)[:30000],
        "kind":kind,"position":position,"origin":origin,"image_url":str(raw.get("image") or "") if platform=="instagram" or platform=="x" and kind in ("image","video") else "",
        "media_status":"transcript-analyzed" if transcript else "metadata-only" if kind!="text" else "text-analyzed"}
def select_items(payload,origin="import"):
    raw=payload if isinstance(payload,list) else payload.get("items",payload.get("posts",[]))
    if not isinstance(raw,list): raise ValueError("JSON must contain an items array")
    counts=Counter(); seen=set(); items=[]; skipped=0
    for pos,value in enumerate(raw):
        if not isinstance(value,dict) or value.get("deletedAt"): skipped+=1; continue
        collection=value.get("collection") or []
        if isinstance(collection,str): collection=[collection]
        if (value.get("provider") or value.get("platform"))=="youtube" and collection and not any(str(c).lower() in ("watch later","watch later videos","wl","watchlater") for c in collection): skipped+=1; continue
        try: item=normalize(value,pos,origin)
        except ValueError: skipped+=1; continue
        platform=item["platform"]
        if platform not in LIMITS and platform!="web": skipped+=1; continue
        if item["id"] in seen or counts[platform]>=LIMITS.get(platform,50): skipped+=1; continue
        counts[platform]+=1; seen.add(item["id"]); items.append(item)
    return items,skipped
class Ingestor:
    def __init__(self,store,llm): self.store,self.llm=store,llm; self.jobs={}; self.tasks=set()
    def launch(self,items,skipped=0):
        if any(j["status"] in ("queued","processing") and j.get("type")!="video-enrichment" for j in self.jobs.values()): raise ValueError("An import is already running.")
        jid=str(uuid.uuid4())
        job={"id":jid,"status":"queued","total":len(items),"done":0,"imported":0,"skipped":skipped,"failed":0,"errors":[],"current":"Preparing your library","started_at":now(),"platforms":dict(Counter(i["platform"] for i in items))}
        self.jobs[jid]=job
        task=asyncio.create_task(self.run(job,items)); self.tasks.add(task); task.add_done_callback(self.tasks.discard)
        return job
    async def preview(self,item):
        url=item.get("image_url","")
        for redirect in range(3):
            parsed=urlsplit(url);host=(parsed.hostname or "").lower()
            allowed=any(host==suffix or host.endswith("."+suffix) for suffix in ("cdninstagram.com","fbcdn.net","twimg.com"))
            if parsed.scheme!="https" or not allowed: raise ValueError("No supported post image preview")
            async with httpx.AsyncClient(timeout=20) as client:
                async with client.stream("GET",url) as response:
                    if response.status_code in (301,302,303,307,308):
                        url=response.headers.get("location","");continue
                    response.raise_for_status()
                    mime=response.headers.get("content-type","").split(";")[0]
                    if mime not in ("image/jpeg","image/png","image/webp"): raise ValueError("Unsupported image preview")
                    chunks=bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks)>5_000_000: raise ValueError("Image preview exceeds 5 MB")
                    return await self.llm.image(item,bytes(chunks),mime,self.store.vocabulary())
        raise ValueError("Too many preview redirects")
    async def run(self,job,items):
        job["status"]="processing"
        try:
            pending=[]
            for item in items:
                item["imported_at"]=job["started_at"]
                if self.store.exists(item["id"]) and not self.store.needs_content(item["id"]):
                    job["done"]+=1;job["skipped"]+=1
                else: pending.append(item)
            def payload(item):
                return {k:v for k,v in item.items() if k in ("id","platform","title","author","text","transcript","media_status")}
            async def classify_one(item):
                data=await self.llm.classify([payload(item)],self.store.vocabulary())
                exact=next((c for c in data if str(c.get("id"))==item["id"]),None)
                if exact is not None: return exact
                if len(data)==1: return data[0]
                raise ValueError("Model omitted resource")
            async def classify_batch(batch):
                try:
                    data=await self.llm.classify([payload(i) for i in batch],self.store.vocabulary())
                    by_id={str(c.get("id")):c for c in data if isinstance(c,dict)}
                    for item in batch:
                        try:
                            classified=by_id.get(item["id"])
                            if not classified or not classified.get("topics") or not classified.get("summary"):
                                if item.get("image_url"):
                                    try:
                                        classified=await self.preview(item)
                                        item["media_status"]="image-preview-analyzed"
                                    except Exception as exc:
                                        job["errors"].append({"url":item["url"],"stage":"image","error":str(exc)[:240]})
                                        classified=await classify_one(item)
                                else: classified=await classify_one(item)
                            if not classified.get("topics") or not classified.get("summary"):
                                item["media_status"]="needs-content"
                                classified={"title":item.get("title") or f"Saved {item['platform']} reference","summary":"The capture did not expose enough readable content to classify this source.","topics":[]}
                                job["errors"].append({"url":item["url"],"stage":"coverage","error":"Needs readable source content; retained as a reference without invented labels."})
                            self.store.upsert(item,classified);job["imported"]+=1
                        except Exception as exc:
                            job["failed"]+=1;job["errors"].append({"url":item["url"],"stage":"classification","error":str(exc)[:300]})
                        job["done"]+=1
                except Exception as exc:
                    job["failed"]+=len(batch);job["done"]+=len(batch)
                    job["errors"].append({"stage":"classification","error":str(exc)[:300]})
            for start in range(0,len(pending),24):
                chunk=pending[start:start+24]
                job["current"]=f"Connecting saved content · {job['done']} of {job['total']}"
                await asyncio.gather(*(classify_batch(chunk[n:n+8]) for n in range(0,len(chunk),8)))
                self.store.save()
            job["status"]="completed" if not job["failed"] else "partial" if job["imported"] else "failed"
        except Exception as exc:
            job["status"]="failed";job["errors"].append({"error":str(exc)[:300]})
        finally:
            items.clear()
            job["current"]="Saved content is searchable" if job["status"]=="completed" else "Import finished with issues"
            job["finished_at"]=now()
        if settings().get("YOUTUBE_VIDEO_ANALYSIS","true").lower()=="true" and not any(j.get("type")=="video-enrichment" and j["status"]=="processing" for j in self.jobs.values()):
            task=asyncio.create_task(self.enrich_videos());self.tasks.add(task);task.add_done_callback(self.tasks.discard)
    async def enrich_videos(self):
        videos=[r for r in self.store.resources(platform="youtube") if r.get("media_status")!="video-analyzed"]
        if not videos: return
        job={"id":str(uuid.uuid4()),"type":"video-enrichment","status":"processing","total":len(videos),"done":0,"imported":0,"skipped":0,"failed":0,"errors":[],"current":"Deepening YouTube video understanding","started_at":now(),"platforms":{"youtube":len(videos)}}
        self.jobs[job["id"]]=job
        async def enrich(item):
            try:
                info=await self.llm.video(item["url"],item["title"],self.store.vocabulary())
                if not info.get("summary") or not info.get("topics"): raise ValueError("Video returned insufficient grounded knowledge")
                item["media_status"]="video-analyzed"
                self.store.upsert(item,info);job["imported"]+=1
            except Exception as exc:
                job["failed"]+=1;job["errors"].append({"url":item["url"],"stage":"video","error":str(exc)[:250]})
            finally: job["done"]+=1
        # Reserve a Gemini request lane for interactive search.
        for start in range(0,len(videos),2):
            job["current"]=f"Library ready · enriching YouTube videos {start+1}–{min(start+2,len(videos))} of {len(videos)}"
            await asyncio.gather(*(enrich(v) for v in videos[start:start+2]));self.store.save()
        job["status"]="completed" if not job["failed"] else "partial"
        job["current"]="Video enrichment finished; coverage is shown on each source"
        job["finished_at"]=now()
