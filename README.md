# LiteKB · 轻量个人知识库（Unraid 部署）

零依赖、零构建：单文件 `kb.py`（仅用 Python 标准库 + SQLite FTS5 全文检索），用 `python:3.12-alpine` 跑起来，挂载即生效，无需写 Dockerfile、无需 `pip install`。

## 特性
- 写笔记：标题 / 标签 / 正文 / 来源
- 全文检索（FTS5，支持短语 + 分词回退，命中高亮片段）
- 列表 / 详情 / 删除
- 极简 Web UI（深色）+ REST API
- 可选 `KB_TOKEN` 鉴权（Bearer）
- 数据存 SQLite，落 Unraid 共享盘，容器删数据不丢

## 部署（Unraid）

### 方式 A：Docker Compose（推荐）
1. 在 Unraid 任意处建目录，如 `/mnt/user/appdata/litekb/`，把 `kb.py` 与 `docker-compose.yml` 放进去。
2. 编辑 `docker-compose.yml`：把 `KB_TOKEN` 改成你的强令牌（或留空关闭鉴权）。
3. 确认共享 `kbdata` 已存在（前次 SiYuan 教程建的；没有就 Shares 里建一个）。
4. Unraid 终端执行：
   ```bash
   cd /mnt/user/appdata/litekb
   docker compose up -d
   ```
5. 浏览器开 `http://<Unraid-IP>:6808`。

### 方式 B：Docker Run（无 Compose 插件）
```bash
docker run -d --name litekb --restart=unless-stopped \
  -p 6808:6808 \
  -e KB_TOKEN=你的强令牌 \
  -e KB_DATA=/data \
  -v /mnt/user/kbdata/litekb:/data \
  -v /mnt/user/appdata/litekb/kb.py:/app/kb.py:ro \
  python:3.12-alpine \
  python /app/kb.py
```

### 固定 IP（br0，可选）
若想和 SiYuan 一样用固定 IP（如 `192.168.5.143`），把端口映射换成：
`--net=br0 --ip=192.168.5.143`（docker run）或 compose 里加 `networks` 配置，访问地址即 `http://192.168.5.143:6808`。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | Web UI |
| GET | `/health` | 健康检查 `{"ok":true}` |
| POST | `/api/notes` | 建笔记 `{title,tags[],content,source}` |
| GET | `/api/notes?limit=50` | 列表 |
| GET | `/api/notes/{id}` | 详情 |
| GET | `/api/search?q=关键词&limit=20` | 全文检索 |
| DELETE | `/api/notes/{id}` | 删除 |

鉴权：设了 `KB_TOKEN` 后，所有 API 需带 `Authorization: Bearer <token>`（或 `?token=`）。

## 启用鉴权（可选）
`docker-compose.yml` 的 `KB_TOKEN` 与 WorkBuddy 技能里的 `litekb_config.json` 的 `token` 填**同一个强令牌**；两处都留空则关闭鉴权（仅家庭内网建议）。

## 与 WorkBuddy 联动
`kb_client.py` 是客户端封装（`add()` / `search()` / `get()` / `delete()`），**优先读环境变量、其次读同目录 `litekb_config.json`**。已打包成 WorkBuddy 技能 `litekb`（位于 `~/.workbuddy/skills/litekb/`），实现「任务结束自动写入、开始前自动检索」的本地兜底库（ima 仍是云端主库）。

📘 完整部署 + 调用步骤见 **`部署与调用指南.md`**。

## 备份
直接备份 Unraid 共享 `kbdata/litekb/`（SQLite 文件 `kb.db` + `-wal`/`-shm`）。升级前停容器再拷。
