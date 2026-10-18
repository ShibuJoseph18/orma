from backend.graph import GraphStore
s=GraphStore()
rows=s.query("""MATCH (r:Resource)-[:ABOUT]->(c:Concept)
WITH c,collect(DISTINCT r.platform) AS sources,count(r) AS hits
WHERE size(sources)>1
RETURN c.name,sources,hits ORDER BY size(sources) DESC,hits DESC LIMIT 16""")
print("Shared concepts:",rows)
print("Media coverage:",s.query("MATCH (r:Resource) RETURN r.platform,r.media_status,count(r)"))
print("References without topics:",s.query("MATCH (r:Resource) WHERE r.media_status='needs-content' RETURN r.url"))
