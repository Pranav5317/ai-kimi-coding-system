import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from tools.filesystem import WorkspaceSandbox


DEFAULT_PROJECT_STATE_TEMPLATE = (
    "# Project State\n\n"
    "## Project Overview\n"
    "No project overview recorded yet.\n\n"
    "## User Requirements\n"
    "No user requirements recorded yet.\n\n"
    "## Technology Stack\n"
    "No technology stack selected yet.\n\n"
    "## Architecture\n"
    "No architecture defined yet.\n\n"
    "## Agent Responsibilities\n"
    "- Agent 1 (Frontend Developer): UI components, styling, client-side logic\n"
    "- Agent 2 (Backend Developer): Server architecture, API endpoints, backend logic\n"
    "- Agent 3 (Data Manager): Database schemas, migrations, CRUD models\n"
    "- Agent 4 (Supervisor): Monitoring, scope validation, escalation & permission tracking\n"
    "- Agent 5 (Project Manager): Application lifecycle, workspace management, dev servers, coordination\n\n"
    "## Current Progress\n"
    "Project initialized.\n\n"
    "## Current Tasks\n"
    "No active tasks assigned yet.\n\n"
    "## Completed Tasks\n"
    "No completed tasks recorded yet.\n\n"
    "## Important Decisions\n"
    "No major architectural decisions recorded yet.\n\n"
    "## Known Issues\n"
    "No known issues recorded.\n\n"
    "## Component Dependencies\n"
    "No component dependencies recorded yet.\n\n"
    "## Project Structure\n"
    "Standard sandboxed workspace layout.\n\n"
    "## Pending User Decisions\n"
    "No pending decisions.\n"
)

CANONICAL_SECTIONS: List[str] = [
    "Project Overview",
    "User Requirements",
    "Technology Stack",
    "Architecture",
    "Agent Responsibilities",
    "Current Progress",
    "Current Tasks",
    "Completed Tasks",
    "Important Decisions",
    "Known Issues",
    "Component Dependencies",
    "Project Structure",
    "Pending User Decisions"
]

SECTION_KEY_MAP: Dict[str, str] = {
    "project_overview": "Project Overview",
    "overview": "Project Overview",
    "user_requirements": "User Requirements",
    "requirements": "User Requirements",
    "technology_stack": "Technology Stack",
    "tech_stack": "Technology Stack",
    "architecture": "Architecture",
    "agent_responsibilities": "Agent Responsibilities",
    "responsibilities": "Agent Responsibilities",
    "current_progress": "Current Progress",
    "progress": "Current Progress",
    "current_tasks": "Current Tasks",
    "tasks": "Current Tasks",
    "completed_tasks": "Completed Tasks",
    "completed": "Completed Tasks",
    "important_decisions": "Important Decisions",
    "decisions": "Important Decisions",
    "known_issues": "Known Issues",
    "issues": "Known Issues",
    "component_dependencies": "Component Dependencies",
    "dependencies": "Component Dependencies",
    "project_structure": "Project Structure",
    "structure": "Project Structure",
    "pending_user_decisions": "Pending User Decisions",
    "pending_decisions": "Pending User Decisions"
}


