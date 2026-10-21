import os
import threading
import time


class SnowflakeIdGenerator:
    """
    雪花ID生成器

    位数分配:
    - 1位符号位，始终为0
    - 41位时间戳（毫秒级）
    - 10位工作机器ID（5位数据中心ID + 5位机器ID）
    - 12位序列号（同一毫秒内的计数器）
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
        """
        初始化雪花ID生成器

        Args:
            datacenter_id: 数据中心ID (0-31)
            worker_id: 工作机器ID (0-31)
            epoch: 起始时间戳（毫秒），默认 2025-01-01 00:00:00 UTC
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
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def generate_id(self) -> int:
        """
        生成下一个雪花 ID

        Returns:
            64 位整数雪花 ID

        Raises:
            RuntimeError: 检测到时钟回拨时抛出
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
    """生成下一个雪花 ID（使用全局默认生成器）"""
    return _default_generator.generate_id()
