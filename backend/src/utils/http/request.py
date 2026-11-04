"""HTTP 请求封装。

基于 requests 会话复用连接，统一超时、可选认证、指数退避重试与响应字段缓存。
"""

import random
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from src.core.cache.cache_manager import CacheManager
from src.core.logging import get_logger

logger = get_logger(__name__)


def split_url(url: str) -> tuple[str, str]:
    """拆分 URL 为 ``(base_url, endpoint)``。

    endpoint 保留 path、query 与 fragment。

    Args:
        url: 完整 URL

    Returns:
        base_url 为 ``scheme://host``，endpoint 为其余部分

    Raises:
        ValueError: 缺少 scheme 或 host
    """
    p = urlparse(url.strip())
    if not p.scheme or not p.netloc:
        raise ValueError(f"无效的 URL: {url}")

    base_url = f"{p.scheme}://{p.netloc}"
    endpoint = p.path or "/"
    if p.query:
        endpoint += f"?{p.query}"
    if p.fragment:
        endpoint += f"#{p.fragment}"
    return base_url, endpoint


def get_random_pc_ua():
    """随机生成一个常见桌面浏览器的 User-Agent。

    Returns:
        User-Agent 字符串
    """
    browsers = {
        "Chrome": {
            "versions": [
                f"{random.randint(90, 120)}.0.{random.randint(1000, 9999)}.{random.randint(10, 999)}" for _ in range(5)
            ],
            "template": "Mozilla/5.0 (Windows NT {windows_ver}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36",
        },
        "Firefox": {
            "versions": [f"{random.randint(90, 110)}.0" for _ in range(5)],
            "template": "Mozilla/5.0 (Windows NT {windows_ver}; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}",
        },
        "Edge": {
            "versions": [
                f"{random.randint(90, 120)}.0.{random.randint(100, 999)}.{random.randint(10, 99)}" for _ in range(5)
            ],
            "template": "Mozilla/5.0 (Windows NT {windows_ver}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36 Edg/{version}",
        },
        "Safari": {
            "versions": [f"{random.randint(10, 16)}.{random.randint(0, 3)}" for _ in range(5)],
            "template": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{mac_ver}_{mac_rev}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{version} Safari/605.1.15",
        },
        "Opera": {
            "versions": [
                f"{random.randint(70, 100)}.0.{random.randint(1000, 9999)}.{random.randint(10, 999)}" for _ in range(5)
            ],
            "template": "Mozilla/5.0 (Windows NT {windows_ver}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36 OPR/{version}",
        },
    }

    windows_versions = ["10.0", "11.0", "6.3", "6.2", "6.1"]
    windows_ver = random.choice(windows_versions)

    mac_ver = random.randint(10, 15)
    mac_rev = random.randint(0, 9)

    browser_name = random.choice(list(browsers.keys()))
    browser_data = browsers[browser_name]

    version = random.choice(browser_data["versions"])

    # 部分浏览器模板同时需要 Chrome 与 OPR 版本号
    chrome_ver = f"{random.randint(80, 120)}.0.{random.randint(1000, 9999)}.{random.randint(10, 999)}"

    template = browser_data["template"]
    if browser_name == "Safari":
        user_agent = template.format(mac_ver=mac_ver, mac_rev=mac_rev, version=version)
    elif browser_name == "Opera":
        user_agent = template.format(windows_ver=windows_ver, chrome_ver=chrome_ver, version=version)
    else:
        user_agent = template.format(windows_ver=windows_ver, version=version)

    return user_agent


def _encode_header_for_wire(value: Any) -> str:
    """把请求头值转成 requests 可编码的形式。

    requests/urllib3 只用 latin-1 编码请求头，非 ASCII 值会抛 ``UnicodeEncodeError``。
    这里先按 UTF-8 编为字节再以 latin-1 解码回字符串，使原始字节原样发出。

    Args:
        value: 原始头值，任意类型按 ``str`` 处理

    Returns:
        可直接交给 requests 的头值
    """
    text = str(value)
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-8").decode("latin-1")


