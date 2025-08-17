import shutil
import threading
from datetime import datetime
import time
import fastapi
import os
import jmcomic
import uuid
from pathlib import Path
import uvicorn

app = fastapi.FastAPI()

def delayed_delete(path: Path, delay: int):
    time.sleep(delay)
    if path.exists() and path.is_dir():
        shutil.rmtree(path)

class FirstImageDownloader(jmcomic.JmDownloader):
    def do_filter(self, detail):
        if detail.is_photo():
            photo = detail
            return photo[:1]
        return detail

@app.get("/{timestamp}")
async def read_root(timestamp: int):
    nowtimestamp = time.time()
    nowtime = datetime.fromtimestamp(nowtimestamp)
    timedelta = nowtime - datetime.fromtimestamp(timestamp)
    ms = str(int(timedelta.total_seconds() *1000 %1000))
    return {"status": "ok","app": "jmcomic_server_api","latency": ms}

@app.get("/download/album/{album_id}")
async def download_album(album_id: int):
    UUID = uuid.uuid1()
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
      base_dir: {current_dir}/tmep/
      rule: Bd_Pname
    download:
      cache: false
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
            zip_dir: {current_dir}/tmep/{UUID}
            delete_original_file: true
    version: '2.1'
    """
    option = jmcomic.create_option_by_str(optionStr)
    jmcomic.download_album(album_id,option)
    file_path = f"{current_dir}/tmep/{UUID}"
    file = os.listdir(file_path)[0]
    if os.path.exists(file_path):
        threading.Thread(target=delayed_delete, args=(Path(f"{file_path}"), 4*60*60), daemon=True).start()
        return fastapi.responses.FileResponse(f"{file_path}/{file}",filename=f"{file}.zip")
    return {"status": "error"}

@app.get("/search/{tag}/{num}")
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

@app.get("/info/{aid}")
async def info(aid: str):
    UUID = uuid.uuid1()
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
          base_dir: {current_dir}/tmep/{UUID}
          rule: Bd_Pname
        download:
          cache: false
          image:
            decode: true
            suffix: null
          threading:
            image: 30
            photo: 8
        log: true
        plugins:
          valid: log
        version: '2.1'
        """
    option = jmcomic.create_option_by_str(optionStr)
    client = jmcomic.JmOption.default().new_jm_client()
    jmcomic.JmModuleConfig.CLASS_DOWNLOADER = FirstImageDownloader
    try:
        page = client.search_site(search_query= aid)
    except jmcomic.MissingAlbumPhotoException as e:
        return {"status": "error", "message": f'id={e.error_jmid}的本子不存在'}
    except jmcomic.JsonResolveFailException:
        return {"status": "error", "message": "JSON解析错误"}
    except jmcomic.RequestRetryAllFailException:
        return {"status": "error", "message": "重试次数耗尽"}
    except jmcomic.JmcomicException as e:
        return {"status": "error", "message": f"出现其他错误:{e}"}
    album: jmcomic.JmAlbumDetail = page.single_album
    jmcomic.download_album(int(album.album_id),option)
    file_path = f"{current_dir}/tmep/{UUID}/{album.title}/"
    file = os.listdir(file_path)[0]
    if os.path.exists(file_path):
        threading.Thread(target=delayed_delete, args=(Path(f"{file_path}"), 4 * 60 * 60), daemon=True).start()
        return fastapi.responses.FileResponse(f"{file_path}/{file}", filename=f"{file}")
    return {"status": "error"}

@app.get("/rank/{time}")
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
    ranklist = [];templist = []
    for page in pages:
        for i in page:
            templist.append(i)
        ranklist.append({"aid":templist[0], "title":templist[1]})
        templist = []
    return ranklist

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", log_level="info")
