"""v4 迁移：测试报告改为按 ``run_id`` 聚合 ``send_request``，删除 ``report`` 表。

背景：报告原本是一条条 ``report`` 行 + 磁盘文件，但写文件的代码路径早已不存在
（``ReportService.create_report`` 零调用方），表里也是空的。改造后报告实时聚合
``agent_tool_call``，不再需要这张表，也不再产出文件。

注意事项：

1. **必须在 v3 之后执行**：v3 在历史库上会「重建 report 表」（SQLite 不能改外键），
   如果 v4 排在前面，v3 又会把它建回来。
2. **新库是空操作**：ORM 模型已删除，``create_all`` 不会再建 report；
   ``DROP TABLE IF EXISTS`` 直接跳过。
3. **删表前先记行数**：即使当前实测为 0 行，也要在日志里留下证据，
   避免「哪天有人手工写过数据被静默删掉」。
4. **补索引**：``(tool_name, run_id)`` 专供报告聚合。
   ``create_all`` 不会 ALTER 已存在的表，老库只能靠这里补。
"""

from __future__ import annotations

from sqlalchemy import Engine, text

from src.core.logging import get_logger

logger = get_logger(__name__)


def migrate_v4(engine: Engine) -> None:
    """删除 report 表并补齐报告聚合所需索引（幂等）。"""
    with engine.begin() as conn:
        dropped_rows = 0
        has_report = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='report'")
        ).scalar()
        if has_report:
            dropped_rows = int(conn.execute(text("SELECT COUNT(*) FROM report")).scalar() or 0)
            conn.execute(text("DROP TABLE report"))

        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_atc_tool_run ON agent_tool_call(tool_name, run_id)")
        )

    if has_report:
        logger.warning(
            "v4 迁移：report 表已删除（报告改为按 run 聚合 send_request）",
            action="migrate_v4",
            dropped_rows=dropped_rows,
        )
    else:
        logger.info("v4 迁移：report 表不存在，跳过删除", action="migrate_v4")
