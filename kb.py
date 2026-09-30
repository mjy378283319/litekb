#!/usr/bin/env python3
# LiteKB - 轻量知识库（零依赖，仅用 Python 标准库 + SQLite FTS5）
# 启动: python kb.py   (或容器内 python /app/kb.py)
# 环境变量:
#   KB_DATA  数据目录(存放 kb.db)，默认 /data
#   KB_TOKEN 访问令牌(留空=无鉴权)；设置后 API 需 Header: Authorization: Bearer <token>
#   KB_HOST  监听地址，默认 0.0.0.0
#   KB_PORT  监听端口，默认 6808

import os
import re
import sys
import json
import time
import sqlite3
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_DIR = os.environ.get("KB_DATA", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "kb.db")
TOKEN = os.environ.get("KB_TOKEN", "").strip()
HOST = os.environ.get("KB_HOST", "0.0.0.0")
PORT = int(os.environ.get("KB_PORT", "6808"))


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )"""
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(title, tags, content, content_rowid=id)"
    )
    conn.commit()
    conn.close()


init_db()


def auth_ok(headers, query):
    if not TOKEN:
        return True
    h = headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:].strip() == TOKEN
    if query.get("token", [""])[0] == TOKEN:
        return True
    return False


def send_json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_html(handler, html_text, code=200):
    body = html_text.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_tags(tags):
    if isinstance(tags, list):
        tags = ",".join(tags)
    return ",".join([t.strip() for t in (tags or "").split(",") if t.strip()])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        if not auth_ok(self.headers, q):
            return send_json(self, {"error": "unauthorized"}, 401)
        path = parsed.path
        if path == "/health":
            return send_json(self, {"ok": True})
        if path == "/":
            return send_html(self, UI)
        if path == "/api/search":
            return self.api_search(q)
        if path == "/api/notes":
            return self.api_list(q)
        m = re.match(r"^/api/notes/(\d+)$", path)
        if m:
            return self.api_get(int(m.group(1)))
        return send_json(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        if not auth_ok(self.headers, q):
            return send_json(self, {"error": "unauthorized"}, 401)
        if parsed.path == "/api/notes":
            return self.api_create()
        return send_json(self, {"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        if not auth_ok(self.headers, q):
            return send_json(self, {"error": "unauthorized"}, 401)
        m = re.match(r"^/api/notes/(\d+)$", parsed.path)
        if m:
            return self.api_delete(int(m.group(1)))
        return send_json(self, {"error": "not found"}, 404)

    def api_create(self):
        raw = self._read_body()
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            return send_json(self, {"error": "invalid json"}, 400)
        title = str(data.get("title", "")).strip()
        content = str(data.get("content", ""))
        if not title and not content.strip():
            return send_json(self, {"error": "title or content required"}, 400)
        tags = parse_tags(data.get("tags", ""))
        source = str(data.get("source", ""))
        now = time.time()
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO notes(title,tags,content,source,created_at) VALUES(?,?,?,?,?)",
            (title, tags, content, source, now),
        )
        nid = cur.lastrowid
        try:
            conn.execute(
                "INSERT INTO notes_fts(rowid,title,tags,content) VALUES(?,?,?,?)",
                (nid, title, tags, content),
            )
        except Exception:
            pass
        conn.commit()
        conn.close()
        return send_json(
            self,
            {"id": nid, "title": title, "tags": tags, "source": source, "created_at": now},
            201,
        )

    def api_search(self, q):
        term = (q.get("q", [""])[0]).strip()
        tag = (q.get("tag", [""])[0]).strip()
        try:
            limit = max(1, min(100, int(q.get("limit", ["20"])[0])))
        except Exception:
            limit = 20
        conn = get_db()
        rows = []
        if term:
            sql = """SELECT n.id,n.title,n.tags,n.source,n.created_at,
                            snippet(notes_fts,2,'[',']','…',12) AS snip
                     FROM notes_fts f JOIN notes n ON n.id=f.rowid
                     WHERE notes_fts MATCH ? ORDER BY n.created_at DESC LIMIT ?"""
            phrase = '"' + term.replace('"', '""') + '"'
            rows = conn.execute(sql, (phrase, limit)).fetchall()
            if not rows:
                tokens = [t for t in re.split(r"\s+", term) if t]
                or_match = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
                rows = conn.execute(sql, (or_match, limit)).fetchall()
        else:
            wheres, params = [], []
            if tag:
                wheres.append("tags LIKE ?")
                params.append("%" + tag + "%")
            sql = (
                "SELECT id,title,tags,source,created_at FROM notes "
                + ("WHERE " + " AND ".join(wheres) if wheres else "")
                + " ORDER BY created_at DESC LIMIT ?"
            )
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        conn.close()
        return send_json(self, {"count": len(rows), "results": [dict(r) for r in rows]})

    def api_list(self, q):
        try:
            limit = max(1, min(200, int(q.get("limit", ["50"])[0])))
        except Exception:
            limit = 50
        conn = get_db()
        rows = conn.execute(
            "SELECT id,title,tags,source,created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return send_json(self, {"count": len(rows), "results": [dict(r) for r in rows]})

    def api_get(self, nid):
        conn = get_db()
        r = conn.execute(
            "SELECT id,title,tags,content,source,created_at FROM notes WHERE id=?", (nid,)
        ).fetchone()
        conn.close()
        if not r:
            return send_json(self, {"error": "not found"}, 404)
        return send_json(self, dict(r))

    def api_delete(self, nid):
        conn = get_db()
        conn.execute("DELETE FROM notes_fts WHERE rowid=?", (nid,))
        conn.execute("DELETE FROM notes WHERE id=?", (nid,))
        conn.commit()
        conn.close()
        return send_json(self, {"deleted": nid})


UI = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LiteKB</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#0f1115;color:#e6e6e6}
  header{padding:14px 18px;border-bottom:1px solid #23262d;font-weight:600;font-size:16px}
  .wrap{max-width:900px;margin:0 auto;padding:18px;display:grid;gap:20px}
  .card{background:#161a21;border:1px solid #23262d;border-radius:10px;padding:14px}
  label{display:block;font-size:12px;color:#9aa4b2;margin:8px 0 4px}
  input,textarea{width:100%;background:#0f1115;border:1px solid #2b3038;border-radius:6px;color:#e6e6e6;padding:8px;font:inherit}
  textarea{min-height:120px;resize:vertical}
  button{margin-top:10px;background:#3b82f6;border:0;color:#fff;padding:8px 14px;border-radius:6px;cursor:pointer;font:inherit}
  button.sec{background:#2b3038}
  .res{border-top:1px solid #23262d;padding:10px 0}
  .res h4{margin:0 0 4px;font-size:14px}
  .res .meta{color:#7c8694;font-size:12px}
  .res .snip{color:#aab2bf;font-size:13px;margin-top:4px;white-space:pre-wrap}
  .tag{display:inline-block;background:#1f2937;border:1px solid #2b3038;border-radius:999px;padding:1px 8px;margin:2px;font-size:12px;color:#9aa4b2}
  #status{font-size:13px;color:#7c8694}
  mark{background:#3b82f655;color:#cfe2ff}
</style>
</head>
<body>
<header>LiteKB · 轻量知识库</header>
<div class="wrap">
  <div class="card">
    <label>标题</label><input id="title" placeholder="如：WALL-E 舵机选型踩坑">
    <label>标签(逗号分隔)</label><input id="tags" placeholder="WALL-E,舵机,踩坑">
    <label>正文(支持多行)</label><textarea id="content" placeholder="把踩坑经过、结论、命令贴这里…"></textarea>
    <label>来源(可选)</label><input id="source" placeholder="如：WorkBuddy 2026-09-30">
    <button onclick="addNote()">保存笔记</button>
    <span id="status"></span>
  </div>
  <div class="card">
    <label>搜索关键词</label><input id="q" placeholder="如：舵机 扭矩">
    <button class="sec" onclick="search()">搜索</button>
    <div id="results" style="margin-top:10px"></div>
  </div>
</div>
<script>
const TOKEN = new URLSearchParams(location.search).get('token') || '';
const auth = TOKEN ? {Authorization:'Bearer '+TOKEN} : {};
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function addNote(){
  const body={title:title.value.trim(),tags:tags.value.trim(),content:content.value,source:source.value.trim()};
  const r=await fetch('/api/notes',{method:'POST',headers:{'Content-Type':'application/json',...auth},body:JSON.stringify(body)});
  const j=await r.json();
  status.textContent = r.ok ? '已保存 #'+j.id : ('失败: '+(j.error||r.status));
  if(r.ok){title.value='';tags.value='';content.value='';source.value='';}
}
async function search(){
  const qv=q.value.trim(); if(!qv) return;
  const r=await fetch('/api/search?q='+encodeURIComponent(qv),{headers:auth});
  const j=await r.json();
  let html='';
  if(!j.results.length) html='<div class="res">无匹配</div>';
  for(const x of j.results){
    const tags=(x.tags||'').split(',').filter(Boolean).map(t=>'<span class="tag">'+esc(t)+'</span>').join('');
    const snip=esc(x.snip||'').replace(/\[([^\]]+)\]/g,'<mark>$1</mark>');
    html+='<div class="res"><h4>#'+(x.id)+' '+esc(x.title)+'</h4><div class="meta">'+(x.source||'')+' · '+tags+'</div>'+
          (snip?'<div class="snip">'+snip+'</div>':'')+'</div>';
  }
  results.innerHTML=html;
}
</script>
</body>
</html>"""


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LiteKB running on http://{HOST}:{PORT}  (data={DATA_DIR}, token={'set' if TOKEN else 'none'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
