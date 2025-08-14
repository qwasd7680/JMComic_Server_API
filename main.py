from datetime import datetime
import jmcomic
import time
from fastapi import FastAPI
app = FastAPI()


@app.get("/{timestamp}")
async def read_root(timestamp: int):
    nowtimestamp = time.time()
    nowtime = datetime.fromtimestamp(nowtimestamp)
    timedelta = nowtime - datetime.fromtimestamp(timestamp)
    ms = str(int(timedelta.total_seconds() *1000 %1000))
    return {"status": "ok","app": "jmcomic_server_api","latency": ms}
