"""线程安全的进程内键值缓存，用于测试执行期间共享临时数据。

单例实例全局唯一；``create_scoped`` 按 run_id 隔离命名空间，避免并发 run 互相污染。
"""

import threading
from typing import Any, Optional


class CacheManager:
    """线程安全的数据缓存。

    单例由 ``get_instance`` 以双重检查锁创建；``create_scoped`` 返回独立实例，
    两者数据互不可见。所有读写都在实例锁内完成。
    """

    _instance: Optional["CacheManager"] = None
    _lock = threading.Lock()
    _initialized = False

    def __init__(self, namespace: str = "") -> None:
        """初始化实例的存储容器与锁。

        Args:
            namespace: 命名空间标识，用于区分不同 run 的缓存
        """
        if not CacheManager._initialized and namespace == "":
            self._data: dict[str, Any] = {}
            self._data_lock = threading.Lock()
            CacheManager._initialized = True
        elif namespace != "":
            self._data = {}
            self._data_lock = threading.Lock()
        self._namespace = namespace

    @classmethod
    def get_instance(cls) -> "CacheManager":
        """返回全局单例，首次调用时以双重检查锁创建。

        Returns:
            全局唯一的缓存实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.__new__(cls)
                    type(cls._instance).__init__(cls._instance)

        return cls._instance

    @classmethod
    def create_scoped(cls, namespace: str) -> "CacheManager":
        """创建一个带独立命名空间与存储的缓存实例。

        Args:
            namespace: 命名空间标识，建议传 run_id

        Returns:
            独立缓存实例，与单例实例不共享数据
        """
        instance = cls.__new__(cls)
        instance._data = {}
        instance._data_lock = threading.Lock()
        instance._namespace = namespace
        return instance

    def set(self, key: str, value: Any) -> None:
        """写入键值对，键已存在时覆盖。

        Args:
            key: 缓存键
            value: 任意对象，不做序列化或拷贝
        """
        with self._data_lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """读取缓存值。

        Args:
            key: 缓存键
            default: 键不存在时的返回值

        Returns:
            缓存值；键不存在时返回 default
        """
        with self._data_lock:
            return self._data.get(key, default)

    def has(self, key: str) -> bool:
        """判断键是否存在于本命名空间。

        Args:
            key: 缓存键

        Returns:
            存在为 True，否则为 False
        """
        with self._data_lock:
            return key in self._data

    def clear(self) -> None:
        """清空本实例的全部缓存数据。"""
        with self._data_lock:
            self._data.clear()

    def get_all_keys(self) -> list[str]:
        """返回当前所有缓存键的快照。

        Returns:
            键名列表，顺序与写入顺序一致
        """
        with self._data_lock:
            return list(self._data.keys())

    def size(self) -> int:
        """返回缓存中的键值对数量。

        Returns:
            键值对个数
        """
        with self._data_lock:
            return len(self._data)

    @classmethod
    def reset_instance(cls) -> None:
        """销毁单例实例，仅供测试使用。

        副作用：清空单例数据并重置初始化标记。
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None
                cls._initialized = False


def get_cache() -> CacheManager:
    """返回全局缓存单例。

    Returns:
        全局唯一的缓存实例
    """
    return CacheManager.get_instance()
