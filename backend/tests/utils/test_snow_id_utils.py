"""SnowflakeIdGenerator 单元测试。

覆盖：初始化验证、唯一性、单调递增、位结构、
      并发安全、时钟回拨、序列溢出、next_id 便捷函数。
"""

import threading
from unittest.mock import patch

import pytest

from src.utils.id.snow_id_utils import SnowflakeIdGenerator, next_id

# ---------------------------------------------------------------------------
#  初始化验证
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSnowflakeIdGeneratorInit:
    """初始化参数验证测试。"""

    def test_valid_params(self):
        gen = SnowflakeIdGenerator(datacenter_id=0, worker_id=0)
        assert gen.datacenter_id == 0
        assert gen.worker_id == 0

    def test_max_valid_params(self):
        gen = SnowflakeIdGenerator(datacenter_id=31, worker_id=31)
        assert gen.datacenter_id == 31
        assert gen.worker_id == 31

    def test_worker_id_too_large_raises(self):
        with pytest.raises(ValueError, match="Worker ID"):
            SnowflakeIdGenerator(datacenter_id=0, worker_id=32)

    def test_worker_id_negative_raises(self):
        with pytest.raises(ValueError, match="Worker ID"):
            SnowflakeIdGenerator(datacenter_id=0, worker_id=-1)

    def test_datacenter_id_too_large_raises(self):
        with pytest.raises(ValueError, match="Datacenter ID"):
            SnowflakeIdGenerator(datacenter_id=32, worker_id=0)

    def test_datacenter_id_negative_raises(self):
        with pytest.raises(ValueError, match="Datacenter ID"):
            SnowflakeIdGenerator(datacenter_id=-1, worker_id=0)

    def test_custom_epoch(self):
        custom_epoch = 1000000000000
        gen = SnowflakeIdGenerator(epoch=custom_epoch)
        assert gen.epoch == custom_epoch


# ---------------------------------------------------------------------------
#  ID 生成基本功能
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSnowflakeIdGeneration:
    """ID 生成功能测试。"""

    def test_generates_positive_integer(self):
        gen = SnowflakeIdGenerator()
        id_val = gen.generate_id()
        assert isinstance(id_val, int)
        assert id_val > 0

    def test_uniqueness(self):
        gen = SnowflakeIdGenerator()
        ids = {gen.generate_id() for _ in range(1000)}
        assert len(ids) == 1000

    def test_monotonically_increasing(self):
        gen = SnowflakeIdGenerator()
        prev = 0
        for _ in range(100):
            current = gen.generate_id()
            assert current > prev
            prev = current

    def test_bit_structure_contains_datacenter_id(self):
        gen = SnowflakeIdGenerator(datacenter_id=15, worker_id=7)
        id_val = gen.generate_id()

        extracted_datacenter = (
            id_val >> SnowflakeIdGenerator.DATACENTER_ID_SHIFT
        ) & SnowflakeIdGenerator.MAX_DATACENTER_ID
        extracted_worker = (id_val >> SnowflakeIdGenerator.WORKER_ID_SHIFT) & SnowflakeIdGenerator.MAX_WORKER_ID

        assert extracted_datacenter == 15
        assert extracted_worker == 7

    def test_different_workers_produce_different_ids(self):
        gen1 = SnowflakeIdGenerator(datacenter_id=0, worker_id=1)
        gen2 = SnowflakeIdGenerator(datacenter_id=0, worker_id=2)
        id1 = gen1.generate_id()
        id2 = gen2.generate_id()
        assert id1 != id2

    def test_id_fits_in_64_bits(self):
        gen = SnowflakeIdGenerator()
        for _ in range(100):
            id_val = gen.generate_id()
            assert id_val.bit_length() <= 63


# ---------------------------------------------------------------------------
#  并发安全测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSnowflakeIdConcurrency:
    """并发安全测试。"""

    def test_thread_safety(self):
        gen = SnowflakeIdGenerator()
        results = []
        lock = threading.Lock()

        def generate_ids(count):
            local_ids = []
            for _ in range(count):
                local_ids.append(gen.generate_id())
            with lock:
                results.extend(local_ids)

        threads = [threading.Thread(target=generate_ids, args=(200,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 1000
        assert len(set(results)) == 1000


# ---------------------------------------------------------------------------
#  时钟回拨测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSnowflakeIdClockDrift:
    """时钟回拨测试。"""

    def test_clock_backward_raises_runtime_error(self):
        gen = SnowflakeIdGenerator()
        gen._last_timestamp = 1000000

        with (
            patch.object(gen, "_current_millis", return_value=999990),
            pytest.raises(RuntimeError, match="时钟回拨"),
        ):
            gen.generate_id()


# ---------------------------------------------------------------------------
#  序列溢出测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSnowflakeIdSequenceOverflow:
    """同一毫秒内序列号溢出测试。"""

    def test_sequence_overflow_waits_next_millis(self):
        gen = SnowflakeIdGenerator(datacenter_id=0, worker_id=0, epoch=0)

        base_time = 1000000
        gen._last_timestamp = base_time
        gen._sequence = SnowflakeIdGenerator.MAX_SEQUENCE

        call_count = [0]

        def mock_millis():
            call_count[0] += 1
            if call_count[0] <= 1:
                return base_time
            return base_time + 1

        with patch.object(gen, "_current_millis", side_effect=mock_millis):
            id_val = gen.generate_id()

        assert id_val > 0
        assert gen._last_timestamp == base_time + 1
        assert gen._sequence == 0


# ---------------------------------------------------------------------------
#  next_id 便捷函数测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNextIdFunction:
    """next_id 全局函数测试。"""

    def test_returns_positive_integer(self):
        id_val = next_id()
        assert isinstance(id_val, int)
        assert id_val > 0

    def test_uniqueness(self):
        ids = {next_id() for _ in range(100)}
        assert len(ids) == 100

    def test_respects_env_config(self):
        with patch.dict("os.environ", {"SNOWFLAKE_DATACENTER_ID": "5", "SNOWFLAKE_WORKER_ID": "10"}):
            import importlib

            import src.utils.id.snow_id_utils as module

            importlib.reload(module)
            try:
                id_val = module.next_id()
                assert id_val > 0

                extracted_dc = (
                    id_val >> SnowflakeIdGenerator.DATACENTER_ID_SHIFT
                ) & SnowflakeIdGenerator.MAX_DATACENTER_ID
                extracted_wk = (id_val >> SnowflakeIdGenerator.WORKER_ID_SHIFT) & SnowflakeIdGenerator.MAX_WORKER_ID
                assert extracted_dc == 5
                assert extracted_wk == 10
            finally:
                importlib.reload(module)
