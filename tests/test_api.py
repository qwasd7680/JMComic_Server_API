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
    assert int(response.json().get("latency")) >= 0


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


def test_search_album_returns_proper_error_for_invalid_num():
    client = TestClient(app)
    response = client.get("/v1/search/test/0")
    assert response.status_code == 400

    response = client.get("/v1/search/test/101")
    assert response.status_code == 400


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


def test_info_nonexistent_album():
    client = TestClient(app)
    response = client.get("/v1/info/999999999")
    # Should return 404 (MissingAlbumPhotoException) or 500/502
    assert response.status_code in (404, 500, 502)


def test_rank_month():
    client = TestClient(app)
    response = client.get("/v1/rank/month")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0
    first = response.json()[0]
    assert "aid" in first
    assert "title" in first


def test_rank_week():
    client = TestClient(app)
    response = client.get("/v1/rank/week")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_rank_day():
    client = TestClient(app)
    response = client.get("/v1/rank/day")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_rank_invalid_time():
    client = TestClient(app)
    response = client.get("/v1/rank/invalid")
    assert response.status_code == 422  # FastAPI enum validation


def test_getcover_invalid_aid():
    client = TestClient(app)
    response = client.get("/v1/get/cover/../../etc/passwd")
    assert response.status_code in (400, 404, 422)


def test_getcover_not_found():
    client = TestClient(app)
    response = client.get("/v1/get/cover/999999999")
    assert response.status_code == 404


def test_download_file_not_found():
    client = TestClient(app)
    response = client.get("/v1/download/nonexistent-album-title")
    assert response.status_code == 404


def test_download_file_invalid_name():
    client = TestClient(app)
    response = client.get("/v1/download/../../etc/passwd")
    assert response.status_code in (400, 404, 422)


def test_download_album_missing_client_id():
    client = TestClient(app)
    response = client.post("/v1/download/album/123", json={})
    assert response.status_code == 400
    assert "client_id" in response.json()["detail"].lower()


def test_download_album_invalid_json():
    client = TestClient(app)
    response = client.post(
        "/v1/download/album/123",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


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
        assert data["status"] == "download_ready"
        assert "file_name" in data
        file_title = data["file_name"]

    zip_file_path = FILE_PATH / f"{file_title}.zip"
    assert zip_file_path.exists()
    zip_file_path.unlink()
    assert zip_file_path.exists() == False


def test_cors_headers():
    client = TestClient(app)
    response = client.options(
        "/v1/123456",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
