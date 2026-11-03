"""HTTP 请求工具：body 编码与线上实际字节。

断言对准本地 echo 服务收到的原始字节，而不是传给 `requests` 的 kwargs。
字符串 body 曾被 json_repair 兜底压成空串，仅在 requests 层 mock 无法发现此类失真。
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.agent.tools.http_tools import _prepare_body, make_http_tools


class _EchoHandler(BaseHTTPRequestHandler):
    """把收到的原始报文记录到 `received`，响应固定为 JSON。"""

    received: list[dict] = []

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        type(self).received.append(
            {
                "method": self.command,
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "raw": raw,
            }
        )
        payload = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle

    def log_message(self, *args):  # 静音
        pass


@pytest.fixture()
def echo():
    """启动本地 echo 服务，产出 `(base_url, received)`。"""
    _EchoHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", _EchoHandler.received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def send():
    """返回调用 `send_request` 的快捷函数。

    `session_scope` 被替换为抛错函数，用例一旦触库即失败。
    """

    def _no_db():
        raise AssertionError("本用例不应访问数据库")

    tools = {tool.name: tool for tool in make_http_tools(space_id=1, session_scope=_no_db)}
    tool = tools["send_request"]

    def _call(**kwargs):
        return json.loads(tool.invoke(kwargs))

    return _call


def _last(received: list[dict]) -> dict:
    """取最后一条服务端记录，无记录即失败。"""
    assert received, "服务端没有收到请求"
    return received[-1]


# ---------------------------------------------------------------------------
#  body 编码：纯函数层
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrepareBody:
    """`_prepare_body` 的编码分支与错误返回。"""

    def test_keeps_form_string_as_is(self):
        headers: dict = {}
        kwargs, error = _prepare_body("user=a&pwd=b", "auto", headers)

        assert error is None
        assert kwargs["data"] == b"user=a&pwd=b"
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"

    def test_keeps_xml_string_as_is(self):
        headers: dict = {}
        kwargs, error = _prepare_body("<xml><a>1</a></xml>", "auto", headers)

        assert error is None
        assert kwargs["data"] == b"<xml><a>1</a></xml>"
        assert headers["Content-Type"] == "text/plain; charset=utf-8"

    def test_valid_json_goes_through_json_kwarg(self):
        kwargs, error = _prepare_body('{"a": 1}', "auto", {})

        assert error is None
        assert kwargs == {"json": {"a": 1}}

    def test_invalid_json_is_not_repaired(self):
        """非法 JSON 只返回错误，不做静默修复。"""
        kwargs, error = _prepare_body('{"a": 1,}', "auto", {})

        assert kwargs == {}
        assert error is not None and "raw" in error

    def test_invalid_json_with_json_type_returns_error(self):
        kwargs, error = _prepare_body('{"a": 1,}', "json", {})

        assert kwargs == {}
        assert error is not None and "raw" in error

    def test_raw_type_sends_invalid_json_verbatim(self):
        headers: dict = {}
        kwargs, error = _prepare_body('{"a": 1,}', "raw", headers)

        assert error is None
        assert kwargs["data"] == b'{"a": 1,}'
        # 非法 JSON 用例需服务端按 JSON 解析，否则返回 415 而非解析错误
        assert headers["Content-Type"] == "application/json"

    def test_form_type_encodes_json_object(self):
        headers: dict = {}
        kwargs, error = _prepare_body('{"user": "a"}', "form", headers)

        assert error is None
        assert kwargs == {"data": {"user": "a"}}
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"

    def test_respects_existing_content_type(self):
        headers = {"content-type": "application/xml"}
        kwargs, error = _prepare_body("<a>1</a>", "auto", headers)

        assert error is None
        assert kwargs["data"] == b"<a>1</a>"
        assert list(headers) == ["content-type"], "已给的 Content-Type 不应被覆盖"

    def test_non_ascii_body_keeps_utf8_bytes(self):
        kwargs, error = _prepare_body("中文内容", "raw", {})

        assert error is None
        assert kwargs["data"] == "中文内容".encode()

    def test_empty_body_sends_nothing(self):
        for body in ("", "   ", None):
            kwargs, error = _prepare_body(body, "auto", {})
            assert kwargs == {} and error is None

    def test_rejects_unknown_body_type(self):
        kwargs, error = _prepare_body("x", "yaml", {})

        assert kwargs == {}
        assert error is not None and "body_type" in error

    def test_accepts_object_body(self):
        """模型常把 body 直接写成对象，参数校验需接受。"""
        assert _prepare_body({"a": 1}, "auto", {}) == ({"json": {"a": 1}}, None)
        assert _prepare_body([1, 2], "json", {}) == ({"json": [1, 2]}, None)

    def test_object_body_with_raw_is_serialized(self):
        headers: dict = {}
        kwargs, error = _prepare_body({"a": "中"}, "raw", headers)

        assert error is None
        assert kwargs["data"] == '{"a": "中"}'.encode()
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
#  端到端：服务端实际收到的字节
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendRequestBodyOnWire:
    """端到端：服务端实际收到的字节。"""

    def test_form_body_reaches_server(self, echo, send):
        base, received = echo
        send(path=f"{base}/login", method="POST", body="user=a&pwd=b")

        got = _last(received)
        assert got["raw"] == b"user=a&pwd=b"
        assert got["content_type"] == "application/x-www-form-urlencoded"

    def test_xml_body_reaches_server(self, echo, send):
        base, received = echo
        send(path=f"{base}/soap", method="POST", body="<xml><a>1</a></xml>")

        assert _last(received)["raw"] == b"<xml><a>1</a></xml>"

    def test_invalid_json_with_raw_reaches_server(self, echo, send):
        base, received = echo
        send(path=f"{base}/json", method="POST", body='{"a": 1,}', body_type="raw")

        got = _last(received)
        assert got["raw"] == b'{"a": 1,}'
        assert got["content_type"] == "application/json"

    def test_invalid_json_without_raw_is_refused(self, echo, send):
        base, received = echo
        result = send(path=f"{base}/json", method="POST", body='{"a": 1,}')

        assert "error" in result
        assert received == [], "被拒绝的请求不应发出"

    def test_no_body_for_plain_get(self, echo, send):
        base, received = echo
        send(path=f"{base}/items")

        got = _last(received)
        assert got["raw"] == b""
        assert got["content_type"] is None

    def test_delete_can_carry_body(self, echo, send):
        base, received = echo
        send(path=f"{base}/items/1", method="DELETE", body='{"ids": [1]}')

        got = _last(received)
        assert got["method"] == "DELETE"
        assert got["raw"] == b'{"ids": [1]}'

    def test_non_ascii_header_does_not_crash(self, echo, send):
        base, received = echo
        result = send(path=f"{base}/x", method="POST", headers='{"X-Test": "中文"}', body='{"a": 1}')

        assert result.get("status_code") == 200, result
        assert received, "请求应当发出去"

    def test_non_ascii_query_is_percent_encoded(self, echo, send):
        base, received = echo
        send(path=f"{base}/x", params='{"q": "中文"}')

        assert _last(received)["path"] == "/x?q=%E4%B8%AD%E6%96%87"

    def test_non_object_headers_returns_error(self, echo, send):
        base, received = echo
        result = send(path=f"{base}/x", headers="Bearer abc")

        assert "headers" in result["error"]
        assert received == []

    def test_object_headers_and_body_are_accepted(self, echo, send):
        base, received = echo
        result = send(
            path=f"{base}/x",
            method="POST",
            headers={"X-Test": "中"},
            body={"a": 1},
        )

        assert result.get("status_code") == 200, result
        assert _last(received)["raw"] == b'{"a": 1}'
