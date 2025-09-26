import shutil
import threading
import time
import fastapi
import os
import jmcomic
from pathlib import Path
import uvicorn

app = fastapi.FastAPI()

os.environ['impl'] = 'html'
testClient = client = jmcomic.JmHtmlClient(postman=jmcomic.JmModuleConfig.new_postman(),domain_list=['18comic.vip'],retry_times=1)
try:
    page = testClient.search_site(search_query="胡桃")
except jmcomic.JmcomicException as e:
    if str(e)[:36] == "请求失败，响应状态码为403，原因为: [ip地区禁止访问/爬虫被识别]":
        os.environ['impl'] = 'api'
        print(e)
        print("已为您更换到api方式，页码数可能会不可用")

def delayed_delete(path: Path, delay: int):
    """
    延迟删除，传入路径（可以是文件或者文件夹）以及延迟时间（单位：秒）
    示例用法：
        threading.Thread(target=delayed_delete, args=(Path(f"{file_path}"), 0.5 * 60 * 60), daemon=True).start()
    """
    time.sleep(delay)
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()

"""
    API V1.0
    初始版本
"""
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
    return {"status": "ok", "app": "jmcomic_server_api", "latency": ms,"version": "1.0"}


@app.get("/v1/download/album/{album_id}")
async def download_album(album_id: int):
    """
    :param album_id: 本子号
    :return: 文件名，用于下载
    """
    current_dir = os.getcwd()
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
      base_dir: {current_dir}/temp/
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
            zip_dir: {current_dir}/temp/
            delete_original_file: true
    version: '2.1'
    """
    option = jmcomic.create_option_by_str(optionStr)
    jmcomic.JmModuleConfig.CLASS_DOWNLOADER = jmcomic.JmDownloader
    album = jmcomic.download_album(album_id, option)
    file_path = f"{current_dir}/temp"
    file = album[0].title
    if os.path.exists(file_path):
        threading.Thread(target=delayed_delete, args=(Path(f"{file_path}/{file}.zip"), 0.5 * 60 * 60), daemon=True).start()
        return {"status": "success","msg": "Download Complete","file_name": file}
    return {"status": "error"}

@app.get("/v1/download/{file_name}")
async def download_file(file_name: str):
    current_dir = os.getcwd()
    file_path = f"{current_dir}/tmep/{file_name}.zip"
    if os.path.exists(file_path):
        return fastapi.responses.FileResponse(file_path, filename=f"{file_name}.zip")
    return {"status": "error","msg": "File not found"}


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
    current_dir = os.getcwd()
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
          base_dir: {current_dir}/temp
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
    file_path = f"{current_dir}/temp/cover-{album.album_id}.jpg"
    if not os.path.exists(file_path):
        client.download_album_cover(album.album_id, f'./temp/cover-{album.album_id}.jpg')
    return {"status": "success", "tag": album.tags,"view_count": album.views,"like_count":album.likes,"page_count":str(album.page_count),"method":os.environ.get("impl")}


@app.get("/v1/get/cover/{aid}")
async def getcover(aid: str):
    current_dir = os.getcwd()
    file_path = f"{current_dir}/temp/cover-{aid}.jpg"
    if os.path.exists(file_path):
        threading.Thread(target=delayed_delete, args=(Path(f"{file_path}"), 0.5 * 60 * 60), daemon=True).start()
        return fastapi.responses.FileResponse(f"{file_path}", filename=f"cover.jpg")
    return {"status": "error"}


@app.get("/v1/rank/{searchTime}")
async def rank(searchTime: str):
    client = jmcomic.JmOption.default().new_jm_client()
    pages: jmcomic.JmCategoryPage = client.categories_filter(
        page=1,
        time=jmcomic.JmMagicConstants.TIME_ALL,  # 时间选择全部，具体可以写什么请见JmMagicConstants
        category=jmcomic.JmMagicConstants.CATEGORY_ALL,  # 分类选择全部，具体可以写什么请见JmMagicConstants
        order_by=jmcomic.JmMagicConstants.ORDER_BY_LATEST,  # 按照更新时间排序，具体可以写什么请见JmMagicConstants
    )
    if searchTime == "month":
        pages: jmcomic.JmCategoryPage = client.month_ranking(1)
    elif searchTime == "week":
        pages: jmcomic.JmCategoryPage = client.week_ranking(1)
    elif searchTime == "day":
        pages: jmcomic.JmCategoryPage = client.day_ranking(1)
    ranklist = []
    templist = []
    for page in pages:
        for i in page:
            templist.append(i)
        ranklist.append({"aid": templist[0], "title": templist[1]})
        templist = []
    return ranklist


if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", log_level="info")
