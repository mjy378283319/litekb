#!/usr/bin/env python3
"""LiteKB 客户端 —— WorkBuddy 用来自动归档/检索知识库。
依赖: requests
配置(环境变量): LITEKB_URL, LITEKB_TOKEN
"""
import os
import requests

URL = os.environ.get("LITEKB_URL", "http://192.168.5.x:6808").rstrip("/")
TOKEN = os.environ.get("LITEKB_TOKEN", "")


def _headers():
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def add(title: str, content: str, tags: list = None, source: str = "") -> dict:
    """写入一条笔记，返回 {id,title,...}。"""
    r = requests.post(
        f"{URL}/api/notes",
        json={"title": title, "content": content, "tags": tags or [], "source": source},
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def search(q: str, limit: int = 20) -> dict:
    """全文检索，返回 {count, results:[...]}。"""
    r = requests.get(
        f"{URL}/api/search",
        params={"q": q, "limit": limit},
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def list_notes(limit: int = 50) -> dict:
    r = requests.get(f"{URL}/api/notes", params={"limit": limit}, headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def get(nid: int) -> dict:
    r = requests.get(f"{URL}/api/notes/{nid}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def delete(nid: int) -> dict:
    r = requests.delete(f"{URL}/api/notes/{nid}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    # 自测
    print("search:", search("测试"))
