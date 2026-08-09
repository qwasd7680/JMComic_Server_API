import os
import time
import logging
import threading
import shutil
import asyncio
from enum import Enum
from functools import wraps
from typing import Dict, Optional, Tuple, Any, Set
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import uvicorn
import jmcomic
from pathlib import Path
from datetime import datetime, timedelta

# --- Logging configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Global configuration and initialization ---
app = FastAPI()

# CORS middleware — allow all origins for watchOS client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")

# Auto-create temp directory
os.makedirs(FILE_PATH, exist_ok=True)

# Configure implementation mode — lazy init to avoid blocking startup
_impl_mode: Optional[str] = None
_impl_lock = threading.Lock()


def get_impl_mode() -> str:
    """Get implementation mode (html or api), lazy-init with thread-safe double-checked locking."""
    global _impl_mode
    if _impl_mode is None:
        with _impl_lock:
            if _impl_mode is None:
                os.environ['impl'] = 'html'
                testClient = jmcomic.JmHtmlClient(
                    postman=jmcomic.JmModuleConfig.new_postman(),
                    domain_list=['18comic.vip'],
                    retry_times=1
                )
                try:
                    testClient.search_site(search_query="胡桃")
                    _impl_mode = 'html'
                except jmcomic.JmcomicException as e:
                    _impl_mode = 'api'
                    error_msg = str(e)
                    if error_msg[:36] == "请求失败，响应状态码为403，原因为: [ip地区禁止访问/爬虫被识别]":
                        logger.warning("Jmcomic Error: %s", e)
                        logger.warning("已为您更换到api方式，页码数可能会不可用")
                    else:
                        logger.warning("HTML模式初始化失败，切换到API模式: %s", e)
                except Exception as e:
                    _impl_mode = 'api'
                    logger.warning("警告: HTML模式测试时发生意外错误，使用API模式: %s", e)
                os.environ['impl'] = _impl_mode
    return _impl_mode


# Client connection pool — reuse client instead of creating new each time
_client_cache: Optional[jmcomic.JmcomicClient] = None
_client_lock = threading.Lock()


def get_jm_client() -> jmcomic.JmcomicClient:
    """Get shared JmComic client instance (thread-safe)."""
    global _client_cache
    if _client_cache is None:
        with _client_lock:
            if _client_cache is None:
                get_impl_mode()  # ensure impl is set
                _client_cache = jmcomic.JmOption.default().new_jm_client()
    return _client_cache


# Configuration string template factories
def create_download_option_string(base_dir: Path) -> str:
    """Create download option configuration string."""
    return f"""
        client:
          cache: null
          domain: []
          impl: api
          postman:
            meta_data:
              headers: null
              impersonate: chrome
              proxies: {{}}
            type: curl_cffi
          retry_times: 5
        dir_rule:
          base_dir: {base_dir}
          rule: Bd_Pname
        download:
          cache: true
          image:
            decode: true
            suffix: null
          threading:
            image: 30
            photo: 8
        log: true
        plugins:
          valid: log
          after_album:
            - plugin: zip
              kwargs:
                level: photo
                filename_rule: Ptitle
                zip_dir: {base_dir}
                delete_original_file: true
        version: '2.1'
        """


def create_info_option_string(base_dir: Path, impl: str) -> str:
    """Create info-fetch option configuration string."""
    return f"""
        client:
          cache: null
          domain: []
          impl: {impl}
          postman:
            meta_data:
              headers: null
              impersonate: chrome
              proxies: {{}}
            type: curl_cffi
          retry_times: 5
        dir_rule:
          base_dir: {base_dir}
          rule: Bd_Pname
        download:
          cache: false
          image:
            decode: true
            suffix: webp
          threading:
            image: 30
            photo: 8
        log: true
        plugins:
          valid: log
        version: '2.1'
        """


