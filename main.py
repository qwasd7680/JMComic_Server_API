from datetime import datetime
import time
import fastapi
import os
import jmcomic
import uuid

app = fastapi.FastAPI()


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
        - plugin: zip # 压缩文件插件
          kwargs:
            level: photo 
            filename_rule: Ptitle 
            zip_dir: {current_dir}/tmep/{UUID}
            delete_original_file: true
    version: '2.1'
    """
    option = jmcomic.create_option_by_str(optionStr)
    jmcomic.download_album(album_id,option)
    file_path = f"{current_dir}/tmep/{UUID}/"
    file = os.listdir(file_path)[0]
    if os.path.exists(file_path):
        return fastapi.responses.FileResponse(f"{file_path}{file}",filename=f"{file}.zip")
    return {"status": "error"}