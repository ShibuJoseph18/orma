"""Generate and verify the source-only follow-up patch for Linkosh."""
from pathlib import Path
import difflib,subprocess,tempfile,zipfile
root=Path(__file__).resolve().parents[1]; tools=root/"tools/linkosh-test"
with tempfile.TemporaryDirectory(prefix="orma-linkosh-source-") as folder:
    baseline=Path(folder)
    with zipfile.ZipFile(tools/"downloads/linkosh-chrome-v0.1.1.zip") as archive:
        entries=archive.namelist()
        prefix="" if "manifest.json" in entries else next(n[:-len("manifest.json")] for n in entries if n.endswith("/manifest.json"))
        for entry in entries:
            if not entry.startswith(prefix) or entry.endswith("/"): continue
            rel=Path(entry[len(prefix):])
            if rel.is_absolute() or ".." in rel.parts: raise ValueError("Unsafe archive path")
            target=baseline/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
    subprocess.run(["git","apply",str(tools/"linkosh-memory-ingestion.patch")],cwd=baseline,check=True)
    actual=tools/"extension";parts=[]
    paths=sorted({p.relative_to(baseline) for p in baseline.rglob("*") if p.is_file()} | {p.relative_to(actual) for p in actual.rglob("*") if p.is_file()})
    for rel in paths:
        a,b=baseline/rel,actual/rel
        old=a.read_bytes() if a.exists() else b"";new=b.read_bytes() if b.exists() else b""
        if old==new: continue
        if b"\0" in old or b"\0" in new: raise ValueError("Unexpected binary difference: "+str(rel))
        for line in difflib.unified_diff(old.decode().splitlines(keepends=True),new.decode().splitlines(keepends=True),fromfile="a/"+rel.as_posix(),tofile="b/"+rel.as_posix()):
            parts.append(line if line.endswith("\n") else line+"\n"+chr(92)+" No newline at end of file\n")
    output=tools/"linkosh-orma-app.patch";output.write_text("".join(parts))
    subprocess.run(["git","apply","--check",str(output)],cwd=baseline,check=True)
    subprocess.run(["git","apply",str(output)],cwd=baseline,check=True)
    assert all((baseline/p).read_bytes()==(actual/p).read_bytes() for p in paths if (actual/p).exists())
    print("Verified source-only extension patch:",output,"bytes:",output.stat().st_size)