# --- Path safety helper ---
def safe_file_path(base_dir: Path, filename: str) -> Optional[Path]:
    """
    Sanitize filename and verify the resolved path stays within base_dir.
    Returns the resolved Path if safe, None otherwise.
    """
    safe_name = filename.replace('/', '').replace('\\', '').replace('..', '')
    if not safe_name or safe_name != filename:
        return None
    try:
        file_path = (base_dir / safe_name).resolve()
        base_resolved = base_dir.resolve()
        if not str(file_path).startswith(str(base_resolved) + os.sep) and file_path != base_resolved:
            return None
        return file_path
    except (ValueError, OSError):
        return None


# --- Simple in-memory cache with TTL, max-size eviction, and cleanup ---
class SimpleCache:
    """Simple TTL cache with max-size eviction."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_size = max_size
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value, return None if expired."""
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if datetime.now() < expiry:
                    return value
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value with TTL. Evicts oldest entry if over max_size."""
        with self.lock:
            self.cache[key] = (value, datetime.now() + self.ttl)
            if len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]

    def cleanup(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = datetime.now()
        removed = 0
        with self.lock:
            expired_keys = [k for k, (_, exp) in self.cache.items() if exp <= now]
            for k in expired_keys:
                del self.cache[k]
                removed += 1
        return removed

    def clear(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()


# Cache instances
search_cache = SimpleCache(ttl_seconds=300, max_size=500)        # search: 5 min
rank_cache = SimpleCache(ttl_seconds=600, max_size=100)          # ranking: 10 min
album_info_cache = SimpleCache(ttl_seconds=600, max_size=1000)   # album info: 10 min


# --- Background cache cleanup task ---
async def periodic_cache_cleanup(interval: int = 300):
    """Periodically clean up expired cache entries."""
    while True:
        await asyncio.sleep(interval)
        total = search_cache.cleanup() + rank_cache.cleanup() + album_info_cache.cleanup()
        if total > 0:
            logger.info("Cache cleanup: removed %d expired entries", total)


# --- Pending tasks tracking (prevents GC and enables error tracking) ---
_pending_tasks: Set[asyncio.Task] = set()


def _remove_pending_task(task: asyncio.Task) -> None:
    """Remove a completed task from the pending set."""
    _pending_tasks.discard(task)


# --- WebSocket connection manager ---
class ConnectionManager:
    """Manage WebSocket connections with thread-safe send interface."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.loop = asyncio.get_running_loop()
        logger.info("[WebSocket] Client %s connected.", client_id)

    async def _send_and_close(self, client_id: str, message: dict):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_json(message)
            logger.info("[WebSocket] Sent message to client %s: %s", client_id, message)
            try:
                await websocket.close()
            except Exception:
                pass
            self.active_connections.pop(client_id, None)
        else:
            logger.warning("[WebSocket] No connection for client %s, cannot send.", client_id)


manager = ConnectionManager()


# --- Delayed file/folder cleanup ---
def delayed_delete(path: Path, delay: int):
    """Delete a file or directory after a delay (runs in a daemon thread)."""
    time.sleep(delay)
    try:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                logger.info("[Cleanup] Deleted folder: %s", path)
            elif path.is_file():
                path.unlink()
                logger.info("[Cleanup] Deleted file: %s", path)
    except Exception as e:
        logger.error("[Cleanup Error] Failed to delete %s: %s", path, e)


# --- Exception handling decorator for jmcomic errors ---
def handle_jmcomic_errors(func):
    """
    Decorator that catches jmcomic exceptions and raises appropriate HTTPException.
    Apply to endpoints that make jmcomic blocking calls.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except jmcomic.MissingAlbumPhotoException as e:
            raise HTTPException(status_code=404, detail=f"Album not found: id={e.error_jmid}")
        except jmcomic.JsonResolveFailException:
            raise HTTPException(status_code=502, detail="JSON解析错误")
        except jmcomic.RequestRetryAllFailException:
            raise HTTPException(status_code=504, detail="重试次数耗尽")
        except jmcomic.JmcomicException as e:
            raise HTTPException(status_code=500, detail=f"出现其他错误: {e}")
    return wrapper


# --- SearchTime Enum for rank endpoint validation ---
class SearchTime(str, Enum):
    day = "day"
    week = "week"
    month = "month"


# --- WebSocket route ---
@app.websocket("/ws/notifications/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time download notifications."""
    await manager.connect(client_id, websocket)


