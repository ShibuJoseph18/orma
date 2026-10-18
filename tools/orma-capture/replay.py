"""Read-only historical fixture replay. SQLite is NOT an extension dependency."""
from pathlib import Path
import sqlite3, json, subprocess, os
root = Path(__file__).resolve().parents[2]
fixture = root / 'tools/linkosh-test/exports/linkosh.sqlite'
node = os.environ.get('ORMA_NODE', '/home/shibu/.nvm/versions/node/v24.21.0/bin/node')
with sqlite3.connect(f'file:{fixture}?mode=ro', uri=True) as db:
    pages = [json.loads(row[0]) for row in db.execute("SELECT body FROM raw_data WHERE kind='items' ORDER BY page ASC, id ASC")]
script = """
import {collectSaved} from './tools/orma-capture/parser.mjs';
let input='';for await(const chunk of process.stdin)input+=chunk;
const pages=JSON.parse(input);
const result=await collectSaved({limit:10000,fetchPage:async i=>pages[i] || {data:{data:{searchDashClustersByAll:{elements:[]}}}}});
console.log(JSON.stringify({fixtureReplay:true,liveCapture:false,provider:'linkedin',...result},null,2));
"""
result = subprocess.run([node, '--input-type=module', '-e', script],input=json.dumps(pages),text=True,capture_output=True,cwd=root,check=True)
report = json.loads(result.stdout)
items = report['items']
assert len(items)==102, len(items)
assert [x['author']['name'] for x in items[:3]]==['Marcelo Trylesinski','Richa Sharma','Aayush Saini']
assert len({x['id'] for x in items})==102
out = root / 'tools/linkosh-test/reports/orma-capture-replay.json'
out.write_text(result.stdout)
out.chmod(0o600)
print(json.dumps({'count':len(items),'firstThree':[x['author']['name'] for x in items[:3]],'withImageReferences':sum(bool(x['attachmentPreview']['media']) for x in items),'playablePreviews':sum(x['attachmentPreview']['playablePreview'] for x in items),'report':str(out),'liveCapture':False},indent=2))
