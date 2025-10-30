from fastapi.testclient import TestClient
import time
import os
from pathlib import Path
from main import app

current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")
os.makedirs(FILE_PATH, exist_ok=True)


def test_read_root():
    client = TestClient(app)
    nowtimestamp = int(time.time() * 1000)
    response = client.get("/v1/{0}".format(nowtimestamp))
    timedelta = int(time.time() * 1000) - nowtimestamp
    ms = int(timedelta)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
    assert response.json().get("app") == "jmcomic_server_api"
    assert int(response.json().get("latency")) <= ms
    assert int(response.json().get("latency")) > 0


def test_search_album():
    client = TestClient(app)
    tag = "全彩"
    num = 1
    response = client.get("/v1/search/{0}/{1}".format(tag, num))
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0
    first_album = response.json()[0]
    assert "album_id" in first_album
    assert "title" in first_album


def test_get_cover_and_info():
    client = TestClient(app)
    aid = 1225432
    response = client.get("/v1/info/{0}".format(aid))
    assert response.status_code == 200
    info_json = response.json()
    assert info_json.get("status") == "success"
    assert "全彩" in info_json.get("tag", [])
    assert int(info_json.get("view_count")) > 0
    assert int(info_json.get("like_count")) > 0
    assert info_json.get("page_count") == "0"
    response = client.get("/v1/get/cover/{0}".format(aid))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    file_path = FILE_PATH / f"cover-{aid}.jpg"
    assert file_path.exists()
    file_path.unlink()
    assert file_path.exists() == False


def test_download_album():
    client = TestClient(app)
    aid = 1225432
    client_id = "1145141919810"
    with client.websocket_connect(f"/ws/notifications/{client_id}") as websocket:
        response = client.post(f"/v1/download/album/{aid}", json={"client_id": client_id})
        assert response.status_code == 202
        assert response.json() == {
            "status": "processing",
            "message": "下载任务已在后台启动，请通过 WebSocket 监听 'download_ready' 通知。"
        }
        data = websocket.receive_json()
        assert data == {
            "status": "download_ready",
            "file_name": "［酸菜鱼ゅ°］ヒルチャールに败北した胡桃 表情、台词差分",
            "message": f"文件 '［酸菜鱼ゅ°］ヒルチャールに败北した胡桃 表情、台词差分' 已完成处理，可以下载。"
        }
    client.get("/v1/download/album/{0}".format(aid))
    file_title = "［酸菜鱼ゅ°］ヒルチャールに败北した胡桃 表情、台词差分"
    zip_file_name = f"{file_title}.zip"
    zip_file_path = FILE_PATH / zip_file_name
    assert zip_file_path.exists() == True
    zip_file_path.unlink()
    assert zip_file_path.exists() == False