def _sanitize_headers(headers: dict[str, Any]) -> dict[str, str]:
    """校验头名并编码头值。

    头名必须是 ASCII（RFC 9110 的 token 规则），非 ASCII 内容应放入 body 或查询参数。

    Args:
        headers: 原始请求头

    Returns:
        可直接交给 requests 的请求头

    Raises:
        ValueError: 头名含非 ASCII 字符
    """
    result: dict[str, str] = {}
    for name, value in headers.items():
        header_name = str(name)
        if not header_name.isascii():
            raise ValueError(f"请求头名称必须是 ASCII，收到: {header_name}（非 ASCII 内容请放到 body 或 URL 参数里）")
        result[header_name] = _encode_header_for_wire(value)
    return result


class HttpRequest:
    """HTTP 请求客户端。

    持有单个 ``requests.Session`` 复用连接，创建后超时、SSL 校验与认证方式固定不变。
    实例可作为上下文管理器使用，退出时关闭会话。
    """

    def __init__(
        self,
        base_url: str,
        connect_timeout: int = 30,
        read_timeout: int = 10,
        verify_ssl: bool = True,
        auth_type: str | None = None,
        auth_credentials: dict[str, str] | None = None,
    ):
        """初始化客户端。

        副作用：创建会话，并按 ``auth_type`` 写入会话级认证头。

        Args:
            base_url: API 基础 URL
            connect_timeout: 连接超时秒数
            read_timeout: 读取超时秒数
            verify_ssl: 是否校验 SSL 证书
            auth_type: 认证类型，取值 ``bearer`` / ``basic`` / ``api_key``
            auth_credentials: 认证凭证，字段随 ``auth_type`` 而定
        """
        self.base_url = base_url
        self.cache = CacheManager.get_instance()

        # 复用连接，避免每次请求重复 TLS 握手
        self.session = requests.Session()

        self.timeout = (connect_timeout, read_timeout)

        self.session.verify = verify_ssl

        self._setup_authentication(auth_type, auth_credentials)

        logger.info(f"HTTP客户端初始化，base_url: {self.base_url}", base_url=self.base_url)

    def _setup_authentication(self, auth_type: str | None, auth_credentials: dict[str, str] | None) -> None:
        """按认证类型配置会话。

        凭证缺失时静默跳过，不抛错。

        副作用：写入 ``session.headers`` 或 ``session.auth``。

        Args:
            auth_type: 认证类型
            auth_credentials: 认证凭证
        """
        if not auth_type or not auth_credentials:
            return

        if auth_type == "bearer":
            token = auth_credentials.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                logger.info("Bearer Token认证已配置", auth_type="bearer")

        elif auth_type == "basic":
            username = auth_credentials.get("username")
            password = auth_credentials.get("password")

            if username and password:
                self.session.auth = HTTPBasicAuth(username, password)
                logger.info(f"Basic认证已配置，用户: {username}", auth_type="basic", username=username)

        elif auth_type == "api_key":
            api_key = auth_credentials.get("api_key")
            header_name = auth_credentials.get("header_name", "X-API-Key")

            if api_key:
                self.session.headers.update({header_name: api_key})
                logger.info(f"API Key认证已配置，header: {header_name}", auth_type="api_key", header_name=header_name)

    def _build_url(self, endpoint: str) -> str:
        """拼出完整 URL，已是绝对地址时原样返回。

        Args:
            endpoint: 端点路径或完整 URL

        Returns:
            完整 URL
        """
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return urljoin(self.base_url, endpoint.lstrip("/"))

    def _log_request(self, method: str, url: str, **kwargs) -> None:
        """以 debug 级别记录请求。

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 请求参数，其中 ``data`` 只记录占位符
        """
        log_data: dict[str, Any] = {
            "method": method,
            "url": url,
        }

        # data 可能是表单明文，日志中只留占位符
        if "params" in kwargs:
            log_data["params"] = kwargs["params"]

        if "json" in kwargs:
            log_data["json_body"] = kwargs["json"]

        if "data" in kwargs:
            log_data["data"] = "***" if kwargs["data"] else None

        if "headers" in kwargs:
            log_data["headers"] = kwargs["headers"]

        logger.debug(f"发送请求: {method} {url}", **log_data)

    def _log_response(self, response: requests.Response) -> None:
        """以 debug 级别记录响应状态、耗时与 JSON 响应体。

        Args:
            response: 响应对象
        """
        log_data = {
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "url": response.url,
        }

        try:
            if response.headers.get("Content-Type", "").startswith("application/json"):
                log_data["response_body"] = response.json()
        except Exception:
            log_data["response_body"] = "(non-JSON or empty)"

        logger.debug(
            f"收到响应: {response.status_code} {response.url}，耗时: {response.elapsed.total_seconds():.3f}s",
            **log_data,
        )

    def _make_request_with_retry(
        self, method: str, url: str, enable_retry: bool = True, max_retries: int = 3, retry_interval: int = 1, **kwargs
    ) -> requests.Response:
        """发送请求，失败时按指数退避重试。

        仅连接错误、超时与 5xx 响应会重试，其余异常直接抛出。
        每次尝试都会合并会话头、注入随机 User-Agent 并编码头值。

        副作用：发起网络请求；每次尝试都会写请求与响应日志。

        Args:
            method: HTTP 方法
            url: 完整 URL
            enable_retry: 是否启用重试
            max_retries: 最大重试次数，首次请求不计入
            retry_interval: 首次重试等待秒数，之后每次翻倍
            **kwargs: 透传给 ``Session.request``

        Returns:
            响应对象

        Raises:
            RequestException: 重试耗尽或遇到不可重试的异常
        """
        max_retries = max_retries if enable_retry else 0
        retry_delay = retry_interval

        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if "headers" in kwargs:
                    # 会话头与请求头合并，非 ASCII 值按 UTF-8 字节发送
                    headers = dict(self.session.headers)
                    headers.update(kwargs["headers"] or {})
                    headers["User-Agent"] = get_random_pc_ua()
                    kwargs["headers"] = _sanitize_headers(headers)
                else:
                    headers = dict(self.session.headers)
                    headers["User-Agent"] = get_random_pc_ua()
                    kwargs["headers"] = _sanitize_headers(headers)

                self._log_request(method, url, **kwargs)

                response = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)

                self._log_response(response)

                return response

            except (ConnectionError, Timeout) as e:
                last_exception = e
                logger.warning(
                    f"[http_request] 网络错误，第{attempt + 1}/{max_retries + 1}次尝试: {str(e)}",
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
                    error=str(e),
                )

                if attempt < max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(
                        f"[http_request] 请求重试耗尽，共{max_retries + 1}次尝试: {str(e)}",
                        attempts=max_retries + 1,
                        error=str(e),
                    )

            except HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                logger.error(f"HTTP错误: {status_code} - {str(e)}", status_code=status_code, error=str(e))
                if status_code >= 500 and attempt < max_retries:
                    last_exception = e
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

            except RequestException as e:
                logger.error(f"请求异常: {str(e)}", error=str(e))
                raise

        # 全部重试失败时抛出最后一次异常
        if last_exception:
            raise last_exception
        raise RequestException(f"Request failed after {max_retries + 1} attempts")

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """发送 GET 请求。

        副作用：发起网络请求。

        Args:
            endpoint: 端点路径或完整 URL
            **kwargs: 透传给 ``Session.request``，如 ``params`` / ``headers``

        Returns:
            响应对象
        """
        url = self._build_url(endpoint)
        return self._make_request_with_retry("GET", url, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """发送 POST 请求。

        副作用：发起网络请求。

        Args:
            endpoint: 端点路径或完整 URL
            **kwargs: 透传给 ``Session.request``，如 ``json`` / ``data`` / ``headers``

        Returns:
            响应对象
        """
        url = self._build_url(endpoint)
        return self._make_request_with_retry("POST", url, **kwargs)

    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """发送 PUT 请求。

        副作用：发起网络请求。

        Args:
            endpoint: 端点路径或完整 URL
            **kwargs: 透传给 ``Session.request``

        Returns:
            响应对象
        """
        url = self._build_url(endpoint)
        return self._make_request_with_retry("PUT", url, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """发送 DELETE 请求。

        副作用：发起网络请求。

        Args:
            endpoint: 端点路径或完整 URL
            **kwargs: 透传给 ``Session.request``

        Returns:
            响应对象
        """
        url = self._build_url(endpoint)
        return self._make_request_with_retry("DELETE", url, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        """发送 PATCH 请求。

        副作用：发起网络请求。

        Args:
            endpoint: 端点路径或完整 URL
            **kwargs: 透传给 ``Session.request``

        Returns:
            响应对象
        """
        url = self._build_url(endpoint)
        return self._make_request_with_retry("PATCH", url, **kwargs)

    def extract_and_cache(self, response: requests.Response, cache_key: str, json_path: str | None = None) -> Any:
        """按路径从响应中取值并写入缓存。

        路径未命中时同样写入 None，便于下游区分「已取过但为空」。

        副作用：写入全局 ``CacheManager``。

        Args:
            response: 响应对象，需为 JSON
            cache_key: 缓存键
            json_path: 点号分隔的路径，如 ``data.user.id``；None 时缓存整个响应体

        Returns:
            提取到的值；路径未命中时为 None

        Raises:
            ValueError: 响应体不是合法 JSON
        """
        try:
            response_data = response.json()
        except Exception as e:
            logger.error(f"响应JSON解析失败: {str(e)}", error=str(e))
            raise ValueError(f"Response is not valid JSON: {str(e)}") from e

        # 未指定路径时缓存整个响应体
        if json_path is None:
            self.cache.set(cache_key, response_data)
            logger.info(f"缓存完整响应，key: {cache_key}", cache_key=cache_key)
            return response_data

        extracted_value = self._extract_by_path(response_data, json_path)

        if extracted_value is not None:
            self.cache.set(cache_key, extracted_value)
            logger.info(f"提取并缓存数据: {json_path} -> {cache_key}", json_path=json_path, cache_key=cache_key)
        else:
            logger.warning(
                f"路径未找到，缓存None: path={json_path}, key={cache_key}", json_path=json_path, cache_key=cache_key
            )
            self.cache.set(cache_key, None)

        return extracted_value

    def _extract_by_path(self, data: Any, path: str) -> Any:
        """按点号路径取值，列表段按整数下标解析。

        Args:
            data: 已解析的响应数据
            path: 点号分隔路径；空串时返回原数据

        Returns:
            取到的值；路径不存在或类型不匹配时返回 None
        """
        if not path:
            return data

        keys = path.split(".")
        current = data

        for key in keys:
            try:
                if isinstance(current, list):
                    index = int(key)
                    current = current[index]
                elif isinstance(current, dict):
                    current = current[key]
                else:
                    logger.warning(
                        f"路径提取类型不匹配: key={key}, 实际类型={type(current).__name__}",
                        key=key,
                        actual_type=type(current).__name__,
                    )
                    return None
            except (KeyError, IndexError, ValueError, TypeError) as e:
                logger.warning(f"路径提取失败: {path}, 错误: {str(e)}", path=path, error=str(e))
                return None

        return current

    def get_cached_value(self, cache_key: str, default: Any = None) -> Any:
        """读取缓存值。

        Args:
            cache_key: 缓存键
            default: 键不存在时的返回值

        Returns:
            缓存值或 default
        """
        value = self.cache.get(cache_key, default)
        logger.debug(f"获取缓存值: {cache_key}", cache_key=cache_key)
        return value

    def validate_status_code(self, response: requests.Response, expected_status: int | list[int]) -> bool:
        """校验响应状态码是否命中期望值。

        Args:
            response: 响应对象
            expected_status: 期望状态码，单个整数或列表

        Returns:
            命中返回 True，否则返回 False
        """
        if isinstance(expected_status, int):
            expected_status = [expected_status]

        is_valid = response.status_code in expected_status

        if is_valid:
            logger.info(
                f"状态码验证通过: {response.status_code} in {expected_status}",
                actual=response.status_code,
                expected=expected_status,
            )
        else:
            logger.error(
                f"状态码验证失败: {response.status_code} not in {expected_status}",
                actual=response.status_code,
                expected=expected_status,
            )

        return is_valid

    def close(self) -> None:
        """关闭会话，释放连接。

        副作用：之后的请求无法再复用该实例。
        """
        if self.session:
            self.session.close()
            logger.debug("HTTP会话已关闭", base_url=self.base_url)

    def __enter__(self):
        """进入上下文，返回自身。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时关闭会话。"""
        self.close()
