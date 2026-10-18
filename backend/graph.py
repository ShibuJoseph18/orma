import hashlib,threading
from datetime import datetime,timezone
from pathlib import Path
from .llm import settings
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/".data"; DATA.mkdir(exist_ok=True)
def now(): return datetime.now(timezone.utc).isoformat()
def key(value): return hashlib.sha256(value.encode()).hexdigest()[:24]
def names(values,cap=8):
    result=[]
    for value in values if isinstance(values,list) else []:
        if not isinstance(value,str): continue
        name=" ".join(value.strip().split())[:80]
        if name and name.casefold() not in {n.casefold() for n in result}: result.append(name)
    return result[:cap]
class GraphStore:
    def __init__(self,graph_name=None,db_path=None):
        cfg=settings(); url=cfg.get("FALKORDB_URL","").strip()
        if url:
            from falkordb import FalkorDB
            self.db=FalkorDB.from_url(url,socket_connect_timeout=5,socket_timeout=15); self.mode="server"
        else:
            from redislite.falkordb_client import FalkorDB
            self.db=FalkorDB(str(db_path or DATA/"orma.rdb")); self.mode="embedded"
        self.graph=self.db.select_graph(graph_name or cfg.get("FALKORDB_GRAPH","orma")); self.lock=threading.RLock()
        self.query("RETURN 1")
        for label,prop in [("Resource","id"),("Concept","key"),("Platform","name"),("Author","key"),("Search","id")]:
            try: self.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
            except Exception as exc:
                if not any(x in str(exc).lower() for x in ("already indexed","already exists")): raise
    def query(self,query,params=None):
        with self.lock: return self.graph.query(query,params or {}).result_set
    def save(self):
        if hasattr(self.db,"connection") and hasattr(self.db.connection,"save"): self.db.connection.save()
    def needs_content(self,rid): return bool(self.query("MATCH (r:Resource {id:$id}) WHERE r.media_status=\"needs-content\" RETURN r.id",{"id":rid}))
    def vocabulary(self): return [r[0] for r in self.query("MATCH (c:Concept) RETURN c.name ORDER BY c.name LIMIT 1000")]
    def exists(self,rid): return bool(self.query("MATCH (r:Resource {id:$id}) RETURN r.id",{"id":rid}))
    def upsert(self,item,c):
        topics=names(c.get("topics"),6)
        resource={k:item[k] for k in ("id","url","platform","author","kind","media_status","position","origin")}
        resource.update(title=str(c.get("title") or item.get("title") or "Saved resource")[:120],summary=str(c.get("summary") or "")[:600],imported_at=item.get("imported_at",now()))
        if (not topics or not resource["summary"]) and item.get("media_status")!="needs-content": raise ValueError("Missing topic or derived summary")
        self.query("""MERGE (r:Resource {id:$id})
            SET r.url=$url,r.platform=$platform,r.author=$author,r.kind=$kind,r.title=$title,r.summary=$summary,
                r.media_status=$media_status,r.imported_at=$imported_at,r.position=$position,r.origin=$origin
            MERGE (p:Platform {name:$platform}) MERGE (r)-[:FROM_PLATFORM]->(p)
            MERGE (u:User {id:'local'}) MERGE (u)-[:SAVED]->(r)""",resource)
        self.query("MATCH (r:Resource {id:$id})-[e:ABOUT|MENTIONS|HELPS_WITH]->() DELETE e",{"id":item["id"]})
        self.query("MATCH ()-[e:RELATED_TO {resource_id:$id}]->() DELETE e",{"id":item["id"]})
        if resource["author"]:
            self.query("MATCH (r:Resource {id:$id}) MERGE (a:Author {key:$ak}) SET a.name=$author MERGE (a)-[:CREATED]->(r)",{**resource,"ak":key(resource["platform"]+":"+resource["author"].casefold())})
        for values,relation,kind in [(topics,"ABOUT","topic"),(names(c.get("entities"),5),"MENTIONS","entity"),(names(c.get("goals"),3),"HELPS_WITH","goal")]:
            for name in values:
                self.query(f"MATCH (r:Resource {{id:$id}}) MERGE (c:Concept {{key:$key}}) ON CREATE SET c.name=$name,c.kind=$kind MERGE (r)-[:{relation}]->(c)",{"id":item["id"],"key":name.casefold(),"name":name,"kind":kind})
        valid={x.casefold() for x in topics}
        for conn in (c.get("connections") or [])[:5]:
            if not isinstance(conn,dict): continue
            a,b=str(conn.get("from","")).casefold(),str(conn.get("to","")).casefold()
            if a not in valid or b not in valid or a==b: continue
            self.query("MATCH (a:Concept {key:$a}),(b:Concept {key:$b}) MERGE (a)-[e:RELATED_TO {resource_id:$id}]->(b) SET e.reason=$reason",{"a":a,"b":b,"id":item["id"],"reason":str(conn.get("reason",""))[:180]})
        return resource
    def resources(self,platform="",concept="",limit=500):
        rows=self.query("""MATCH (r:Resource) WHERE ($platform='' OR r.platform=$platform)
            OPTIONAL MATCH (r)-[:ABOUT]->(c:Concept)
            RETURN r,collect(DISTINCT c.name) ORDER BY r.imported_at DESC,r.position ASC LIMIT $limit""",{"platform":platform,"limit":limit})
        output=[{**r.properties,"topics":topics} for r,topics in rows]
        if concept: output=[r for r in output if concept.casefold() in [t.casefold() for t in r["topics"]]]
        return output
    def stats(self):
        return {"resources":self.query("MATCH (r:Resource) RETURN count(r)")[0][0],
            "connections":self.query("MATCH ()-[e]->() RETURN count(e)")[0][0],
            "topics":[{"name":name,"count":n} for name,n in self.query("MATCH (c:Concept)<-[:ABOUT]-(r:Resource) RETURN c.name,count(r) ORDER BY count(r) DESC LIMIT 24")],
            "platforms":dict(self.query("MATCH (r:Resource) RETURN r.platform,count(r)")),
            "concepts":len(self.vocabulary())}
    def snapshot(self):
        nodes=[{"id":r["id"],"label":r["title"],"type":"resource","platform":r["platform"]} for r in self.resources()]
        edges=[]; concepts={}
        for rid,ck,name,kind,relation in self.query("MATCH (r:Resource)-[e:ABOUT|MENTIONS|HELPS_WITH]->(c:Concept) RETURN r.id,c.key,c.name,c.kind,type(e)"):
            cid="concept:"+ck; concepts[cid]={"id":cid,"label":name,"type":kind}
            edges.append({"source":rid,"target":cid,"label":relation})
        nodes.extend(concepts.values())
        for a,b,reason in self.query("MATCH (a:Concept)-[e:RELATED_TO]->(b:Concept) RETURN a.key,b.key,e.reason"):
            edges.append({"source":"concept:"+a,"target":"concept:"+b,"label":reason or "RELATED_TO"})
        return {"nodes":nodes,"edges":edges}
    def search(self,terms,limit=12,platform=""):
        params={"terms":terms,"platform":platform}; ranked={}
        seeds=self.query("""MATCH (r:Resource)-[e:ABOUT|MENTIONS|HELPS_WITH]->(c:Concept)
            WHERE any(term IN $terms WHERE toLower(c.name) CONTAINS term OR term CONTAINS toLower(c.name))
            AND ($platform='' OR r.platform=$platform) RETURN r.id,c.name,type(e)""",params) if terms else []
        for rid,name,relation in seeds:
            hit=ranked.setdefault(rid,{"score":0,"paths":[],"match":"direct"}); hit["score"]+=4
            path={"nodes":[name,rid],"relations":[relation],"label":name+" → saved resource"}
            if path not in hit["paths"]: hit["paths"].append(path)
        # Two-hop graph expansion changes the actual candidate set.
        expanded=self.query("""MATCH (a:Concept)-[:RELATED_TO]-(b:Concept)<-[:ABOUT]-(r:Resource)
            WHERE any(term IN $terms WHERE toLower(a.name) CONTAINS term OR term CONTAINS toLower(a.name))
            AND ($platform='' OR r.platform=$platform) RETURN DISTINCT r.id,a.name,b.name""",params) if terms else []
        for rid,a,b in expanded:
            hit=ranked.setdefault(rid,{"score":0,"paths":[],"match":"connected"}); hit["score"]+=1.5
            path={"nodes":[a,b,rid],"relations":["RELATED_TO","ABOUT"],"label":a+" → "+b+" → saved resource"}
            if path not in hit["paths"]: hit["paths"].append(path)
        lexical=self.query("""MATCH (r:Resource) WHERE any(term IN $terms WHERE toLower(r.title+' '+r.summary) CONTAINS term)
            AND ($platform='' OR r.platform=$platform) RETURN r.id""",params) if terms else []
        for (rid,) in lexical: ranked.setdefault(rid,{"score":0,"paths":[],"match":"summary"})["score"]+=1
        resources={r["id"]:r for r in self.resources(platform=platform)}
        ordered=sorted(ranked.items(),key=lambda v:v[1]["score"],reverse=True)
        selected=[];seen_ids=set();seen_platforms=set()
        peak=ordered[0][1]["score"] if ordered else 0
        # Surface strong matches from distinct platforms before filling by score.
        for rid,hit in ordered:
            if rid not in resources: continue
            source=resources[rid]["platform"]
            if source not in seen_platforms and hit["score"]>=peak*.35:
                selected.append((rid,hit));seen_ids.add(rid);seen_platforms.add(source)
        for rid,hit in ordered:
            if rid not in seen_ids and rid in resources: selected.append((rid,hit));seen_ids.add(rid)
        return [{**resources[rid],**hit,"paths":hit["paths"][:4]} for rid,hit in selected[:limit]]

    def remember(self,question,answer,resources):
        sid=key(now()+question)
        self.query("CREATE (s:Search {id:$id,question:$question,answer:$answer,created_at:$at})",{"id":sid,"question":question[:2000],"answer":answer[:6000],"at":now()})
        for r in resources: self.query("MATCH (s:Search {id:$sid}),(r:Resource {id:$rid}) MERGE (s)-[:RETRIEVED]->(r)",{"sid":sid,"rid":r["id"]})
        self.save(); return sid
    def history(self): return [r.properties for (r,) in self.query("MATCH (s:Search) RETURN s ORDER BY s.created_at DESC LIMIT 30")]
