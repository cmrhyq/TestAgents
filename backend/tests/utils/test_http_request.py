"""`HttpRequest` 与 `get_random_pc_ua` 的行为。

覆盖 UA 生成、初始化鉴权、URL 构建、各 HTTP 方法、重试、路径提取与请求头编码。
"""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout


@pytest.fixture(autouse=True)
def _mock_dependencies():
    """替换 `CacheManager`，产出缓存 mock 供断言。"""
    mock_cache = MagicMock()
    with patch("src.utils.http.request.CacheManager") as mock_cache_cls:
        mock_cache_cls.get_instance.return_value = mock_cache
        yield {"cache": mock_cache}


# ---------------------------------------------------------------------------
#  get_random_pc_ua 测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetRandomPcUa:
    """UA 生成结果的字符串形态与随机性。"""

    def test_returns_string(self):
        from src.utils.http.request import get_random_pc_ua

        ua = get_random_pc_ua()
        assert isinstance(ua, str)
        assert len(ua) > 0

    def test_contains_mozilla(self):
        from src.utils.http.request import get_random_pc_ua

        ua = get_random_pc_ua()
        assert "Mozilla/5.0" in ua

    def test_randomness(self):
        from src.utils.http.request import get_random_pc_ua

        uas = {get_random_pc_ua() for _ in range(20)}
        assert len(uas) > 1


