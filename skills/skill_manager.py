import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class Skill:
    """Represents a specialized capability or workflow skill module."""
    name: str
    description: str
    target_agent: str
    instructions: str
    file_path: Path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "target_agent": self.target_agent,
            "file_path": str(self.file_path)
        }


class SkillManager:
    """
    Discovers, loads, and manages specialized Skill modules across builtin libraries
    and active project workspace directories.
    """

    def __init__(self, builtin_dir: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self.builtin_dir = builtin_dir or (Path(__file__).resolve().parent / "builtin")
        self.workspace_root = workspace_root
        self.skills: Dict[str, Skill] = {}
        self.discover_skills()

    def set_workspace_root(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.discover_skills()

    def _parse_frontmatter(self, text: str) -> Tuple[Dict[str, str], str]:
        """Parses YAML frontmatter delimited by --- at top of markdown files."""
        from typing import Tuple
        meta: Dict[str, str] = {}
        body = text

        pattern = r"^\s*---\r?\n(.*?)\r?\n---\r?\n(.*)$"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            frontmatter_str = match.group(1)
            body = match.group(2).strip()

            for line in frontmatter_str.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip("\"'")

        return meta, body

    def discover_skills(self) -> Dict[str, Skill]:
        """Scans builtin and workspace skills folders for markdown skill definitions."""
        self.skills.clear()

        search_dirs: List[Path] = []
        if self.builtin_dir.exists():
            search_dirs.append(self.builtin_dir)

        if self.workspace_root:
            ws_skills = self.workspace_root / "skills"
            if ws_skills.exists():
                search_dirs.append(ws_skills)

        for sdir in search_dirs:
            for root, _, files in os.walk(sdir):
                for fname in files:
                    if fname.lower() in ("skill.md", "skill.markdown") or fname.endswith(".skill.md"):
                        fpath = Path(root) / fname
                        try:
                            content = fpath.read_text(encoding="utf-8")
                            meta, body = self._parse_frontmatter(content)
                            name = meta.get("name") or fpath.parent.name
                            desc = meta.get("description") or f"Specialized skill defined in {fpath.name}"
                            target = meta.get("target_agent") or meta.get("agent") or "agent5"

                            skill = Skill(
                                name=name.strip().lower(),
                                description=desc.strip(),
                                target_agent=target.strip().lower(),
                                instructions=body,
                                file_path=fpath
                            )
                            self.skills[skill.name] = skill
                        except Exception:
                            pass

        return self.skills

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns list of all available skill metadata dictionaries."""
        self.discover_skills()
        return [skill.to_dict() for skill in sorted(self.skills.values(), key=lambda s: s.name)]

    def get_skill(self, name: str) -> Optional[Skill]:
        """Gets a skill by name (case-insensitive)."""
        self.discover_skills()
        clean = name.strip().lower()
        return self.skills.get(clean)

    def apply_skill(self, name: str) -> str:
        """Loads and formats a skill's instructions for insertion into reasoning context."""
        skill = self.get_skill(name)
        if not skill:
            available = ", ".join(sorted(list(self.skills.keys()))) if self.skills else "None"
            return f"Skill Error: Skill '{name}' not found. Available skills: {available}"

        return (
            f"=== APPLIED SKILL: {skill.name.upper()} ===\n"
            f"Target Agent: {skill.target_agent}\n"
            f"Description: {skill.description}\n\n"
            f"Specialized Instructions & Guidance:\n"
            f"{skill.instructions}\n"
            f"=== END OF SKILL: {skill.name.upper()} ==="
        )

    def auto_match_skills(self, user_prompt: str) -> List[Skill]:
        """
        Analyzes user prompt and automatically identifies matching Skill modules
        based on explicit skill names and specialized domain phrases.
        """
        if not user_prompt or not user_prompt.strip():
            return []

        self.discover_skills()
        prompt_lower = user_prompt.lower()
        matched: List[Skill] = []

        # Domain triggers mapping for built-in skills
        skill_triggers: Dict[str, List[str]] = {
            "fastapi-backend": ["fastapi", "fastapi-backend", "fastapi backend"],
            "react-frontend": ["react", "react-frontend", "react frontend", "jsx component", "tsx component"],
            "database-migration": ["database migration", "alembic", "db migration", "migration script"],
            "unit-testing": ["unit test", "unit testing", "pytest", "unit-testing", "jest test"],
            "nextjs-frontend": ["nextjs", "next.js", "next-js", "app router", "server components", "nextjs-frontend"],
            "vue-frontend": ["vue", "vuejs", "vue.js", "pinia", "vue-frontend"],
            "svelte-frontend": ["svelte", "sveltekit", "svelte 5", "svelte-frontend"],
            "express-nodejs": ["express", "expressjs", "express.js", "node.js backend", "express-nodejs"],
            "django-backend": ["django", "django rest", "drf", "django-backend"],
            "nestjs-backend": ["nestjs", "nest.js", "nest js", "nestjs-backend"],
            "prisma-orm": ["prisma", "schema.prisma", "prisma migrate", "prisma-orm"],
            "mongodb-mongoose": ["mongodb", "mongoose", "mongodb-mongoose"]
        }

        for skill in self.skills.values():
            s_name = skill.name.lower()
            
            # Check explicit name or custom triggers
            triggers = skill_triggers.get(s_name, [s_name, s_name.replace("-", " ")])
            
            if any(t in prompt_lower for t in triggers):
                if skill not in matched:
                    matched.append(skill)

        return matched
