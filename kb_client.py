#!/usr/bin/env python3
"""LiteKB 客户端 —— WorkBuddy 用来自动归档/检索知识库。
零依赖：仅用 Python 标准库 urllib。
配置优先级: 环境变量 LITEKB_URL / LITEKB_TOKEN  >  同目录 litekb_config.json  >  内置默认
"""
import os
import json
import urllib.request
import urllib.error
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_cfg():
    """读取配置：环境变量优先，其次同目录 litekb_config.json，最后内置默认。"""
    url = (os.environ.get("LITEKB_URL") or "").strip()
    token = (os.environ.get("LITEKB_TOKEN") or "").strip()
    cfg_path = os.path.join(_HERE, "litekb_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except Exception:
            cfg = {}
        if not url:
            url = (cfg.get("url") or "").strip()
        if not token:
            token = (cfg.get("token") or "").strip()
    if not url:
        url = "http://192.168.5.x:6808"
    return url.rstrip("/"), token


URL, TOKEN = _load_cfg()


def _headers():
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    return h


def _req(method, path, data=None):
    if not URL or "192.168.5.x" in URL:
        raise RuntimeError("LITEKB_URL 还是占位符，请在 litekb_config.json 或环境变量里填真实地址")
    req = urllib.request.Request(
        URL + path,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None,
        headers=_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"LiteKB {method} {path} -> {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LiteKB 连接失败 {URL}{path}: {e.reason}")


def add(title, content, tags=None, source=""):
    return _req("POST", "/api/notes", {"title": title, "content": content, "tags": tags or [], "source": source})


def search(q, limit=20):
    return _req("GET", "/api/search?" + urllib.parse.urlencode({"q": q, "limit": limit}))


def list_notes(limit=50):
    return _req("GET", "/api/notes?" + urllib.parse.urlencode({"limit": limit}))


def get(nid):
    return _req("GET", "/api/notes/" + str(nid))


def delete(nid):
    return _req("DELETE", "/api/notes/" + str(nid))


if __name__ == "__main__":
    print("config url:", URL, "| token set:", bool(TOKEN))
    print("health:", _req("GET", "/health"))
