"""Skill 业务层：导入、装配、启用开关。

三件事，各有各的坑：

1. **导入 zip**：必须防 zip-slip。``ZipFile.extractall`` 不做任何校验，
   条目名叫 ``../../etc/passwd`` 就会写到目录外。这里逐条校验后自己写盘。
2. **装配**：把选中 skill 的正文拼成 system prompt 片段；单个超长要截断并标注。
3. **工具收窄**：skill 声明的 ``allowed_tools`` 与模式白名单**取交集**，
   skill 只能收窄权限、不能放大——否则一个恶意 skill 就能绕过 Ask 模式的只读约束。
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from src.core.config import get_config
from src.core.logging import get_logger
from src.skill.manifest import SkillManifestError, parse_skill_md
from src.skill.repository import SKILL_FILE, DiscoveredSkill, SkillRepository
from src.workspace.manager import WorkspaceManager

logger = get_logger(__name__)


class SkillImportError(ValueError):
    """skill 包无法导入（非法 zip / 无 SKILL.md / 路径穿越）。"""


class SkillService:
    """Skill 导入与装配。

    Args:
        builtin_root: 内置 skill 根目录；None 时取配置
        workspace: 工作目录管理器；None 时取全局单例
    """

    def __init__(
        self,
        builtin_root: str | Path | None = None,
        workspace: WorkspaceManager | None = None,
    ) -> None:
        self.repository = SkillRepository(builtin_root=builtin_root, workspace=workspace)

    # ─── 导入 ────────────────────────────────────────────────────────────

    def import_zip(self, data: bytes, space_id: int | str | None) -> list[str]:
        """把 zip 里的 skill 包安装到目标 scope 目录。

        支持一个 zip 里包含多个 skill（每个 skill 一个顶层目录）。
        安装目录名以 frontmatter 的 ``name`` 为准，保证「一个名字一份内容」。

        Args:
            data: zip 字节
            space_id: 空间 ID；None 表示装进内置库（谨慎使用）

        Returns:
            安装成功的 skill 名列表（已排序）

        Raises:
            SkillImportError: zip 非法、无有效 SKILL.md、或包含越界路径
        """
        staging = Path(tempfile.mkdtemp(prefix="skill-import-"))
        try:
            self._extract_safely(data, staging)
            skill_dirs = self._find_skill_dirs(staging)
            if not skill_dirs:
                raise SkillImportError("zip 中未找到任何 SKILL.md")

            target_root = self.repository.install_dir(space_id)
            installed: list[str] = []
            for skill_dir in skill_dirs:
                name = self._validate(skill_dir / SKILL_FILE)
                dest = target_root / name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(skill_dir, dest)
                installed.append(name)

            logger.info(
                "skill 导入完成",
                space_id=str(space_id),
                skills=installed,
            )
            return sorted(installed)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    # ─── 装配 ────────────────────────────────────────────────────────────

    def build_prompt_blocks(self, names: list[str], space_id: int | str | None) -> str:
        """把选中的 skill 正文渲染为可注入 system prompt 的文本。"""
        if not names:
            return ""

        max_chars = get_config().skill.max_skill_chars
        skills = self.repository.load_selected(names, space_id)
        blocks = [skill.manifest.to_prompt_block(max_chars=max_chars) for skill in skills]
        return "\n\n".join(blocks)

    def resolve_allowed_tools(self, names: list[str], space_id: int | str | None) -> set[str] | None:
        """返回选中 skill 的工具交集声明。

        Returns:
            ``None`` 表示「不额外限制」（任一 skill 未声明即为 None）；
            否则返回并集——多个 skill 各自声明时，合起来才是它们需要的工具。
        """
        if not names:
            return None

        skills = self.repository.load_selected(names, space_id)
        if not skills:
            return None

        declared = [set(skill.manifest.allowed_tools) for skill in skills]
        if any(not tools for tools in declared):
            # 有一个没声明就整体放开：不能因为 A 声明了、B 没声明，就把 B 需要的工具砍掉
            return None
        merged: set[str] = set()
        for tools in declared:
            merged |= tools
        return merged

    def list_skills(self, space_id: int | str | None) -> list[DiscoveredSkill]:
        """列出两级可见的全部 skill。"""
        return self.repository.discover(space_id)

    def find(self, name: str, space_id: int | str | None) -> DiscoveredSkill | None:
        return self.repository.find(name, space_id)

    # ─── 内部 ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_safely(data: bytes, staging: Path) -> None:
        """逐条目校验后解压，拒绝任何越界路径。"""
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise SkillImportError("上传内容不是合法的 zip 文件") from exc

        with archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = SkillService._safe_target(staging, member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(target, "wb") as dest:
                    shutil.copyfileobj(source, dest)

    @staticmethod
    def _safe_target(staging: Path, member_name: str) -> Path:
        """校验 zip 条目路径，返回落盘目标。越界即抛异常（整包拒绝）。"""
        if not member_name or member_name.endswith("/"):
            raise SkillImportError(f"zip 条目名非法: {member_name!r}")

        raw = Path(member_name.replace("\\", "/"))
        if raw.is_absolute() or raw.drive or ".." in raw.parts:
            raise SkillImportError(f"zip 包含越界路径，已拒绝: {member_name}")

        target = (staging / raw).resolve()
        if not target.is_relative_to(staging.resolve()):
            raise SkillImportError(f"zip 包含越界路径，已拒绝: {member_name}")
        return target

    @staticmethod
    def _find_skill_dirs(staging: Path) -> list[Path]:
        """找出所有含 SKILL.md 的目录（最多两层，兼容「包了一层外层目录」的 zip）。"""
        candidates: list[Path] = []
        for path in staging.rglob(SKILL_FILE):
            candidates.append(path.parent)
        # 避免同一 skill 被父子目录重复计入（父目录没有 SKILL.md，天然不会）
        return sorted(set(candidates))

    @staticmethod
    def _validate(skill_file: Path) -> str:
        """校验 SKILL.md 并返回其 name。"""
        try:
            manifest = parse_skill_md(skill_file.read_text(encoding="utf-8"))
        except SkillManifestError as exc:
            raise SkillImportError(f"{skill_file.parent.name}: {exc}") from exc
        return manifest.name


_service: SkillService | None = None


def get_skill_service() -> SkillService:
    """全局 SkillService（无状态，可安全复用）。"""
    global _service
    if _service is None:
        _service = SkillService()
    return _service


def reset_skill_service() -> None:
    """重置单例（测试用）。"""
    global _service
    _service = None
