"""
Integration tests — require network access to JMComic service.

Run with:
    pytest tests/test_integration.py                    # all integration tests
    pytest tests/test_integration.py -m "not slow"      # skip slow download tests
    pytest -m integration                               # only integration tests

In CI (GitHub Actions), these run against the real JMComic service.
The server auto-detects impl mode (html/api) on first request.
"""
import time
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app, search_cache, rank_cache, album_info_cache, comment_cache

current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")
os.makedirs(FILE_PATH, exist_ok=True)

# Known test album — used across multiple tests
TEST_AID = 1225432
TEST_TAG = "全彩"


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches before each test to avoid stale data."""
    search_cache.clear()
    rank_cache.clear()
    album_info_cache.clear()
    comment_cache.clear()
    yield


# ============================================================
# Health check
# ============================================================

@pytest.mark.integration
class TestHealthCheck:
    def test_health_returns_ok(self, client):
        now = int(time.time() * 1000)
        resp = client.get(f"/v1/{now}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "jmcomic_server_api"
        assert int(data["latency"]) >= 0

    def test_health_latency_is_reasonable(self, client):
        now = int(time.time() * 1000)
        resp = client.get(f"/v1/{now}")
        latency = int(resp.json()["latency"])
        assert 0 <= latency < 10000  # <10s


# ============================================================
# Search
# ============================================================

@pytest.mark.integration
class TestSearch:
    def test_search_returns_results(self, client):
        resp = client.get(f"/v1/search/{TEST_TAG}/1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_search_result_structure(self, client):
        resp = client.get(f"/v1/search/{TEST_TAG}/1")
        first = resp.json()[0]
        assert "album_id" in first
        assert "title" in first
        assert isinstance(first["album_id"], str)
        assert isinstance(first["title"], str)
        assert len(first["album_id"]) > 0
        assert len(first["title"]) > 0

    def test_search_page_2(self, client):
        resp = client.get(f"/v1/search/{TEST_TAG}/2")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_search_different_tags(self, client):
        for tag in ["全彩", "CG集", "中文"]:
            resp = client.get(f"/v1/search/{tag}/1")
            assert resp.status_code == 200
            assert len(resp.json()) > 0

    def test_search_nonexistent_tag(self, client):
        resp = client.get("/v1/search/zzzznonexistenttag12345/1")
        # May return 200 with empty list, or 404/500 from upstream
        assert resp.status_code in (200, 404, 500, 502)
        if resp.status_code == 200:
            assert isinstance(resp.json(), list)

    def test_search_caching(self, client):
        resp1 = client.get(f"/v1/search/{TEST_TAG}/1")
        resp2 = client.get(f"/v1/search/{TEST_TAG}/1")
        assert resp1.json() == resp2.json()

    def test_search_invalid_num(self, client):
        assert client.get(f"/v1/search/{TEST_TAG}/0").status_code == 400
        assert client.get(f"/v1/search/{TEST_TAG}/101").status_code == 400
        assert client.get(f"/v1/search/{TEST_TAG}/-1").status_code == 400


# ============================================================
# Album info
# ============================================================

@pytest.mark.integration
class TestAlbumInfo:
    def test_info_returns_success(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_info_has_required_fields(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        data = resp.json()
        assert "tag" in data
        assert "view_count" in data
        assert "like_count" in data
        assert "page_count" in data
        assert "method" in data

    def test_info_tag_is_list(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        data = resp.json()
        assert isinstance(data["tag"], list)
        assert len(data["tag"]) > 0

    def test_info_counts_are_numeric(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        data = resp.json()
        assert int(data["view_count"]) > 0
        assert int(data["like_count"]) > 0

    def test_info_method_is_valid(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        data = resp.json()
        assert data["method"] in ("html", "api")

    def test_info_page_count_depends_on_mode(self, client):
        resp = client.get(f"/v1/info/{TEST_AID}")
        data = resp.json()
        if data["method"] == "html":
            assert int(data["page_count"]) > 0
        else:
            # api mode may return "0"
            assert data["page_count"] is not None

    def test_info_caching(self, client):
        resp1 = client.get(f"/v1/info/{TEST_AID}")
        resp2 = client.get(f"/v1/info/{TEST_AID}")
        assert resp1.json() == resp2.json()

    def test_info_nonexistent_album(self, client):
        resp = client.get("/v1/info/999999999")
        assert resp.status_code in (404, 500, 502)


# ============================================================
# Cover image
# ============================================================

@pytest.mark.integration
class TestCover:
    def test_cover_returns_jpeg(self, client):
        resp = client.get(f"/v1/get/cover/{TEST_AID}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    def test_cover_creates_temp_file(self, client):
        resp = client.get(f"/v1/get/cover/{TEST_AID}")
        assert resp.status_code == 200
        file_path = FILE_PATH / f"cover-{TEST_AID}.jpg"
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        file_path.unlink()

    def test_cover_nonexistent_album(self, client):
        resp = client.get("/v1/get/cover/999999999")
        assert resp.status_code in (404, 500)

    def test_cover_invalid_aid_characters(self, client):
        resp = client.get("/v1/get/cover/test<script>")
        assert resp.status_code == 400

    def test_cover_path_traversal(self, client):
        resp = client.get("/v1/get/cover/../../etc/passwd")
        assert resp.status_code in (400, 404, 422)


# ============================================================
# Ranking
# ============================================================

@pytest.mark.integration
class TestRanking:
    def test_rank_month(self, client):
        resp = client.get("/v1/rank/month")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_rank_week(self, client):
        resp = client.get("/v1/rank/week")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_rank_day(self, client):
        resp = client.get("/v1/rank/day")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_rank_result_structure(self, client):
        resp = client.get("/v1/rank/day")
        first = resp.json()[0]
        assert "aid" in first
        assert "title" in first
        assert isinstance(first["aid"], str)
        assert isinstance(first["title"], str)

    def test_rank_caching(self, client):
        resp1 = client.get("/v1/rank/month")
        resp2 = client.get("/v1/rank/month")
        assert resp1.json() == resp2.json()

    def test_rank_invalid_time(self, client):
        resp = client.get("/v1/rank/invalid")
        assert resp.status_code == 422


# ============================================================
# Download flow (WebSocket + POST + GET)
# ============================================================

@pytest.mark.integration
@pytest.mark.slow
class TestDownload:
    def test_full_download_flow(self, client):
        """Full async download flow: WS connect → POST → wait notification → GET zip."""
        client_id = "test-download-flow"
        with client.websocket_connect(f"/ws/notifications/{client_id}") as ws:
            # Start download
            resp = client.post(
                f"/v1/download/album/{TEST_AID}",
                json={"client_id": client_id},
            )
            assert resp.status_code == 202
            assert resp.json()["status"] == "processing"

            # Wait for WebSocket notification
            data = ws.receive_json()
            assert data["status"] == "download_ready"
            assert "file_name" in data
            file_title = data["file_name"]

        # Download the zip
        zip_path = FILE_PATH / f"{file_title}.zip"
        assert zip_path.exists()
        assert zip_path.stat().st_size > 0

        # Cleanup
        zip_path.unlink()
        assert not zip_path.exists()

    def test_download_missing_client_id(self, client):
        resp = client.post(f"/v1/download/album/{TEST_AID}", json={})
        assert resp.status_code == 400

    def test_download_invalid_json(self, client):
        resp = client.post(
            f"/v1/download/album/{TEST_AID}",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_download_file_not_found(self, client):
        resp = client.get("/v1/download/this-album-does-not-exist-12345")
        assert resp.status_code == 404

    def test_download_file_path_traversal(self, client):
        resp = client.get("/v1/download/../../etc/passwd")
        assert resp.status_code in (400, 404, 422)


# ============================================================
# Comments
# ============================================================

@pytest.mark.integration
class TestComments:
    def test_comments_returns_success(self, client):
        resp = client.get(f"/v1/comments/{TEST_AID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["aid"] == str(TEST_AID)
        assert data["page"] == 1

    def test_comments_has_required_fields(self, client):
        resp = client.get(f"/v1/comments/{TEST_AID}")
        data = resp.json()
        assert "page_size" in data
        assert "total" in data
        assert "page_count" in data
        assert "comment_count" in data
        assert isinstance(data["comments"], list)

    def test_comments_page_2(self, client):
        resp = client.get(f"/v1/comments/{TEST_AID}?page=2")
        assert resp.status_code == 200
        assert resp.json()["page"] == 2

    def test_comments_invalid_page(self, client):
        resp = client.get(f"/v1/comments/{TEST_AID}?page=0")
        assert resp.status_code == 400
        assert "page must be" in resp.json()["detail"]

    def test_comments_caching(self, client):
        resp1 = client.get(f"/v1/comments/{TEST_AID}")
        resp2 = client.get(f"/v1/comments/{TEST_AID}")
        assert resp1.json() == resp2.json()

    def test_comments_response_structure(self, client):
        resp = client.get(f"/v1/comments/{TEST_AID}")
        comments = resp.json()["comments"]
        if len(comments) > 0:
            comment = comments[0]
            assert "comment_id" in comment
            assert "content" in comment
            assert "username" in comment
            assert "is_spoiler" in comment
            assert "created_at" in comment
            assert "likes" in comment
            assert "replies" in comment
            assert isinstance(comment["replies"], list)


# ============================================================
# Health check (new /v1/health endpoint)
# ============================================================

@pytest.mark.integration
class TestHealthV2:
    def test_health_endpoint(self, client):
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "jmcomic_server_api"
