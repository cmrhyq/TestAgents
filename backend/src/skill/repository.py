"""Skill 文件系统发现。

内容以文件为真源，每次读取都重新解析 ``SKILL.md``，不做 DB 缓存。
分两级发现，空间级同名 skill 覆盖内置 skill。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.config import resolve_backend_path
from src.core.logging import get_logger
from src.skill.manifest import SkillManifest, SkillManifestError, parse_skill_md
from src.workspace.manager import WorkspaceManager

logger = get_logger(__name__)

SKILL_FILE = "SKILL.md"
SPACE_SKILL_DIR = ".skills"

SCOPE_BUILTIN = "builtin"
SCOPE_SPACE = "space"


@dataclass(slots=True)
class DiscoveredSkill:
    """发现到的 skill：元数据 + 真实位置。"""

    manifest: SkillManifest
    directory: Path
    scope: str

    @property
    def name(self) -> str:
        """skill 名，取自 frontmatter。"""
        return self.manifest.name

    @property
    def display_path(self) -> str:
        """相对 backend 根的路径，用于前端展示与入库；不在根下时返回绝对路径。"""
        from src.core.config import get_backend_root

        try:
            return self.directory.resolve().relative_to(get_backend_root()).as_posix()
        except ValueError:
            return str(self.directory.resolve())


class SkillRepository:
    """扫描、定位与安装 skill 目录。

    目录结构以文件系统为真源，本类不做缓存。

    Args:
        builtin_root: 内置 skill 根目录；None 时取配置 ``skill.builtin_root``
        workspace: 工作目录管理器；None 时取全局单例
    """

    def __init__(
        self,
        builtin_root: str | Path | None = None,
        workspace: WorkspaceManager | None = None,
    ) -> None:
        if builtin_root is None:
            from src.core.config import get_config

            builtin_root = resolve_backend_path(get_config().skill.builtin_root)
        if workspace is None:
            from src.workspace.manager import get_workspace_manager

            workspace = get_workspace_manager()

        self.builtin_root = Path(builtin_root).resolve()
        self.workspace = workspace

    # ─── 发现 ────────────────────────────────────────────────────────────

    def discover(self, space_id: int | str | None) -> list[DiscoveredSkill]:
        """扫描两级目录，返回按名排序、空间级覆盖同名的 skill 列表。

        空间目录不存在时只返回内置 skill。

        Args:
            space_id: 空间 ID；None 时只扫描内置目录

        Returns:
            去重后的 skill 列表
        """
        found: dict[str, DiscoveredSkill] = {}

        for skill in self._scan(self.builtin_root, SCOPE_BUILTIN):
            found[skill.name] = skill

        if space_id is not None:
            space_skills_dir = self._space_skill_dir(space_id)
            for skill in self._scan(space_skills_dir, SCOPE_SPACE):
                # 空间级直接覆盖同名内置
                found[skill.name] = skill

        return sorted(found.values(), key=lambda s: s.name)

    def find(self, name: str, space_id: int | str | None = None) -> DiscoveredSkill | None:
        """按名查找 skill，空间级优先。

        Args:
            name: skill 名
            space_id: 空间 ID；None 时只查内置目录

        Returns:
            命中的 skill；不存在或格式非法时返回 None
        """
        if space_id is not None:
            candidate = self._load(self._space_skill_dir(space_id) / name, SCOPE_SPACE)
            if candidate is not None:
                return candidate
        return self._load(self.builtin_root / name, SCOPE_BUILTIN)

    def load_selected(self, names: list[str], space_id: int | str | None) -> list[DiscoveredSkill]:
        """按名批量加载，不存在或格式非法的名字记录 warning 后跳过。

        Args:
            names: skill 名列表
            space_id: 空间 ID

        Returns:
            成功加载的 skill 列表，顺序与入参一致
        """
        result: list[DiscoveredSkill] = []
        for name in names:
            skill = self.find(name, space_id)
            if skill is None:
                logger.warning("指定的 skill 不存在，已忽略", skill=name, space_id=str(space_id))
                continue
            result.append(skill)
        return result

    # ─── 安装 ────────────────────────────────────────────────────────────

    def install_dir(self, space_id: int | str | None) -> Path:
        """返回导入目标根目录，不存在时创建。

        Args:
            space_id: 空间 ID；None 表示内置目录

        Returns:
            目标目录路径
        """
        if space_id is None:
            self.builtin_root.mkdir(parents=True, exist_ok=True)
            return self.builtin_root

        target = self._space_skill_dir(space_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ─── 内部 ────────────────────────────────────────────────────────────

    def _space_skill_dir(self, space_id: int | str) -> Path:
        """返回空间级 skill 根目录。"""
        return self.workspace.space_dir(space_id) / SPACE_SKILL_DIR

    def _scan(self, root: Path, scope: str) -> list[DiscoveredSkill]:
        """扫描一层子目录；根目录不存在时返回空列表。"""
        if not root.is_dir():
            return []

        skills: list[DiscoveredSkill] = []
        # 只扫一层：skill 以目录为单位，递归会让 references/ 下的 SKILL.md 被误认作独立 skill
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            skill = self._load(child, scope)
            if skill is not None:
                skills.append(skill)
        return skills

    def _load(self, skill_dir: Path, scope: str) -> DiscoveredSkill | None:
        """读取并解析目录下的 ``SKILL.md``，缺失或非法时返回 None。"""
        skill_file = skill_dir / SKILL_FILE
        if not skill_file.is_file():
            return None

        try:
            manifest = parse_skill_md(skill_file.read_text(encoding="utf-8"))
        except SkillManifestError as exc:
            logger.warning("skill 格式非法，已跳过", path=str(skill_file), error=str(exc))
            return None
        except OSError as exc:
            logger.warning("skill 读取失败，已跳过", path=str(skill_file), error=str(exc))
            return None

        return DiscoveredSkill(manifest=manifest, directory=skill_dir, scope=scope)
