# RESTful API For JMComic-Crawler-Python

[![Docker Image CI](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/docker-image.yml/badge.svg)](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/docker-image.yml)
[![Pytest](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/python-app.yml/badge.svg)](https://github.com/qwasd7680/JMComic_Server_API/actions/workflows/python-app.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-green.svg)

## 项目介绍

基于 **FastAPI** 的 RESTful API，封装 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) 的接口，便于开发 C/S 应用。

**核心特性：**
- 非阻塞式异步架构，耗时下载任务在后台线程执行
- WebSocket 实时推送下载进度通知
- 内存缓存（搜索 5min / 排行榜 10min / 详情 10min）
- 自动检测 impl 模式（html / api），兼容不同地区访问
- 下载文件 30 分钟后自动清理

## 快速开始

### 本地部署

```shell
git clone https://github.com/qwasd7680/JMComic_Server_API
cd JMComic_Server_API
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 11111
```

生产环境：
```shell
gunicorn -k uvicorn.workers.UvicornWorker main:app --workers 4 --bind 0.0.0.0:11111
```

### Docker

```shell
docker build -t jmcomic-api .
docker run -p 11111:11111 jmcomic-api
```

### HuggingFace Space

1. 新建 Space → Docker → blank
2. 创建 `Dockerfile`：
```dockerfile
FROM ghcr.io/qwasd7680/jmcomic_server_api:latest
COPY . /app
WORKDIR /app
RUN mkdir -p /app/temp && chmod 777 /app/temp
RUN pip install -r requirements.txt
EXPOSE 7860
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--workers", "4", "--bind", "0.0.0.0:7860"]
```
3. 提交后等待 build，点击 "Embed this Space" → 复制 "Direct URL"

## API 接口

### 健康检查

```
GET /v1/{timestamp}
```

```json
{"status": "ok", "app": "jmcomic_server_api", "latency": "644", "version": "1.0"}
```

### 排行榜

```
GET /v1/rank/{time}
```

| 参数 | 说明 |
|------|------|
| `time` | `day` / `week` / `month` |

```json
[{"aid": "1208626", "title": "..."}, {"aid": "1208625", "title": "..."}]
```

### 搜索

```
GET /v1/search/{tag}/{num}
```

| 参数 | 说明 |
|------|------|
| `tag` | 搜索关键词（标签、作者、标题等） |
| `num` | 页码（1-100） |

```json
[{"album_id": "1208664", "title": "..."}, {"album_id": "1208641", "title": "..."}]
```

### 本子详情

```
GET /v1/info/{aid}
```

```json
{"status": "success", "tag": ["全彩", "CG集"], "view_count": 102497, "like_count": 42, "page_count": "20", "method": "html"}
```

> `page_count` 在 api 模式下可能返回 `"0"`（因上游接口限制）。`method` 字段指示当前使用的模式。

### 封面图片

```
GET /v1/get/cover/{aid}
```

直接返回 `image/jpeg`，可嵌入 `<img>` 或 SwiftUI `AsyncImage`。

### 下载本子（异步 WebSocket 流程）

**步骤 1：建立 WebSocket 连接**
```
ws://{host}/ws/notifications/{client_id}
```
`client_id` 为客户端生成的唯一标识（如 UUID）。

**步骤 2：发起下载请求**
```
POST /v1/download/album/{album_id}
Content-Type: application/json
Body: {"client_id": "your-client-uuid"}
```
服务器立即返回 `202 Accepted`，任务在后台执行。

**步骤 3：等待 WebSocket 通知**
```json
{"status": "download_ready", "file_name": "本子标题", "message": "文件已完成处理，可以下载。"}
```

**步骤 4：下载文件**
```
GET /v1/download/{file_name}
```
返回 zip 文件。

## 测试

```shell
# 单元测试（无需网络）
pytest tests/test_unit.py -v

# 集成测试（需要网络）
pytest tests/test_integration.py -v

# 全部测试
pytest -v
```

## 技术栈

- **框架**：FastAPI + Starlette
- **服务器**：Uvicorn / Gunicorn
- **爬虫库**：[jmcomic](https://github.com/hect0x7/JMComic-Crawler-Python)
- **HTTP 客户端**：httpx + curl_cffi
- **Python**：3.12+

## 致谢

<a href="https://github.com/hect0x7/JMComic-Crawler-Python">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=hect0x7&repo=JMComic-Crawler-Python" />
  </picture>
</a>
