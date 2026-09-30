---
name: litekb
description: 自建轻量知识库 LiteKB（Unraid Docker，SQLite FTS5，零依赖）的自动归档与检索客户端。当用户要求把任务记录/踩坑/结论自动存到本地知识库、或在任务开始前自动检索本地知识库以避免重复踩坑时使用。作为 ima 云端库之外的本地兜底。要求 LiteKB 服务本机可达——家庭 LAN 直连；公司外网需经 lucky 反代（HTTPS + 转发 /ws 不需要，LiteKB 纯 REST）暴露公网。不可达时必须如实说明，切勿假装已存档。
---

# LiteKB 技能（本地知识库兜底）

LiteKB 是跑在 Unraid 上的单文件轻量知识库（kb.py，纯 Python 标准库 + SQLite FTS5）。
它是 ima 云端库之外的**本地兜底**：家庭网络可达、数据完全自托管；公司外网需先把 LiteKB 经 lucky 反代暴露。

## 何时用
- 任务结束：把本次任务的记录、踩坑、结论、关键命令写入 LiteKB（标签含项目名 + 关键词）。
- 任务开始：先检索 LiteKB，确认是否已有同类踩坑/结论可复用（与 ima 并行查，避免重复踩坑）。
- 用户明确说"存本地知识库""查本地库""归档到 LiteKB"。

## 配置文件
`litekb_config.json`（与本 SKILL.md 同目录）：
```json
{ "url": "http://192.168.5.x:6808", "token": "" }
```
- `url`：LiteKB 服务地址（末尾别带斜杠）。
- `token`：若服务端设了 `KB_TOKEN`，填这里；留空则服务端无鉴权。
- 也可用环境变量 `LITEKB_URL` / `LITEKB_TOKEN` 覆盖（优先级高于配置文件）。

## 客户端
`kb_client.py`（同目录）提供：
- `add(title, content, tags=[], source="")` → 写一条笔记，返回 `{id,...}`
- `search(q, limit=20)` → 全文检索，返回 `{count, results}`，每条含 `snip` 高亮片段
- `list_notes(limit=50)` / `get(nid)` / `delete(nid)`

直接用：
```python
import sys; sys.path.insert(0, "<skill_dir>")
from kb_client import add, search
add("WALL-E 舵机选型踩坑", "DS3225 需 3x 安全倍数", tags=["WALL-E","舵机"], source="WorkBuddy 2026-09-30")
hits = search("舵机 扭矩")
```

## 归档规范（与 ima 对齐）
- 标题：`项目名 + 主题`，如 `bambu-spool 汉印多标签偏移`。
- 标签：项目名 + 关键分类（踩坑/结论/配置/命令），务必带项目名，便于跨项目检索。
- 正文：踩坑经过 + 根因 + 解决命令/配置 + 验证结果（存"错误全量"，不要只存干净版）。
- source：写 `WorkBuddy YYYY-MM-DD`。
- **必须存踩坑/错误**，不要只存概览。

## 检索规范
- 任务开始前先 `search(项目名)` 与 `search(关键词)`，命中则把结论前置，避免重复踩坑。
- 与 ima 并行检索（跨项目反模式清单仍适用）。

## 可达性前提（重要）
- 家庭局域网：PC 与 Unraid 同网 → 直接用 LAN 地址，完全自动。
- 公司外网：LiteKB 需经 lucky 反代暴露公网（纯 HTTP/REST，无需 WebSocket），公司 PC 无需 Tailscale/管理员即可用。
- 若 LiteKB 不可达：**不要假装已存档**，如实告知用户，回到可达网络再补；ima 仍可作为云端主库兜底。

## API 速查（服务端）
- `GET /health` → `{"ok":true}`
- `POST /api/notes` body `{title,tags[],content,source}`
- `GET /api/search?q=关键词&limit=20`
- `GET /api/notes?limit=50` / `GET /api/notes/{id}` / `DELETE /api/notes/{id}`
- 鉴权：设了 `KB_TOKEN` 后需 `Authorization: Bearer <token>`