# ---------------------------------------------------------------------------
#  HttpRequest 初始化测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestInit:
    """初始化参数与各鉴权方式。"""

    def test_base_url_set(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            assert client.base_url == "https://api.example.com"

    def test_timeout_configuration(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com", connect_timeout=15, read_timeout=5)
            assert client.timeout == (15, 5)

    def test_ssl_verification(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            mock_session_cls.return_value = session
            HttpRequest("https://api.example.com", verify_ssl=False)
            assert session.verify is False

    def test_bearer_auth(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            session.headers = MagicMock()
            mock_session_cls.return_value = session
            HttpRequest(
                "https://api.example.com",
                auth_type="bearer",
                auth_credentials={"token": "my-token"},
            )
            session.headers.update.assert_called_with({"Authorization": "Bearer my-token"})

    def test_basic_auth(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            session.headers = {}
            mock_session_cls.return_value = session
            HttpRequest(
                "https://api.example.com",
                auth_type="basic",
                auth_credentials={"username": "user", "password": "pass"},
            )
            assert session.auth is not None

    def test_api_key_auth(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            session.headers = MagicMock()
            mock_session_cls.return_value = session
            HttpRequest(
                "https://api.example.com",
                auth_type="api_key",
                auth_credentials={"api_key": "key123", "header_name": "X-API-Key"},
            )
            session.headers.update.assert_called_with({"X-API-Key": "key123"})

    def test_no_auth(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            session.headers = {}
            mock_session_cls.return_value = session
            client = HttpRequest("https://api.example.com")
            assert client is not None


# ---------------------------------------------------------------------------
#  URL 构建测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestBuildUrl:
    """URL 拼接与绝对地址透传。"""

    def test_relative_path(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com/v1/")
            url = client._build_url("/users")
            assert url == "https://api.example.com/v1/users"

    def test_relative_path_with_base_path(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com/")
            url = client._build_url("/users/123")
            assert url == "https://api.example.com/users/123"

    def test_absolute_url_passthrough(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            url = client._build_url("https://other.com/endpoint")
            assert url == "https://other.com/endpoint"

    def test_http_url_passthrough(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            url = client._build_url("http://insecure.com/path")
            assert url == "http://insecure.com/path"


# ---------------------------------------------------------------------------
#  HTTP 方法测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestMethods:
    """五个 HTTP 方法传给 `session.request` 的参数。"""

    @pytest.fixture()
    def client(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            response = MagicMock()
            response.status_code = 200
            response.elapsed.total_seconds.return_value = 0.1
            response.url = "https://api.example.com/test"
            response.headers = {"Content-Type": "application/json"}
            response.raise_for_status = MagicMock()
            session.request.return_value = response
            mock_session_cls.return_value = session

            client = HttpRequest("https://api.example.com")
            client._response = response
            yield client, session

    def test_get(self, client):
        http_client, session = client
        http_client.get("/test")
        session.request.assert_called_once()
        call_kwargs = session.request.call_args
        assert call_kwargs[1]["method"] == "GET"

    def test_post(self, client):
        http_client, session = client
        http_client.post("/test", json={"key": "value"})
        session.request.assert_called_once()
        call_kwargs = session.request.call_args
        assert call_kwargs[1]["method"] == "POST"

    def test_put(self, client):
        http_client, session = client
        http_client.put("/test", json={"key": "value"})
        session.request.assert_called_once()
        call_kwargs = session.request.call_args
        assert call_kwargs[1]["method"] == "PUT"

    def test_delete(self, client):
        http_client, session = client
        http_client.delete("/test")
        session.request.assert_called_once()
        call_kwargs = session.request.call_args
        assert call_kwargs[1]["method"] == "DELETE"

    def test_patch(self, client):
        http_client, session = client
        http_client.patch("/test", json={"key": "value"})
        session.request.assert_called_once()
        call_kwargs = session.request.call_args
        assert call_kwargs[1]["method"] == "PATCH"


# ---------------------------------------------------------------------------
#  重试机制测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestRetry:
    """重试开关、重试次数与重试后成功。"""

    def _create_client(self, session):
        """构造直接使用给定 session 的客户端。"""
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session", return_value=session):
            return HttpRequest("https://api.example.com")

    def test_connection_error_retries(self):
        session = MagicMock()
        session.verify = True
        session.headers = {}
        session.request.side_effect = RequestsConnectionError("refused")

        client = self._create_client(session)

        with pytest.raises(RequestsConnectionError):
            client.get("/test", enable_retry=True, max_retries=2, retry_interval=0)

        assert session.request.call_count == 3

    def test_timeout_retries(self):
        session = MagicMock()
        session.verify = True
        session.headers = {}
        session.request.side_effect = Timeout("timed out")

        client = self._create_client(session)

        with pytest.raises(Timeout):
            client.get("/test", enable_retry=True, max_retries=1, retry_interval=0)

        assert session.request.call_count == 2

    def test_retry_disabled(self):
        session = MagicMock()
        session.verify = True
        session.headers = {}
        session.request.side_effect = RequestsConnectionError("refused")

        client = self._create_client(session)

        with pytest.raises(RequestsConnectionError):
            client.get("/test", enable_retry=False)

        assert session.request.call_count == 1

    def test_successful_after_retry(self):
        session = MagicMock()
        session.verify = True
        session.headers = {}
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.elapsed.total_seconds.return_value = 0.1
        success_response.url = "https://api.example.com/test"
        success_response.headers = {"Content-Type": "application/json"}
        success_response.raise_for_status = MagicMock()

        session.request.side_effect = [RequestsConnectionError("fail"), success_response]

        client = self._create_client(session)
        result = client.get("/test", enable_retry=True, max_retries=2, retry_interval=0)
        assert result.status_code == 200


# ---------------------------------------------------------------------------
#  extract_and_cache & _extract_by_path 测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestExtract:
    """响应提取与缓存写入。"""

    def _create_client_with_cache(self):
        """构造使用空 mock session 的客户端。"""
        from src.utils.http.request import HttpRequest

        session = MagicMock()
        session.verify = True
        session.headers = {}

        with patch("src.utils.http.request.requests.Session", return_value=session):
            client = HttpRequest("https://api.example.com")
            return client

    def test_extract_full_response(self, _mock_dependencies):
        client = self._create_client_with_cache()
        response = MagicMock()
        response.json.return_value = {"data": {"id": 123}}

        result = client.extract_and_cache(response, "full_resp")
        assert result == {"data": {"id": 123}}
        _mock_dependencies["cache"].set.assert_called_with("full_resp", {"data": {"id": 123}})

    def test_extract_by_json_path(self, _mock_dependencies):
        client = self._create_client_with_cache()
        response = MagicMock()
        response.json.return_value = {"data": {"user": {"id": 42}}}

        result = client.extract_and_cache(response, "user_id", "data.user.id")
        assert result == 42
        _mock_dependencies["cache"].set.assert_called_with("user_id", 42)

    def test_extract_nonexistent_path_caches_none(self, _mock_dependencies):
        client = self._create_client_with_cache()
        response = MagicMock()
        response.json.return_value = {"data": {}}

        result = client.extract_and_cache(response, "missing", "data.nonexist.field")
        assert result is None
        _mock_dependencies["cache"].set.assert_called_with("missing", None)

    def test_extract_non_json_raises(self):
        client = self._create_client_with_cache()
        response = MagicMock()
        response.json.side_effect = ValueError("No JSON")

        with pytest.raises(ValueError, match="not valid JSON"):
            client.extract_and_cache(response, "key")

    def test_extract_by_path_nested_dict(self):
        client = self._create_client_with_cache()
        data = {"level1": {"level2": {"value": "found"}}}
        result = client._extract_by_path(data, "level1.level2.value")
        assert result == "found"

    def test_extract_by_path_list_index(self):
        client = self._create_client_with_cache()
        data = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        result = client._extract_by_path(data, "items.1.id")
        assert result == 2

    def test_extract_by_path_invalid_key(self):
        client = self._create_client_with_cache()
        data = {"a": {"b": 1}}
        result = client._extract_by_path(data, "a.c.d")
        assert result is None

    def test_extract_by_path_empty_path(self):
        client = self._create_client_with_cache()
        data = {"key": "val"}
        result = client._extract_by_path(data, "")
        assert result == data

    def test_extract_by_path_type_mismatch(self):
        client = self._create_client_with_cache()
        data = {"key": "string_value"}
        result = client._extract_by_path(data, "key.sub")
        assert result is None


# ---------------------------------------------------------------------------
#  validate_status_code 测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestValidateStatus:
    """状态码校验支持单值与列表。"""

    def _create_client(self):
        """构造替换了 Session 的客户端。"""
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            return HttpRequest("https://api.example.com")

    def test_single_status_match(self):
        client = self._create_client()
        response = MagicMock()
        response.status_code = 200
        assert client.validate_status_code(response, 200) is True

    def test_single_status_no_match(self):
        client = self._create_client()
        response = MagicMock()
        response.status_code = 404
        assert client.validate_status_code(response, 200) is False

    def test_list_status_match(self):
        client = self._create_client()
        response = MagicMock()
        response.status_code = 201
        assert client.validate_status_code(response, [200, 201, 204]) is True

    def test_list_status_no_match(self):
        client = self._create_client()
        response = MagicMock()
        response.status_code = 500
        assert client.validate_status_code(response, [200, 201]) is False


# ---------------------------------------------------------------------------
#  get_cached_value 测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestCache:
    """缓存读取与默认值。"""

    def test_get_cached_value(self, _mock_dependencies):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            _mock_dependencies["cache"].get.return_value = "cached_val"

            result = client.get_cached_value("my_key")
            assert result == "cached_val"
            _mock_dependencies["cache"].get.assert_called_with("my_key", None)

    def test_get_cached_value_with_default(self, _mock_dependencies):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            _mock_dependencies["cache"].get.return_value = "default_val"

            result = client.get_cached_value("missing_key", "default_val")
            assert result == "default_val"
            _mock_dependencies["cache"].get.assert_called_with("missing_key", "default_val")


# ---------------------------------------------------------------------------
#  上下文管理器测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpRequestContextManager:
    """上下文管理器与 `close` 的会话释放。"""

    def test_context_manager_enter(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session"):
            client = HttpRequest("https://api.example.com")
            with client as ctx:
                assert ctx is client

    def test_context_manager_closes_session(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            mock_session_cls.return_value = session

            with HttpRequest("https://api.example.com"):
                pass

            session.close.assert_called_once()

    def test_close_method(self):
        from src.utils.http.request import HttpRequest

        with patch("src.utils.http.request.requests.Session") as mock_session_cls:
            session = MagicMock()
            mock_session_cls.return_value = session

            client = HttpRequest("https://api.example.com")
            client.close()
            session.close.assert_called_once()


# ---------------------------------------------------------------------------
#  请求头编码测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHeaderEncoding:
    """requests 只用 latin-1 编码请求头，非 ASCII 值必须先转成 UTF-8 字节。"""

    def test_ascii_value_untouched(self):
        from src.utils.http.request import _encode_header_for_wire

        assert _encode_header_for_wire("Bearer abc") == "Bearer abc"

    def test_non_ascii_value_becomes_utf8_bytes(self):
        from src.utils.http.request import _encode_header_for_wire

        encoded = _encode_header_for_wire("中文")

        assert encoded.encode("latin-1") == "中文".encode("utf-8")

    def test_sanitize_keeps_all_headers(self):
        from src.utils.http.request import _sanitize_headers

        result = _sanitize_headers({"X-Test": "中文", "Accept": "application/json"})

        assert result["Accept"] == "application/json"
        assert result["X-Test"].encode("latin-1") == "中文".encode("utf-8")

    def test_sanitize_rejects_non_ascii_name(self):
        from src.utils.http.request import _sanitize_headers

        with pytest.raises(ValueError, match="ASCII"):
            _sanitize_headers({"测试": "x"})

