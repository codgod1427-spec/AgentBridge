"""Local AgentBridge HTTP server. Python 3.10+, standard library only."""
import argparse
import json
import os
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path.home() / ".agentbridge"
DB = ROOT / "agentbridge.sqlite3"
WORK = ROOT / "workspace"
LOCK = threading.Lock()
EXECUTION = False

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def database():
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, prompt TEXT NOT NULL, agents TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS steps (workflow_id TEXT NOT NULL, position INTEGER NOT NULL, agent TEXT NOT NULL, status TEXT NOT NULL, output TEXT NOT NULL DEFAULT '', PRIMARY KEY(workflow_id,position))")
    db.commit()
    return db

def agent_run(agent, prompt):
    if not EXECUTION:
        return "failed", "Execution disabled"
    commands = {
        "claude": ["claude", "-p", prompt, "--permission-mode", "plan", "--output-format", "text"],
        "codex": ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", prompt],
    }
    if agent not in commands:
        return "failed", "Unsupported agent"
    WORK.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k in
           ("PATH", "HOME", "USER", "LOGNAME", "LANG", "TERM", "TMPDIR",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
    try:
        result = subprocess.run(commands[agent], cwd=WORK, env=env, text=True,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
        return ("completed" if result.returncode == 0 else "failed"), (result.stdout + "\n" + result.stderr)[-12000:]
    except FileNotFoundError:
        return "failed", f"{agent} executable not found"
    except subprocess.TimeoutExpired:
        return "failed", "Agent timed out"

def process(workflow_id):
    with LOCK:
        with database() as db:
            item = db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if not item or item["status"] != "queued":
                return
            db.execute("UPDATE workflows SET status='running' WHERE id=?", (workflow_id,))
        original = item["prompt"]
        context = original
        for position, agent in enumerate(json.loads(item["agents"])):
            with database() as db:
                db.execute("UPDATE steps SET status='running' WHERE workflow_id=? AND position=?", (workflow_id,position))
            status, output = agent_run(agent, context)
            with database() as db:
                db.execute("UPDATE steps SET status=?, output=? WHERE workflow_id=? AND position=?", (status,output,workflow_id,position))
            if status != "completed":
                with database() as db:
                    db.execute("UPDATE workflows SET status='failed' WHERE id=?", (workflow_id,))
                return
            context = ("Original request:\n" + original[:4000] + "\n\nPrevious " + agent +
                       " result:\n" + output[-6000:] + "\n\nReview and continue. "
                       "Do not access unrelated projects or make changes.")
        with database() as db:
            db.execute("UPDATE workflows SET status='completed' WHERE id=?", (workflow_id,))

HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AgentBridge</title><style>body{font:16px system-ui;background:#101726;color:#f1f5ff;max-width:900px;margin:35px auto;padding:15px}input,textarea,select,button{font:inherit;padding:10px;margin:5px;border-radius:7px}textarea{width:95%;height:95px}button{background:#587af2;color:white;border:0;cursor:pointer}.card{background:#1b2840;padding:18px;margin:15px 0;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#b2c2df}</style><h1>◈ AgentBridge</h1><p>Local AI agent workflow coordinator</p><p id="mode"></p><div class="card"><h2>New workflow</h2><textarea id="prompt" placeholder="Describe the task"></textarea><p><select id="agents"><option value="claude,codex">Claude → Codex</option><option value="codex,claude">Codex → Claude</option><option value="claude">Claude only</option><option value="codex">Codex only</option></select><button id="start">Run workflow</button></p></div><h2>Workflows</h2><div id="items"></div><script>
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function refresh(){try{const config=await(await fetch('/api/config')).json();document.getElementById('mode').textContent=config.execution_enabled?'Execution enabled — use only in a restricted environment':'Execution disabled (safe default)';document.getElementById('start').disabled=!config.execution_enabled;const data=await(await fetch('/api/workflows')).json();document.getElementById('items').innerHTML=data.map(w=>'<div class="card"><b>'+esc(w.id.slice(0,8))+'</b> · '+esc(w.status)+'<p>'+esc(w.prompt)+'</p>'+w.steps.map(s=>'<details><summary>'+esc(s.agent)+' — '+esc(s.status)+'</summary><pre>'+esc(s.output)+'</pre></details>').join('')+'</div>').join('')||'<p>No workflows yet.</p>'}catch(e){document.getElementById('items').textContent=String(e)}}
document.getElementById('start').onclick=async()=>{const prompt=document.getElementById('prompt').value.trim();if(!prompt)return;const agents=document.getElementById('agents').value.split(',');const r=await fetch('/api/workflows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,agents})});if(!r.ok)alert(await r.text());refresh()};refresh();setInterval(refresh,3000);
</script></html>"""

class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, mime="application/json"):
        data=body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(data)
    def trusted_request(self):
        # Reject DNS-rebinding hostnames and cross-origin browser requests.
        host = self.headers.get("Host", "")
        expected = f"127.0.0.1:{self.server.server_port}"
        if host != expected:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{expected}"

    def do_GET(self):
        if not self.trusted_request():
            return self.respond(403,'{"error":"untrusted origin or host"}')
        if self.path=="/":
            return self.respond(200,HTML,"text/html")
        if self.path=="/api/config":
            return self.respond(200,json.dumps({"execution_enabled":EXECUTION}))
        if self.path=="/api/workflows":
            with database() as db:
                rows=[dict(r) for r in db.execute("SELECT * FROM workflows ORDER BY created DESC LIMIT 100")]
                for r in rows:
                    r["steps"]=[dict(s) for s in db.execute("SELECT position,agent,status,output FROM steps WHERE workflow_id=? ORDER BY position",(r["id"],))]
            return self.respond(200,json.dumps(rows))
        self.respond(404,'{"error":"not found"}')
    def do_POST(self):
        if not self.trusted_request():
            return self.respond(403,'{"error":"untrusted origin or host"}')
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.respond(415,'{"error":"application/json required"}')
        if self.path!="/api/workflows":
            return self.respond(404,'{"error":"not found"}')
        if not EXECUTION:
            return self.respond(403,'{"error":"execution disabled"}')
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=12000: raise ValueError()
            body=json.loads(self.rfile.read(size))
            prompt=body["prompt"].strip()
            agents=body["agents"]
            if not 0<len(prompt)<=10000 or not isinstance(agents,list) or not 1<=len(agents)<=3 or any(a not in ("claude","codex") for a in agents):
                raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):
            return self.respond(400,'{"error":"invalid workflow"}')
        wid=str(uuid.uuid4())
        with database() as db:
            db.execute("INSERT INTO workflows VALUES(?,?,?,?,?)",(wid,prompt,json.dumps(agents),"queued",timestamp()))
            for position,agent in enumerate(agents):
                db.execute("INSERT INTO steps(workflow_id,position,agent,status) VALUES(?,?,?,'queued')",(wid,position,agent))
        threading.Thread(target=process,args=(wid,),daemon=True).start()
        self.respond(201,json.dumps({"id":wid,"status":"queued"}))

def main():
    global EXECUTION
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--allow-execution",action="store_true")
    args=parser.parse_args()
    EXECUTION=args.allow_execution
    database().close()
    print(f"AgentBridge http://127.0.0.1:{args.port} (execution {'ON' if EXECUTION else 'OFF'})",flush=True)
    ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()

if __name__=="__main__":
    main()
