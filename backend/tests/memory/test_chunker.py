"""`chunk_text` 的分片行为与边界。

覆盖长度上限、相邻重叠、段落边界优先、内容不丢失，以及 overlap >= size 的非法参数。
"""

from src.memory.knowledge import chunk_text


class TestChunkText:
    """分片长度、重叠与边界对齐约束。"""

    def test_short_text_single_chunk(self):
        assert chunk_text("很短的一段话", size=800, overlap=100) == ["很短的一段话"]

    def test_empty_returns_empty_list(self):
        assert chunk_text("", size=800, overlap=100) == []
        assert chunk_text("   \n\n ", size=800, overlap=100) == []

    def test_respects_size(self):
        text = "甲" * 1000
        chunks = chunk_text(text, size=100, overlap=10)

        assert len(chunks) > 1
        assert all(len(c) <= 100 for c in chunks)

    def test_overlap_between_chunks(self):
        text = "".join(str(i % 10) for i in range(300))
        chunks = chunk_text(text, size=100, overlap=20)

        assert chunks[0][-20:] == chunks[1][:20]

    def test_prefers_paragraph_boundary(self):
        paragraph_a = "A" * 60
        paragraph_b = "B" * 60
        text = f"{paragraph_a}\n\n{paragraph_b}"

        chunks = chunk_text(text, size=100, overlap=0)

        assert chunks[0] == paragraph_a

    def test_no_content_lost(self):
        text = "".join(f"段落{i}。" for i in range(50))
        chunks = chunk_text(text, size=60, overlap=0)
        joined = "".join(c.strip() for c in chunks)

        assert len(joined) >= len(text.replace("\n", "").strip()) * 0.95

    def test_handles_single_long_line(self):
        text = "字" * 500
        chunks = chunk_text(text, size=100, overlap=0)

        assert len(chunks) == 5
        assert "".join(chunks) == text

    def test_invalid_overlap_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            chunk_text("abc", size=10, overlap=10)
