import os
import time
import threading
import shutil
import asyncio
from typing import Dict, Optional, Tuple, Any
from fastapi import *
from fastapi.responses import JSONResponse, FileResponse
from starlette.concurrency import run_in_threadpool
import uvicorn
import jmcomic
from pathlib import Path
from datetime import datetime, timedelta

# --- 全局配置和初始化 ---
app = FastAPI()
current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")

# 自动创建 temp 目录
os.makedirs(FILE_PATH, exist_ok=True)

# 配置实现方式 - 延迟初始化，避免启动时网络调用
# 使用环境变量或在首次请求时确定
_impl_mode: Optional[str] = None


def get_impl_mode() -> str:
    """获取实现模式，延迟初始化避免启动阻塞"""
    global _impl_mode
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
            if str(e)[:36] == "请求失败，响应状态码为403，原因为: [ip地区禁止访问/爬虫被识别]":
                _impl_mode = 'api'
                print(f"Jmcomic Error: {e}")
                print("已为您更换到api方式，页码数可能会不可用")
            else:
                _impl_mode = 'api'
        os.environ['impl'] = _impl_mode
    return _impl_mode


# 客户端连接池 - 重用客户端连接而不是每次创建新的
_client_cache: Optional[jmcomic.JmcomicClient] = None
_client_lock = threading.Lock()


def get_jm_client() -> jmcomic.JmcomicClient:
    """获取共享的 JmComic 客户端实例"""
    global _client_cache
    if _client_cache is None:
        with _client_lock:
            if _client_cache is None:
                get_impl_mode()  # 确保 impl 已设置
                _client_cache = jmcomic.JmOption.default().new_jm_client()
    return _client_cache


# 配置字符串模板工厂 - 避免重复构建字符串
def create_download_option_string(base_dir: Path) -> str:
    """创建下载选项配置字符串"""
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
    """创建信息获取选项配置字符串"""
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


# --- 简单的内存缓存实现 ---

class SimpleCache:
    """简单的TTL缓存实现，用于缓存频繁访问的数据"""
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，如果过期返回None"""
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if datetime.now() < expiry:
                    return value
                else:
                    # 清理过期条目
                    del self.cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        with self.lock:
            self.cache[key] = (value, datetime.now() + self.ttl)

    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()


# 创建缓存实例
# 搜索结果缓存5分钟
search_cache = SimpleCache(ttl_seconds=300)
# 排行榜缓存10分钟（更新不频繁）
rank_cache = SimpleCache(ttl_seconds=600)
# 相册信息缓存10分钟
album_info_cache = SimpleCache(ttl_seconds=600)


# --- WebSocket 连接管理器 ---

class ConnectionManager:
    """
    管理 WebSocket 连接，记录主事件循环并提供线程安全的发送接口。
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        print(f"[WebSocket] 客户端 {client_id} 已连接。")

    async def _send_and_close(self, client_id: str, message: dict):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_json(message)
            print(f"[WebSocket] 发送消息给客户端 {client_id}: {message}")
            try:
                await websocket.close()
            except Exception:
                pass
            self.active_connections.pop(client_id, None)
        else:
            print(f"[WebSocket] 未找到客户端 {client_id} 的连接，无法发送消息。")

manager = ConnectionManager()


# --- 辅助函数：延迟删除（保持用户原有逻辑） ---

def delayed_delete(path: Path, delay: int):
    """
    延迟删除，传入路径（可以是文件或者文件夹）以及延迟时间（单位：秒）
    """
    time.sleep(delay)
    try:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"[Cleanup] 后台线程：成功删除文件夹 {path}")
            elif path.is_file():
                path.unlink()
                print(f"[Cleanup] 后台线程：成功删除文件 {path}")
    except Exception as e:
        print(f"[Cleanup Error] 删除文件/文件夹 {path} 失败: {e}")


# --- WebSocket 路由 ---

