"""A thin façade over Lmod: the build modules, and the user-facing modulefile links.

A built tool is loadable as ``module load <tool>/<tag>`` because
``<lmod_modules>/<tool>/<tag>.lua`` is a symlink to shpc's ``module.lua``. The layout is
unchanged from 0.4.0, so the old ``find`` and ``clean`` see modules built by the new path.
"""

from pathlib import Path

from ..tags import Tag
from ..utils import globals as gl
from ..utils.modules import load_build_modules as _load_build_modules
from ..utils.perms import ensure_shared_dir


class Lmod:
    def __init__(self, modules_dir: Path | None = None):
        self.modules_dir = (
            Path(modules_dir) if modules_dir is not None else gl.lmod_modules()
        )

    def load_build_modules(self) -> bool:
        """``module load shpc singularity`` into this process (warns and continues if absent)."""
        return _load_build_modules()

    def link_path(self, tool: str, tag: Tag) -> Path:
        return self.modules_dir / tool / f"{tag.raw}.lua"

    def link(self, tool: str, tag: Tag, target: Path) -> Path:
        """Point ``<tool>/<tag>.lua`` at ``target``, replacing any existing link."""
        path = self.link_path(tool, tag)
        ensure_shared_dir(path.parent)
        if path.is_symlink() or path.exists():
            path.unlink()
        path.symlink_to(target)
        return path

    def linked_tags(self, tool: str) -> list[str]:
        """Tags with a modulefile link for ``tool``, dangling or not."""
        tool_dir = self.modules_dir / tool
        if not tool_dir.is_dir():
            return []
        return sorted(p.stem for p in tool_dir.glob("*.lua"))