class ProjectStateManager:
    """
    Manages persistent PROJECT_STATE.md inside the sandboxed workspace.
    Maintains structured current project state (requirements, architecture, tech stack,
    progress, tasks, decisions, issues) that survives LLM context compaction.
    Uses the existing WorkspaceSandbox for secure filesystem interactions.
    """

    def __init__(
        self,
        sandbox: WorkspaceSandbox,
        state_file_name: str = "PROJECT_STATE.md"
    ) -> None:
        self.sandbox = sandbox
        self.state_file_name = state_file_name
        self.initialize_state()

    def initialize_state(self, overwrite: bool = False) -> str:
        """
        Initializes the PROJECT_STATE.md file if it does not already exist.
        """
        try:
            resolved = self.sandbox.validate_and_resolve(self.state_file_name)
            if not resolved.exists() or overwrite:
                return self.sandbox.create_file(
                    path=self.state_file_name,
                    content=DEFAULT_PROJECT_STATE_TEMPLATE
                )
            return f"State file '{self.state_file_name}' already exists."
        except Exception as e:
            return f"Error initializing project state: {str(e)}"

    def parse_sections(self, content: str) -> Dict[str, str]:
        """
        Parses markdown content into a dictionary of section_name -> section_body.
        """
        sections: Dict[str, str] = {}
        current_section: Optional[str] = None
        current_lines: List[str] = []

        lines = content.splitlines()
        for line in lines:
            header_match = re.match(r"^##\s+(.+)$", line)
            if header_match:
                if current_section is not None:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = header_match.group(1).strip()
                current_lines = []
            elif current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def format_sections(self, sections: Dict[str, str]) -> str:
        """
        Formats a dictionary of sections into a canonical markdown document.
        Preserves canonical section ordering while retaining any custom sections.
        """
        doc_parts: List[str] = ["# Project State\n"]

        # 1. Output canonical sections in preferred order
        written_sections = set()
        for canon in CANONICAL_SECTIONS:
            content = sections.get(canon, "").strip()
            if not content:
                content = "None recorded."
            doc_parts.append(f"## {canon}\n{content}\n")
            written_sections.add(canon)

        # 2. Output any custom sections not in CANONICAL_SECTIONS
        for sec_name, sec_content in sections.items():
            if sec_name not in written_sections:
                doc_parts.append(f"## {sec_name}\n{sec_content.strip()}\n")

        return "\n".join(doc_parts).strip() + "\n"

    def read_state(self, section: Optional[str] = None, **kwargs: Any) -> str:
        """
        Reads the current project state from PROJECT_STATE.md.
        If a specific section is requested, extracts and returns only that section.
        """
        try:
            raw_content = self.sandbox.read_file(self.state_file_name)
            if raw_content.startswith("--- Content of"):
                # Strip WorkspaceSandbox wrapper markers if present
                lines = raw_content.splitlines()
                inner_lines = lines[1:-1] if len(lines) >= 2 and lines[-1].startswith("--- End") else lines
                content = "\n".join(inner_lines)
            else:
                content = raw_content

            if not section or str(section).strip().lower() in ("all", "full", "complete"):
                return content

            # Section-specific lookup
            clean_sec = str(section).strip()
            lookup_key = SECTION_KEY_MAP.get(clean_sec.lower(), clean_sec)

            sections = self.parse_sections(content)
            # Case-insensitive section lookup
            for sec_name, sec_body in sections.items():
                if sec_name.lower() == lookup_key.lower():
                    return f"## {sec_name}\n{sec_body}"

            return f"Section '{clean_sec}' not found in {self.state_file_name}. Available sections: {list(sections.keys())}"

        except Exception as e:
            return f"Error reading project state: {str(e)}"

    def update_state(
        self,
        sections: Optional[Union[Dict[str, str], str]] = None,
        content: Optional[str] = None,
        section: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Updates specific sections of PROJECT_STATE.md while preserving all untouched sections.
        Accepts dictionary of sections, section/content pair, positional (section, content),
        or keyword arguments (e.g. tech_stack='Python/Flask', current_tasks='...').
        """
        try:
            # Read existing state
            resolved = self.sandbox.validate_and_resolve(self.state_file_name)
            if not resolved.exists():
                self.initialize_state()

            raw_existing = resolved.read_text(encoding="utf-8")
            current_sections = self.parse_sections(raw_existing)

            # Gather updates
            updates: Dict[str, str] = {}

            # Handle explicit section="...", content="..." or positional
            target_sec = section if section is not None else kwargs.pop("section", None)
            target_content = content if content is not None else kwargs.pop("content", None)

            if target_sec is not None and target_content is not None:
                canon_k = SECTION_KEY_MAP.get(str(target_sec).strip().lower(), str(target_sec).strip())
                updates[canon_k] = str(target_content).strip()
            elif isinstance(sections, str) and target_content is not None:
                canon_k = SECTION_KEY_MAP.get(sections.strip().lower(), sections.strip())
                updates[canon_k] = str(target_content).strip()
            elif isinstance(sections, dict):
                for k, v in sections.items():
                    canon_k = SECTION_KEY_MAP.get(str(k).strip().lower(), str(k).strip())
                    updates[canon_k] = str(v).strip()

            # Handle direct keyword arguments (e.g. current_progress="...", tech_stack="...")
            for kw, val in kwargs.items():
                if val is not None and str(val).strip():
                    canon_k = SECTION_KEY_MAP.get(kw.lower(), kw.replace("_", " ").title())
                    updates[canon_k] = str(val).strip()

            if not updates:
                return "No state updates provided. Project state remains unchanged."

            # Merge updates into existing sections
            for sec_name, new_body in updates.items():
                current_sections[sec_name] = new_body

            # Format and save
            new_content = self.format_sections(current_sections)
            self.sandbox.edit_file(path=self.state_file_name, content=new_content)

            updated_names = list(updates.keys())
            return f"Project state successfully updated. Modified sections: {updated_names}"

        except Exception as e:
            return f"Error updating project state: {str(e)}"

    def onboard_existing_project(self, force: bool = False) -> str:
        """
        Scans workspace for pre-existing codebase files, manifests, and frameworks.
        Automatically initializes PROJECT_STATE.md with actual project facts if uninitialized.
        """
        try:
            resolved = self.sandbox.validate_and_resolve(self.state_file_name)
            if resolved.exists() and not force:
                raw_existing = resolved.read_text(encoding="utf-8")
                # If state file has already been populated with non-default overview, skip
                if "No project overview recorded yet." not in raw_existing and "Project initialized." not in raw_existing:
                    return "Project state already onboarded."

            ws_root = self.sandbox.workspace_root
            ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode", "out"}

            ext_counts: Dict[str, int] = {}
            found_manifests: List[str] = []
            found_entry_points: List[str] = []
            detected_deps: List[str] = []

            manifest_names = {"package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "CMakeLists.txt", "Makefile"}
            entry_names = {"main.py", "app.py", "server.js", "index.js", "App.tsx", "App.jsx", "main.cpp", "Main.java", "main.go", "main.rs", "index.html"}

            import os
            for root, dirs, files in os.walk(str(ws_root)):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

                for f in files:
                    if f.startswith("."):
                        continue
                    if f == self.state_file_name or f == "CODE_DIARY.md":
                        continue

                    rel_p = str(Path(root, f).relative_to(ws_root))
                    if f in manifest_names:
                        found_manifests.append(rel_p)
                        # Read dependency hints
                        try:
                            content = (Path(root) / f).read_text(encoding="utf-8", errors="ignore").lower()
                            for dep in ("fastapi", "flask", "django", "express", "react", "vue", "svelte", "next", "vite", "sqlite", "postgres", "mysql", "mongodb", "sqlalchemy", "torch", "tensorflow", "boost", "spring"):
                                if dep in content and dep not in detected_deps:
                                    detected_deps.append(dep)
                        except Exception:
                            pass

                    if f in entry_names:
                        found_entry_points.append(rel_p)

                    ext = Path(f).suffix.lower()
                    if ext:
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1

            detected_routes: List[str] = []
            detected_components: List[str] = []

            # Deep code inspection on entry points and key files
            for root, dirs, files in os.walk(str(ws_root)):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for f in files:
                    if f.startswith(".") or f in (self.state_file_name, "CODE_DIARY.md"):
                        continue
                    file_path = Path(root) / f
                    if file_path.stat().st_size > 512 * 1024:
                        continue
                    ext = file_path.suffix.lower()
                    if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".cpp", ".java", ".go", ".rs"):
                        try:
                            file_text = file_path.read_text(encoding="utf-8", errors="ignore")
                            rel_p = str(file_path.relative_to(ws_root))

                            # Route & API pattern matching
                            matches = re.findall(r'(@(?:app|router|api)\.(?:get|post|put|delete|route)\s*\(\s*["\']([^"\']+)["\'])', file_text, re.IGNORECASE)
                            for m in matches:
                                route_str = f"{rel_p} -> {m[1]}"
                                if route_str not in detected_routes and len(detected_routes) < 15:
                                    detected_routes.append(route_str)

                            # UI Form & Upload detection
                            if "<form" in file_text.lower() or 'type="file"' in file_text.lower() or "input type='file'" in file_text.lower():
                                comp_str = f"{rel_p} (HTML File Upload Form)"
                                if comp_str not in detected_components:
                                    detected_components.append(comp_str)

                            # ML / Vision model hints
                            if any(k in file_text.lower() for k in ("cv2", "ultralytics", "yolo", "torch", "tensorflow", "keras")):
                                comp_str = f"{rel_p} (ML / Image Analysis Pipeline)"
                                if comp_str not in detected_components:
                                    detected_components.append(comp_str)

                            # Database model hints
                            if any(k in file_text.lower() for k in ("sqlite3", "sqlalchemy", "db.model", "mongoose")):
                                comp_str = f"{rel_p} (Database Access / ORM Layer)"
                                if comp_str not in detected_components:
                                    detected_components.append(comp_str)
                        except Exception:
                            pass

            if not ext_counts and not found_manifests:
                return "Workspace is empty. Standard template preserved."

            # Infer primary languages
            top_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            lang_summary = ", ".join(f"{ext} ({cnt} files)" for ext, cnt in top_exts)

            tech_stack_parts = [f"Detected File Types: {lang_summary}"]
            if found_manifests:
                tech_stack_parts.append(f"Manifests: {', '.join(found_manifests)}")
            if detected_deps:
                tech_stack_parts.append(f"Detected Frameworks/Dependencies: {', '.join(detected_deps)}")

            overview = f"Pre-existing project detected at '{ws_root.name}'. Codebase indexed and ready for interactive modification ('vibecoding')."
            tech_stack = "\n".join(tech_stack_parts)

            arch_parts = [
                f"Entry Points: {', '.join(found_entry_points) if found_entry_points else 'None'}",
                f"Detected Server Endpoints: {', '.join(detected_routes) if detected_routes else 'None detected'}",
                f"Detected Systems & Components: {', '.join(detected_components) if detected_components else 'General source files'}"
            ]
            architecture = "\n".join(arch_parts)

            structure = f"Manifests: {', '.join(found_manifests) if found_manifests else 'None'}\nEntry Points: {', '.join(found_entry_points) if found_entry_points else 'None'}"
            progress = "Existing codebase indexed. Architecture and endpoints discovered. Ready for developer instructions."

            return self.update_state(
                project_overview=overview,
                tech_stack=tech_stack,
                architecture=architecture,
                project_structure=structure,
                current_progress=progress
            )

        except Exception as e:
            return f"Error onboarding existing project: {str(e)}"


# --- Tool Definitions for LLM Function Calling ---

PROJECT_STATE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_project_state",
            "description": (
                "Read the persistent PROJECT_STATE.md document from the workspace. "
                "Retrieves current project requirements, tech stack, architecture, progress, tasks, decisions, and known issues. "
                "Call this to inspect the current state of the application across turns or after context compaction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": (
                            "Optional specific section name to read (e.g. 'Project Overview', 'User Requirements', "
                            "'Technology Stack', 'Architecture', 'Current Tasks', 'Important Decisions', 'Known Issues'). "
                            "If omitted, returns the complete project state."
                        )
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_project_state",
            "description": (
                "Update persistent PROJECT_STATE.md sections with current project status, requirements, architectural decisions, "
                "or task progress. Preserves all other untouched sections."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_overview": {"type": "string", "description": "High-level summary of the application."},
                    "user_requirements": {"type": "string", "description": "Functional and non-functional requirements."},
                    "tech_stack": {"type": "string", "description": "Technologies, frameworks, databases, and libraries in use."},
                    "architecture": {"type": "string", "description": "System architecture, components, and API design."},
                    "current_progress": {"type": "string", "description": "Current phase and development status."},
                    "current_tasks": {"type": "string", "description": "Active tasks currently in progress or planned next."},
                    "completed_tasks": {"type": "string", "description": "Milestones and tasks completed so far."},
                    "important_decisions": {"type": "string", "description": "Key technical decisions or design choices made."},
                    "known_issues": {"type": "string", "description": "Bugs, limitations, or blockers."},
                    "component_dependencies": {"type": "string", "description": "Component connections, schemas, or API contracts."},
                    "project_structure": {"type": "string", "description": "Directory layout and file locations."},
                    "pending_user_decisions": {"type": "string", "description": "Questions or items awaiting user review."}
                },
                "required": []
            }
        }
    }
]