@app.websocket("/ws/notifications/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket 连接端点，用于实时通知。
    客户端连接时必须提供唯一的 client_id。
    """
    await manager.connect(client_id, websocket)


# --- 阻塞任务处理函数 (在新线程中运行) ---

def sync_download_and_zip_task(album_id: int, client_id: str):
    """
    这是一个同步函数，包含原始的阻塞下载和压缩逻辑。
    任务完成后，它会通过 asyncio.run() 发送 WebSocket 通知。
    """
    print(f"[Task] 开始执行相册 {album_id} 的阻塞下载任务...")

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
            future = asyncio.run_coroutine_threadsafe(manager._send_and_close(client_id, message), manager.loop)
            try:
                future.result(timeout=10)
            except Exception as e:
                print(f"[Task] 通过主循环发送消息失败: {e}")
        else:
            print("[Task] 未记录到主事件循环，无法发送 WebSocket 通知。")
    except Exception as e:
        if manager.loop:
            fut = asyncio.run_coroutine_threadsafe(
                manager._send_and_close(client_id,
                                        {"status": "error", "file_name": "", "message": f"下载任务失败: {str(e)}"}),
                manager.loop
            )
            try:
                fut.result(timeout=10)
            except Exception as ee:
                print(f"[Task] 发送异常通知失败: {ee}")


# --- HTTP 任务启动路由 (替换原 download_album) ---

@app.post("/v1/download/album/{album_id}")
async def start_album_download(album_id: int, request: Request):
    try:
        data = await request.json()
        client_id = data.get("client_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON containing 'client_id'.")

    print(f"[Server] 接收下载请求，相册 ID: {album_id}，客户端 ID: {client_id}。任务将在后台启动...")

    asyncio.create_task(run_in_threadpool(sync_download_and_zip_task, album_id, client_id))

    # 返回 HTTP 202 Accepted 响应，告知客户端任务已接收
    return JSONResponse(status_code=202, content={"status": "processing",
                                                  "message": "下载任务已在后台启动，请通过 WebSocket 监听 'download_ready' 通知。"})


# --- HTTP 文件下载路由  ---

@app.get("/v1/download/{file_name}")
async def download_file(file_name: str):
    """
    客户端收到通知后，通过此路由下载文件。
    """
    zip_file_name = f"{file_name}.zip"
    file_path = FILE_PATH / zip_file_name  # 使用统一的 Path 对象和变量

    if file_path.exists():
        return FileResponse(file_path, filename=zip_file_name, media_type="application/zip")

    return Response(
        status_code=404,
        content={"status": "error", "msg": "File not found or has expired."}
    )


# --- 其他原有路由 (保持不变) ---

@app.get("/v1/{timestamp}")
async def read_root(timestamp: float):
    """
    用于检查服务是否可用
    :param timestamp: 毫秒级时间戳（可以包含小数）
    :return:延迟
    """
    nowtimestamp = int(time.time() * 1000)
    timedelta = nowtimestamp - int(timestamp)
    ms = str(int(timedelta))
    return {"status": "ok", "app": "jmcomic_server_api", "latency": ms, "version": "1.0"}


@app.get("/v1/search/{tag}/{num}")
async def search_album(tag: str, num: int):
    # 检查缓存
    cache_key = f"search:{tag}:{num}"
    cached_result = search_cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    client = get_jm_client()
    try:
        page: jmcomic.JmSearchPage = client.search_site(search_query=f'+{tag}', page=num)
    except jmcomic.MissingAlbumPhotoException as e:
        return {"status": "error", "message": f'id={e.error_jmid}的本子不存在'}
    except jmcomic.JsonResolveFailException:
        return {"status": "error", "message": "JSON解析错误"}
    except jmcomic.RequestRetryAllFailException:
        return {"status": "error", "message": "重试次数耗尽"}
    except jmcomic.JmcomicException as e:
        return {"status": "error", "message": f"出现其他错误:{e}"}
    
    aid_list = []
    for album_id, title in page:
        aid_list.append({'album_id': album_id, 'title': title})
    
    # 缓存结果
    search_cache.set(cache_key, aid_list)
    return aid_list


@app.get("/v1/info/{aid}")
async def info(aid: str):
    # 检查缓存
    cache_key = f"album_info:{aid}"
    cached_result = album_info_cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 使用共享客户端获取相册信息
    client = get_jm_client()
    impl = get_impl_mode()
    
    try:
        page = client.search_site(search_query=aid)
    except jmcomic.MissingAlbumPhotoException as e:
        return {"status": "error", "message": f'id={e.error_jmid}的本子不存在'}
    except jmcomic.JsonResolveFailException:
        return {"status": "error", "message": "JSON解析错误"}
    except jmcomic.RequestRetryAllFailException:
        return {"status": "error", "message": "重试次数耗尽"}
    except jmcomic.JmcomicException as e:
        return {"status": "error", "message": f"出现其他错误:{e}"}
    
    album: jmcomic.JmAlbumDetail = page.single_album
    file_path = FILE_PATH / f"cover-{album.album_id}.jpg"
    
    # 只有在需要下载封面时才创建自定义客户端
    if not file_path.exists():
        optionStr = create_info_option_string(FILE_PATH, impl)
        option = jmcomic.create_option_by_str(optionStr)
        download_client = option.new_jm_client()
        download_client.download_album_cover(album.album_id, str(file_path))
    
    result = {"status": "success", "tag": album.tags, "view_count": album.views, "like_count": album.likes,
              "page_count": str(album.page_count), "method": impl}
    
    # 缓存结果
    album_info_cache.set(cache_key, result)
    return result


@app.get("/v1/get/cover/{aid}")
async def getcover(aid: str):
    file_path = FILE_PATH / f"cover-{aid}.jpg"
    if file_path.exists():
        # 启动延迟删除线程 (0.5 * 60 * 60 秒 = 30 分钟)
        threading.Thread(target=delayed_delete, args=(file_path, int(0.5 * 60 * 60)), daemon=True).start()
        return FileResponse(file_path, filename=f"cover.jpg", media_type="image/jpeg")
    return {"status": "error"}


@app.get("/v1/rank/{searchTime}")
async def rank(searchTime: str):
    # 检查缓存
    cache_key = f"rank:{searchTime}"
    cached_result = rank_cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    client = get_jm_client()
    pages: jmcomic.JmCategoryPage = client.categories_filter(
        page=1,
        time=jmcomic.JmMagicConstants.TIME_ALL,
        category=jmcomic.JmMagicConstants.CATEGORY_ALL,
        order_by=jmcomic.JmMagicConstants.ORDER_BY_LATEST,
    )
    if searchTime == "month":
        pages: jmcomic.JmCategoryPage = client.month_ranking(1)
    elif searchTime == "week":
        pages: jmcomic.JmCategoryPage = client.week_ranking(1)
    elif searchTime == "day":
        pages: jmcomic.JmCategoryPage = client.day_ranking(1)

    ranklist = []
    for album_id, title in pages:
        ranklist.append({"aid": album_id, "title": title})

    # 缓存结果
    rank_cache.set(cache_key, ranklist)
    return ranklist


if __name__ == '__main__':
    # 确保 uvicorn 运行时引用的是当前文件的 app 实例
    uvicorn.run("main:app", host="0.0.0.0", log_level="info")
