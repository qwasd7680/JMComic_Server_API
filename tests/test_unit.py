import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import (
    app,
    safe_file_path,
    SimpleCache,
    SearchTime,
    ConnectionManager,
    FILE_PATH,
    _serialize_comment,
)


# ============================================================
# safe_file_path — path traversal protection
# ============================================================

class TestSafeFilePath:
    """Tests for the safe_file_path helper."""

    def test_valid_filename(self, tmp_path):
        result = safe_file_path(tmp_path, "test.txt")
        assert result is not None
        assert result == (tmp_path / "test.txt").resolve()

    def test_valid_zip_filename(self, tmp_path):
        result = safe_file_path(tmp_path, "some-album-title.zip")
        assert result is not None
        assert result.name == "some-album-title.zip"

    def test_rejects_slash(self, tmp_path):
        assert safe_file_path(tmp_path, "../etc/passwd") is None

    def test_rejects_backslash(self, tmp_path):
        assert safe_file_path(tmp_path, "..\\etc\\passwd") is None

    def test_rejects_dot_dot(self, tmp_path):
        assert safe_file_path(tmp_path, "..") is None

    def test_rejects_empty_string(self, tmp_path):
        assert safe_file_path(tmp_path, "") is None

    def test_rejects_only_slashes(self, tmp_path):
        assert safe_file_path(tmp_path, "///") is None

    def test_rejects_path_traversal_in_middle(self, tmp_path):
        assert safe_file_path(tmp_path, "foo/../bar") is None

    def test_accepts_unicode(self, tmp_path):
        result = safe_file_path(tmp_path, "［酸菜鱼ゅ°］.zip")
        assert result is not None

    def test_accepts_spaces(self, tmp_path):
        result = safe_file_path(tmp_path, "my file name.zip")
        assert result is not None

    def test_accepts_dashes_underscores(self, tmp_path):
        result = safe_file_path(tmp_path, "cover-12345.jpg")
        assert result is not None


# ============================================================
# SimpleCache — TTL, eviction, cleanup
# ============================================================

