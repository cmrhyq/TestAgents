"""
数据缓存模块

该模块提供线程安全的单例数据缓存，用于在测试执行期间存储和共享数据。
使用单例模式确保全局唯一实例，使用线程锁确保并发安全。
"""

import threading
from typing import Any, Optional


class CacheManager:
    """
    线程安全的数据缓存类

    提供以下功能：
    - 单例模式：确保全局只有一个缓存实例
    - 线程安全：使用锁机制保护并发访问
    - 基本操作：set, get, clear, has 方法
    - 命名空间隔离：支持 run_id 级别的数据隔离，防止并发 workflow 互污染

    使用示例：
        cache = DataCache.get_instance()
        cache.set("user_id", 12345)
        user_id = cache.get("user_id")
        cache.clear()

        # 按 run_id 隔离数据
        scoped = DataCache.create_scoped("run_123")
        scoped.set("token", "abc")
        scoped.clear()  # 只清除该命名空间
    """

    _instance: Optional["CacheManager"] = None
    _lock = threading.Lock()
    _initialized = False

    def __init__(self, namespace: str = "") -> None:
        """
        构造函数

        Args:
            namespace: 命名空间前缀，用于隔离不同 run 的缓存数据
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
        """
        获取 DataCache 的单例实例

        使用双重检查锁定模式确保线程安全的单例创建

        Returns:
            CacheManager: 全局唯一的缓存实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.__new__(cls)
                    type(cls._instance).__init__(cls._instance)

        return cls._instance

    @classmethod
    def create_scoped(cls, namespace: str) -> "CacheManager":
        """
        创建一个带命名空间的独立缓存实例，用于隔离并发 workflow 数据。

        每个 namespace 对应一个独立的缓存空间，互不影响。

        Args:
            namespace: 命名空间标识（建议使用 run_id）

        Returns:
            CacheManager: 带命名空间的缓存实例
        """
        instance = cls.__new__(cls)
        instance._data = {}
        instance._data_lock = threading.Lock()
        instance._namespace = namespace
        return instance

    def set(self, key: str, value: Any) -> None:
        """
        在缓存中存储键值对

        如果键已存在，则更新为新值

        Args:
            key: 缓存键
            value: 要存储的值，可以是任意类型
        """
        with self._data_lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        从缓存中获取值

        Args:
            key: 缓存键
            default: 如果键不存在时返回的默认值

        Returns:
            Any: 存储的值，如果键不存在则返回 default
        """
        with self._data_lock:
            return self._data.get(key, default)

    def has(self, key: str) -> bool:
        """
        检查缓存中是否存在指定的键

        Args:
            key: 要检查的缓存键

        Returns:
            bool: 如果键存在返回 True，否则返回 False
        """
        with self._data_lock:
            return key in self._data

    def clear(self) -> None:
        """
        清空缓存中的所有数据

        用于测试会话结束时清理数据，防止数据泄漏（Requirements 3.5）
        """
        with self._data_lock:
            self._data.clear()

    def get_all_keys(self) -> list[str]:
        """
        获取缓存中所有的键

        Returns:
            list[str]: 所有缓存键的列表
        """
        with self._data_lock:
            return list(self._data.keys())

    def size(self) -> int:
        """
        获取缓存中存储的键值对数量

        Returns:
            int: 缓存中的空间数量
        """
        with self._data_lock:
            return len(self._data)

    @classmethod
    def reset_instance(cls) -> None:
        """
        重置单例实例（主要用于测试）

        警告：此方法会清除单例实例，仅应在测试环境中使用
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None
                cls._initialized = False


# 便捷函数：获取缓存实例
def get_cache() -> CacheManager:
    """
    获取数据缓存实例的便捷函数

    Returns:
        CacheManager: 全局唯一的缓存实例
    """
    return CacheManager.get_instance()