# --- Blocking task handler (runs in thread pool) ---
def sync_download_and_zip_task(album_id: int, client_id: str):
    """Synchronous download & zip logic. Notifies client via WebSocket on completion."""
    logger.info("[Task] Starting blocking download for album %s ...", album_id)

    try:
        optionStr = create_download_option_string(FILE_PATH)
        option = jmcomic.create_option_by_str(optionStr)
        jmcomic.JmModuleConfig.CLASS_DOWNLOADER = jmcomic.JmDownloader
        album_list = jmcomic.download_album(album_id, option)

        if not album_list:
            raise Exception("Album download failed or returned no results.")

        file_title = album_list[0].title
        zip_file_name = f"{file_title}.zip"
        zip_file_path = FILE_PATH / zip_file_name

        if zip_file_path.exists():
            message = {
                "status": "download_ready",
                "file_name": file_title,
                "message": f"文件 '{file_title}' 已完成处理，可以下载。"
            }
        else:
            message = {
                "status": "error",
                "file_name": file_title,
                "message": f"文件 '{file_title}' 未找到或处理失败。"
            }
        if manager.loop:
            future = asyncio.run_coroutine_threadsafe(
                manager._send_and_close(client_id, message), manager.loop
            )
            try:
                future.result(timeout=10)
            except Exception as e:
                logger.error("[Task] Failed to send message via main loop: %s", e)
        else:
            logger.error("[Task] No event loop recorded, cannot send WebSocket notification.")
    except Exception as e:
        if manager.loop:
            fut = asyncio.run_coroutine_threadsafe(
                manager._send_and_close(
                    client_id,
                    {"status": "error", "file_name": "", "message": f"下载任务失败: {str(e)}"}
                ),
                manager.loop
            )
            try:
                fut.result(timeout=10)
            except Exception as ee:
                logger.error("[Task] Failed to send error notification: %s", ee)


# --- HTTP route: start album download ---
@app.post("/v1/download/album/{album_id}")
async def start_album_download(album_id: int, request: Request):
    try:
        data = await request.json()
        client_id = data.get("client_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON containing 'client_id'.")

    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    logger.info("[Server] Received download request: album=%s, client=%s. Starting in background...", album_id, client_id)

    task = asyncio.create_task(run_in_threadpool(sync_download_and_zip_task, album_id, client_id))
    _pending_tasks.add(task)
    task.add_done_callback(_remove_pending_task)

    return JSONResponse(
        status_code=202,
        content={
            "status": "processing",
            "message": "下载任务已在后台启动，请通过 WebSocket 监听 'download_ready' 通知。"
        }
    )


# --- HTTP route: download file ---
@app.get("/v1/download/{file_name}")
async def download_file(file_name: str):
    """
    Client receives notification and downloads the zip file through this route.
    Uses safe_file_path helper for path-traversal protection.
    """
    safe_path = safe_file_path(FILE_PATH, f"{file_name}.zip")
    if safe_path is None:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "msg": "Invalid file name."}
        )

    if safe_path.exists() and safe_path.is_file():
        return FileResponse(safe_path, filename=f"{file_name}.zip", media_type="application/zip")

    return JSONResponse(
        status_code=404,
        content={"status": "error", "msg": "File not found or has expired."}
    )


# --- HTTP route: health check ---
@app.get("/v1/{timestamp}")
async def read_root(timestamp: float):
    """Health check endpoint. Returns server latency."""
    nowtimestamp = int(time.time() * 1000)
    timedelta_ms = nowtimestamp - int(timestamp)
    return {
        "status": "ok",
        "app": "jmcomic_server_api",
        "latency": str(timedelta_ms),
        "version": "1.0"
    }


