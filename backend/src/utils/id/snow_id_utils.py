"""雪花 ID 生成器。

进程内按毫秒与序列号生成 64 位整数 ID；时钟回拨时拒绝生成。
"""

import os
import threading
import time


class SnowflakeIdGenerator:
    """雪花 ID 生成器。

    64 位布局：1 位符号位（恒 0）+ 41 位毫秒时间戳 + 5 位数据中心 ID +
    5 位机器 ID + 12 位序列号。
    """

    WORKER_ID_BITS = 5
    DATACENTER_ID_BITS = 5
    SEQUENCE_BITS = 12

    MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1
    MAX_DATACENTER_ID = (1 << DATACENTER_ID_BITS) - 1
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1

    WORKER_ID_SHIFT = SEQUENCE_BITS
    DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS

    def __init__(self, datacenter_id: int = 0, worker_id: int = 0, epoch: int = 1735660800000):
        """初始化生成器。

        Args:
            datacenter_id: 数据中心 ID，取值 0-31
            worker_id: 机器 ID，取值 0-31
            epoch: 起始时间戳（毫秒），默认 2025-01-01 00:00:00 UTC

        Raises:
            ValueError: 数据中心 ID 或机器 ID 越界
        """
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError(f"Worker ID 必须在 0 到 {self.MAX_WORKER_ID} 之间")

        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError(f"Datacenter ID 必须在 0 到 {self.MAX_DATACENTER_ID} 之间")

        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.epoch = epoch

        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()

    def _wait_next_millis(self, last_timestamp: int) -> int:
        """自旋等待，直到当前毫秒大于给定时间戳。"""
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp

    def _current_millis(self) -> int:
        """返回当前毫秒时间戳。"""
        return int(time.time() * 1000)

    def generate_id(self) -> int:
        """生成下一个雪花 ID。

        同一毫秒内序列号用尽时自旋到下一毫秒，全程持锁。

        Returns:
            64 位整数 ID

        Raises:
            RuntimeError: 检测到时钟回拨
        """
        with self._lock:
            current_timestamp = self._current_millis()

            if current_timestamp < self._last_timestamp:
                raise RuntimeError(f"时钟回拨，拒绝生成ID，回拨时间: {self._last_timestamp - current_timestamp} 毫秒")

            if current_timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self.MAX_SEQUENCE
                if self._sequence == 0:
                    current_timestamp = self._wait_next_millis(self._last_timestamp)
            else:
                self._sequence = 0

            self._last_timestamp = current_timestamp

            snowflake_id = (
                ((current_timestamp - self.epoch) << self.TIMESTAMP_SHIFT)
                | (self.datacenter_id << self.DATACENTER_ID_SHIFT)
                | (self.worker_id << self.WORKER_ID_SHIFT)
                | self._sequence
            )

            return snowflake_id


_default_generator = SnowflakeIdGenerator(
    datacenter_id=int(os.environ.get("SNOWFLAKE_DATACENTER_ID", "0")),
    worker_id=int(os.environ.get("SNOWFLAKE_WORKER_ID", "0")),
)


def next_id() -> int:
    """用全局默认生成器生成下一个 ID。

    默认生成器的数据中心与机器 ID 在导入时从环境变量读取。

    Returns:
        64 位整数 ID
    """
    return _default_generator.generate_id()
