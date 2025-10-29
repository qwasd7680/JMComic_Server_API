import os
import time
import threading
import shutil
import asyncio
from http.client import responses
from typing import Dict
from fastapi import *
from starlette.concurrency import run_in_threadpool
import uvicorn
import jmcomic
from pathlib import Path

# --- 全局配置和初始化 ---
app = FastAPI()
current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")

# 自动创建 temp 目录
os.makedirs(FILE_PATH, exist_ok=True)

# 确保 jmcomic 客户端配置正确
os.environ['impl'] = 'html'
testClient = jmcomic.JmHtmlClient(postman=jmcomic.JmModuleConfig.new_postman(), domain_list=['18comic.vip'],
                                  retry_times=1)
try:
    testClient.search_site(search_query="胡桃")
except jmcomic.JmcomicException as e:
    if str(e)[:36] == "请求失败，响应状态码为403，原因为: [ip地区禁止访问/爬虫被识别]":
        os.environ['impl'] = 'api'
        print(f"Jmcomic Error: {e}")
        print("已为您更换到api方式，页码数可能会不可用")


# --- WebSocket 连接管理器 ---

class ConnectionManager:
    """管理活跃的 WebSocket 连接，使用 client_id 作为 key"""

    def __init__(self):
        # 存储 client_id 到 WebSocket 对象的映射
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """接受新连接，并将其关联到唯一的 client_id"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"[WebSocket] 新客户端连接 ID: {client_id}")

    def disconnect(self, client_id: str):
        """移除断开的连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"[WebSocket] 客户端断开连接 ID: {client_id}")

    async def send_personal_message(self, client_id: str, message: dict):
        """向特定客户端发送 JSON 消息"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
                print(f"[WebSocket] 成功向客户端 {client_id} 发送通知。")
            except Exception as e:
                print(f"[WebSocket Error] 向客户端 {client_id} 发送消息失败: {e}")
                self.disconnect(client_id)
        else:
            print(f"[WebSocket Error] 客户端 {client_id} 的连接不存在。")


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
    try:
        # 保持连接活跃，等待断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"[WebSocket Error] 接收循环出错: {e}")
        manager.disconnect(client_id)


# --- 阻塞任务处理函数 (在新线程中运行) ---

def sync_download_and_zip_task(album_id: int, client_id: str):
    """
    这是一个同步函数，包含原始的阻塞下载和压缩逻辑。
    任务完成后，它会通过 asyncio.run() 发送 WebSocket 通知。
    """
    print(f"[Task] 开始执行相册 {album_id} 的阻塞下载任务...")

    try:
        # 配置 Jmcomic 选项 (使用 Path 对象来构建 base_dir)
        optionStr = f"""
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
          base_dir: {FILE_PATH}
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
                zip_dir: {FILE_PATH}
                delete_original_file: true
        version: '2.1'
        """
        option = jmcomic.create_option_by_str(optionStr)
        jmcomic.JmModuleConfig.CLASS_DOWNLOADER = jmcomic.JmDownloader

        # 阻塞调用
        album_list = jmcomic.download_album(album_id, option)

        if not album_list:
            raise Exception("Album download failed or returned no results.")

        file_title = album_list[0].title
        zip_file_name = f"{file_title}.zip"
        zip_file_path = FILE_PATH / zip_file_name

        if zip_file_path.exists():
            # 启动延迟删除线程 (0.5 * 60 * 60 秒 = 30 分钟)
            threading.Thread(target=delayed_delete,
                             args=(zip_file_path, int(0.5 * 60 * 60)),
                             daemon=True).start()

            # 任务成功，使用 asyncio.run() 在当前线程中运行异步通知任务
            asyncio.run(manager.send_personal_message(client_id, {
                "status": "download_ready",
                "file_name": file_title,
                "message": f"文件 '{file_title}' 已完成处理，可以下载。"
            }))

        else:
            # 任务失败，发送 WebSocket 错误通知
            asyncio.run(manager.send_personal_message(client_id, {
                "status": "error",
                "file_name": file_title,
                "message": f"文件 '{file_title}' 未找到或处理失败。"
            }))

    except Exception as e:
        print(f"[Task Error] 下载任务发生异常: {e}")
        # 任务异常，发送 WebSocket 错误通知
        asyncio.run(manager.send_personal_message(client_id, {
            "status": "error",
            "file_name": "",
            "message": f"下载任务失败: {str(e)}"
        }))


# --- HTTP 任务启动路由 (替换原 download_album) ---

@app.post("/v1/download/album/{album_id}")
async def start_album_download(album_id: int, request: Request):
    """
    接收下载请求，立即返回 202，并在后台线程中启动耗时的下载任务。
    客户端必须在 POST body 中提供唯一的 client_id 来接收通知。
    """
    try:
        data = await request.json()
        client_id = data.get("client_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON containing 'client_id'.")

    if not client_id or client_id not in manager.active_connections:
        raise HTTPException(status_code=400, detail="WebSocket connection not established or client_id invalid.")

    # 立即在线程池中启动同步阻塞任务
    print(f"[Server] 接收下载请求，相册 ID: {album_id}，客户端 ID: {client_id}。任务将在后台启动...")

    # 使用 asyncio.create_task 包裹 run_in_threadpool，使其完全在后台异步运行
    asyncio.create_task(run_in_threadpool(sync_download_and_zip_task, album_id, client_id))

    # 返回 HTTP 202 Accepted 响应，告知客户端任务已接收
    return Response(
        status_code=202,
        content={"status": "processing", "message": "下载任务已在后台启动，请通过 WebSocket 监听 'download_ready' 通知。"}
    )


# --- HTTP 文件下载路由  ---

@app.get("/v1/download/{file_name}")
async def download_file(file_name: str):
    """
    客户端收到通知后，通过此路由下载文件。
    """
    zip_file_name = f"{file_name}.zip"
    file_path = FILE_PATH / zip_file_name  # 使用统一的 Path 对象和变量

    if file_path.exists():
        # 使用 FastAPI.responses.FileResponse
        return responses.FileResponse(file_path, filename=zip_file_name, media_type="application/zip")

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
    client = jmcomic.JmOption.default().new_jm_client()
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
    return aid_list


@app.get("/v1/info/{aid}")
async def info(aid: str):
    impl = os.environ.get("impl")
    optionStr = f"""
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
          base_dir: {FILE_PATH}
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
    option = jmcomic.create_option_by_str(optionStr)
    client = option.new_jm_client()
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
    if not file_path.exists():
        client.download_album_cover(album.album_id, file_path)
    return {"status": "success", "tag": album.tags, "view_count": album.views, "like_count": album.likes,
            "page_count": str(album.page_count), "method": os.environ.get("impl")}


@app.get("/v1/get/cover/{aid}")
async def getcover(aid: str):
    file_path = FILE_PATH / f"cover-{aid}.jpg"
    if file_path.exists():
        # 启动延迟删除线程 (0.5 * 60 * 60 秒 = 30 分钟)
        threading.Thread(target=delayed_delete, args=(file_path, int(0.5 * 60 * 60)), daemon=True).start()
        return responses.FileResponse(file_path, filename=f"cover.jpg", media_type="image/jpeg")
    return {"status": "error"}


@app.get("/v1/rank/{searchTime}")
async def rank(searchTime: str):
    client = jmcomic.JmOption.default().new_jm_client()
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

    return ranklist


if __name__ == '__main__':
    # 确保 uvicorn 运行时引用的是当前文件的 app 实例
    uvicorn.run("main:app", host="0.0.0.0", log_level="info")