# --- HTTP route: search albums ---
@app.get("/v1/search/{tag}/{num}")
@handle_jmcomic_errors
async def search_album(tag: str, num: int):
    # Validate num range (path parameter, validated manually)
    if num < 1 or num > 100:
        raise HTTPException(status_code=400, detail="num must be between 1 and 100")

    cache_key = f"search:{tag}:{num}"
    cached_result = search_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    client = get_jm_client()
    page: jmcomic.JmSearchPage = await run_in_threadpool(
        client.search_site, search_query=f'+{tag}', page=num
    )

    aid_list = [{'album_id': album_id, 'title': title} for album_id, title in page]

    search_cache.set(cache_key, aid_list)
    return aid_list


# --- HTTP route: album info ---
@app.get("/v1/info/{aid}")
@handle_jmcomic_errors
async def info(aid: str):
    cache_key = f"album_info:{aid}"
    cached_result = album_info_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    client = get_jm_client()
    impl = get_impl_mode()

    page = await run_in_threadpool(client.search_site, search_query=aid)

    if not hasattr(page, 'album') or page.album is None:
        raise HTTPException(status_code=404, detail=f"Album not found: id={aid}")

    album: jmcomic.JmAlbumDetail = page.single_album
    file_path = FILE_PATH / f"cover-{album.album_id}.jpg"

    if not file_path.exists():
        optionStr = create_info_option_string(FILE_PATH, impl)
        option = jmcomic.create_option_by_str(optionStr)
        download_client = option.new_jm_client()
        await run_in_threadpool(download_client.download_album_cover, album.album_id, str(file_path))

    result = {
        "status": "success",
        "tag": album.tags,
        "view_count": album.views,
        "like_count": album.likes,
        "page_count": str(album.page_count),
        "method": impl
    }

    album_info_cache.set(cache_key, result)
    return result


# --- HTTP route: get cover image ---
@app.get("/v1/get/cover/{aid}")
async def getcover(aid: str):
    """
    Get album cover image. Uses safe_file_path helper for path-traversal protection.
    """
    # Whitelist characters for aid (alphanumeric, dash, underscore)
    safe_aid = ''.join(c for c in aid if c.isalnum() or c in '-_')
    if not safe_aid or safe_aid != aid:
        raise HTTPException(status_code=400, detail="Invalid album ID")

    safe_path = safe_file_path(FILE_PATH, f"cover-{safe_aid}.jpg")
    if safe_path is None:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if safe_path.exists() and safe_path.is_file():
        # Schedule delayed cleanup (30 minutes)
        threading.Thread(
            target=delayed_delete, args=(safe_path, int(0.5 * 60 * 60)), daemon=True
        ).start()
        return FileResponse(safe_path, filename="cover.jpg", media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Cover not found")


# --- HTTP route: ranking ---
@app.get("/v1/rank/{searchTime}")
@handle_jmcomic_errors
async def rank(searchTime: SearchTime):
    cache_key = f"rank:{searchTime.value}"
    cached_result = rank_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    client = get_jm_client()
    if searchTime == SearchTime.month:
        pages: jmcomic.JmCategoryPage = await run_in_threadpool(client.month_ranking, 1)
    elif searchTime == SearchTime.week:
        pages: jmcomic.JmCategoryPage = await run_in_threadpool(client.week_ranking, 1)
    elif searchTime == SearchTime.day:
        pages: jmcomic.JmCategoryPage = await run_in_threadpool(client.day_ranking, 1)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid searchTime: {searchTime}")

    ranklist = [{"aid": album_id, "title": title} for album_id, title in pages]

    rank_cache.set(cache_key, ranklist)
    return ranklist


# --- Startup event ---
@app.on_event("startup")
async def startup_event():
    """Start background cache cleanup task on application startup."""
    cleanup_task = asyncio.create_task(periodic_cache_cleanup())
    _pending_tasks.add(cleanup_task)


# --- Entry point ---
if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", log_level="info")