class TestSimpleCache:
    """Tests for the SimpleCache class."""

    def test_set_and_get(self):
        cache = SimpleCache(ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = SimpleCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = SimpleCache(ttl_seconds=1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_max_size_eviction(self):
        cache = SimpleCache(ttl_seconds=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_cleanup_removes_expired(self):
        cache = SimpleCache(ttl_seconds=1)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        time.sleep(1.1)
        removed = cache.cleanup()
        assert removed == 2
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_cleanup_keeps_valid(self):
        cache = SimpleCache(ttl_seconds=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        removed = cache.cleanup()
        assert removed == 0
        assert cache.get("k1") == "v1"

    def test_clear(self):
        cache = SimpleCache(ttl_seconds=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_overwrite_key(self):
        cache = SimpleCache(ttl_seconds=60)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_thread_safety(self):
        cache = SimpleCache(ttl_seconds=60, max_size=1000)
        errors = []

        def writer(start):
            try:
                for i in range(100):
                    cache.set(f"key-{start}-{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    cache.get("key-0-0")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================
# SearchTime Enum
# ============================================================

class TestSearchTimeEnum:
    """Tests for the SearchTime enum."""

    def test_valid_values(self):
        assert SearchTime.day == "day"
        assert SearchTime.week == "week"
        assert SearchTime.month == "month"

    def test_enum_members(self):
        assert set(SearchTime) == {SearchTime.day, SearchTime.week, SearchTime.month}


# ============================================================
# ConnectionManager
# ============================================================

class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_initial_state(self):
        mgr = ConnectionManager()
        assert mgr.active_connections == {}
        assert mgr.loop is None

    def test_send_and_close_no_connection(self):
        mgr = ConnectionManager()
        # Should not raise when client_id not found
        import asyncio
        asyncio.run(mgr._send_and_close("nonexistent", {"status": "test"}))


# ============================================================
# Health check endpoint (no network needed)
# ============================================================

class TestHealthCheck:
    """Tests for the /v1/{timestamp} health check endpoint."""

    def test_health_check(self):
        client = TestClient(app)
        now = int(time.time() * 1000)
        response = client.get(f"/v1/{now}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "jmcomic_server_api"
        assert "latency" in data
        assert int(data["latency"]) >= 0

    def test_health_check_with_float_timestamp(self):
        client = TestClient(app)
        now = time.time() * 1000
        response = client.get(f"/v1/{now}")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ============================================================
# Input validation (no network needed)
# ============================================================

class TestInputValidation:
    """Tests for input validation on endpoints."""

    def test_search_num_too_low(self):
        client = TestClient(app)
        response = client.get("/v1/search/test/0")
        assert response.status_code == 400
        assert "num must be between" in response.json()["detail"]

    def test_search_num_too_high(self):
        client = TestClient(app)
        response = client.get("/v1/search/test/101")
        assert response.status_code == 400
        assert "num must be between" in response.json()["detail"]

    def test_search_num_valid(self):
        """Valid num should not return 400 (may return other errors due to network)."""
        client = TestClient(app)
        # num=1 is valid, won't get 400 for validation
        # May get network errors, but not 400 for num
        response = client.get("/v1/search/test/1")
        assert response.status_code != 400 or "num must be" not in response.json().get("detail", "")

    def test_rank_invalid_searchtime(self):
        client = TestClient(app)
        response = client.get("/v1/rank/invalid")
        assert response.status_code == 422  # FastAPI enum validation

    def test_download_missing_client_id(self):
        client = TestClient(app)
        response = client.post("/v1/download/album/123", json={})
        assert response.status_code == 400
        assert "client_id" in response.json()["detail"].lower()

    def test_download_invalid_json(self):
        client = TestClient(app)
        response = client.post(
            "/v1/download/album/123",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_getcover_invalid_aid(self):
        client = TestClient(app)
        response = client.get("/v1/get/cover/../../../etc/passwd")
        # Should be rejected by path validation or character filter
        assert response.status_code in (400, 404, 422)

    def test_getcover_special_characters(self):
        client = TestClient(app)
        response = client.get("/v1/get/cover/test<script>")
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    def test_download_file_invalid_name(self):
        client = TestClient(app)
        response = client.get("/v1/download/../../etc/passwd")
        assert response.status_code in (400, 404, 422)

    def test_download_file_not_found(self):
        client = TestClient(app)
        response = client.get("/v1/download/nonexistent-album-title")
        assert response.status_code == 404

    def test_comments_page_too_low(self):
        client = TestClient(app)
        response = client.get("/v1/comments/12345?page=0")
        assert response.status_code == 400
        assert "page must be" in response.json()["detail"]

    def test_comments_negative_page(self):
        client = TestClient(app)
        response = client.get("/v1/comments/12345?page=-1")
        assert response.status_code == 400
        assert "page must be" in response.json()["detail"]


# ============================================================
# CORS middleware
# ============================================================

class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self):
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


# ============================================================
# _serialize_comment helper
# ============================================================

class TestSerializeComment:
    """Tests for the _serialize_comment helper."""

    def test_basic_fields(self):
        from unittest.mock import MagicMock
        comment = MagicMock()
        comment.comment_id = "123"
        comment.album_id = "456"
        comment.user_id = "789"
        comment.parent_comment_id = None
        comment.content = "hello"
        comment.username = "user1"
        comment.nickname = "User One"
        comment.is_spoiler = False
        comment.created_at = "2025-01-01"
        comment.likes = 42
        comment.replies = []

        result = _serialize_comment(comment)
        assert result["comment_id"] == "123"
        assert result["album_id"] == "456"
        assert result["content"] == "hello"
        assert result["likes"] == 42
        assert result["replies"] == []

    def test_nested_replies(self):
        from unittest.mock import MagicMock
        reply = MagicMock()
        reply.comment_id = "r1"
        reply.album_id = None
        reply.user_id = None
        reply.parent_comment_id = "123"
        reply.content = "reply"
        reply.username = "user2"
        reply.nickname = None
        reply.is_spoiler = True
        reply.created_at = "2025-01-02"
        reply.likes = None
        reply.replies = []

        parent = MagicMock()
        parent.comment_id = "123"
        parent.album_id = "456"
        parent.user_id = "789"
        parent.parent_comment_id = None
        parent.content = "parent"
        parent.username = "user1"
        parent.nickname = "User One"
        parent.is_spoiler = False
        parent.created_at = "2025-01-01"
        parent.likes = 10
        parent.replies = [reply]

        result = _serialize_comment(parent)
        assert len(result["replies"]) == 1
        assert result["replies"][0]["content"] == "reply"
        assert result["replies"][0]["is_spoiler"] is True
