import uuid
import pytest
from backend.ingest import select_items,normalize
from backend.graph import GraphStore

def test_caps_dedupe_and_watch_later():
    rows=[]
    for platform,limit in [("linkedin",100),("instagram",50),("youtube",50),("x",50)]:
        for i in range(limit+10):
            host={"linkedin":"www.linkedin.com","instagram":"www.instagram.com","youtube":"www.youtube.com","x":"x.com"}[platform]
            url=f"https://{host}/p/{i}" if platform!="youtube" else f"https://{host}/watch?v=id{i}"
            rows.append({"url":url,"provider":platform,"summary":"transient text","collection":["Watch later"] if platform=="youtube" else []})
    rows.append(rows[0])
    rows.insert(0,{"url":"https://youtube.com/watch?v=wrong","provider":"youtube","collection":["Other playlist"]})
    items,skipped=select_items({"items":rows})
    assert len(items)==250
    assert {p:sum(i["platform"]==p for i in items) for p in ("linkedin","instagram","youtube","x")}=={"linkedin":100,"instagram":50,"youtube":50,"x":50}
    assert all("wrong" not in i["url"] for i in items)
    assert skipped==42

def test_canonicalization_and_media():
    a=normalize({"url":"https://youtu.be/abc?t=12","title":"A video"})
    b=normalize({"url":"https://www.youtube.com/watch?v=abc&feature=share"})
    assert a["id"]==b["id"] and a["kind"]=="video"
    assert normalize({"url":"https://instagram.com/p/a","kind":"carousel"})["media_status"]=="metadata-only"
    with pytest.raises(ValueError): normalize({"url":"javascript:alert(1)"})

def test_real_falkordb_traversal_privacy_and_parameters(tmp_path):
    graph=GraphStore(graph_name="test_"+uuid.uuid4().hex,db_path=tmp_path/"test.rdb")
    try:
        a=normalize({"url":"https://linkedin.com/posts/test-a","text":"PRIVATE RAW BODY NOT TO RETAIN"})
        b=normalize({"url":"https://youtube.com/watch?v=test-b"})
        graph.upsert(a,{"title":"Agent runtime","summary":"A derived description","topics":["Agent runtime","Sandboxing"],"connections":[{"from":"Agent runtime","to":"Sandboxing","reason":"Runs safely"}]})
        graph.upsert(b,{"title":"Isolation tutorial","summary":"Separate derived description","topics":["Sandboxing"]})
        matches=graph.search(["agent runtime"])
        assert {r["id"] for r in matches}=={a["id"],b["id"]}
        expanded=next(r for r in matches if r["id"]==b["id"])
        assert expanded["match"]=="connected"
        assert expanded["paths"][0]["relations"]==["RELATED_TO","ABOUT"]
        assert graph.search(["' OR true //"])==[]
        stored=graph.resources()
        assert all("text" not in r and "transcript" not in r for r in stored)
        assert "PRIVATE RAW BODY" not in str(stored)
        graph.upsert(a,{"title":"Updated","summary":"Updated derived knowledge","topics":["Agent runtime"]})
        assert len(graph.resources())==2
        assert all(r["id"]!=b["id"] for r in graph.search(["agent runtime"]))
        sid=graph.remember("My question","My answer",stored)
        assert graph.history()[0]["id"]==sid
        graph.save()
    finally:
        graph.graph.delete()
