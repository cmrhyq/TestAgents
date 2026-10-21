"""Skill 文件系统发现。

**文件是真源**：每次需要 skill 内容都从 ``SKILL.md`` 读，不做 DB 缓存，
避免「改了文件但 Agent 还在用旧内容」这类难查的问题。

两级发现，空间级覆盖内置同名：

    workspaces/{space_id}/.skills/{name}/SKILL.md   ← 优先级高
    backend/skills/{name}/SKILL.md                  ← 随代码分发
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
        return self.manifest.name

    @property
    def display_path(self) -> str:
        """相对 backend 根的路径，供前端展示与入库。"""
        from src.core.config import get_backend_root

        try:
            return self.directory.resolve().relative_to(get_backend_root()).as_posix()
        except ValueError:
            return str(self.directory.resolve())


class SkillRepository:
    """扫描、定位、安装 skill 目录。

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
        """扫描两级目录，返回去重后的 skill 列表（按名排序）。

        空空间也要能工作：空间目录不存在时只会扫到内置 skill。
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
        """按名查找（空间级优先）。"""
        if space_id is not None:
            candidate = self._load(self._space_skill_dir(space_id) / name, SCOPE_SPACE)
            if candidate is not None:
                return candidate
        return self._load(self.builtin_root / name, SCOPE_BUILTIN)

    def load_selected(self, names: list[str], space_id: int | str | None) -> list[DiscoveredSkill]:
        """按名批量加载；不存在或格式非法的名字静默跳过。

        「用户选了但 skill 已被删」不应该让整轮对话失败——记录 warning 即可，
        Agent 少一份方法论，但仍能正常工作。
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
        """导入 skill 的目标根目录（会确保存在）。"""
        if space_id is None:
            self.builtin_root.mkdir(parents=True, exist_ok=True)
            return self.builtin_root

        target = self._space_skill_dir(space_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ─── 内部 ────────────────────────────────────────────────────────────

    def _space_skill_dir(self, space_id: int | str) -> Path:
        return self.workspace.space_dir(space_id) / SPACE_SKILL_DIR

    def _scan(self, root: Path, scope: str) -> list[DiscoveredSkill]:
        if not root.is_dir():
            return []

        skills: list[DiscoveredSkill] = []
        # 只看一层子目录：skill 是「目录即包」，不做无限递归，
        # 否则 references/ 里放一个 SKILL.md 就会被误认为独立 skill
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            skill = self._load(child, scope)
            if skill is not None:
                skills.append(skill)
        return skills

    def _load(self, skill_dir: Path, scope: str) -> DiscoveredSkill | None:
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
