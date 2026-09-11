import os
import json
import re
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from diary.code_diary import CodeDiary


def sanitize_code_content(raw_content: Any) -> str:
    """
    Sanitizes and extracts clean, valid source code from raw LLM output or tool arguments.
    Eliminates JSON wrapper objects (e.g. {"python": "..."}), markdown fences, and literal \\n escapes.
    """
    if raw_content is None:
        return ""

    # 1. If passed directly as a dictionary
    if isinstance(raw_content, dict):
        for key in ("code", "python", "html", "javascript", "js", "ts", "css", "sql", "content", "text", "file_content", "body"):
            if key in raw_content and isinstance(raw_content[key], (str, dict)):
                return sanitize_code_content(raw_content[key])
        if len(raw_content) == 1:
            val = next(iter(raw_content.values()))
            if isinstance(val, (str, dict)):
                return sanitize_code_content(val)
        return json.dumps(raw_content, indent=2)

    text = str(raw_content).strip()
    if not text:
        return ""

    # 2. Check if the string is a stringified JSON object
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("{\\") and text.endswith("}")):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return sanitize_code_content(parsed)
        except Exception:
            pass

    # 3. Regex matching for JSON wrapper structures e.g. {"python": "..."} or {"html": "..."}
    json_wrapper_pattern = r'^\s*\{\s*"(?:python|html|javascript|js|ts|css|sql|json|code|content|text|file_content)"\s*:\s*"(.*)"\s*\}\s*$'
    match = re.match(json_wrapper_pattern, text, re.DOTALL)
    if match:
        extracted = match.group(1)
        try:
            unwrapped = json.loads(f'"{extracted}"')
            return sanitize_code_content(unwrapped)
        except Exception:
            cleaned = extracted.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
            return sanitize_code_content(cleaned)

    # 4. Handle unclosed JSON prefix / suffix artifacts like {"python": "import flask... or ..."}
    prefix_match = re.match(r'^\s*\{\s*"(?:python|html|javascript|js|ts|css|sql|code|content|text)"\s*:\s*"(.*)', text, re.DOTALL)
    if prefix_match:
        inner = prefix_match.group(1)
        if inner.endswith('"}'):
            inner = inner[:-2]
        elif inner.endswith('"'):
            inner = inner[:-1]
        cleaned = inner.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        return sanitize_code_content(cleaned)

    # 5. Markdown code fences: ```python ... ``` or ```html ... ``` or ``` ... ```
    fence_pattern = r'^\s*```(?:[a-zA-Z0-9_\-\+]*)\r?\n(.*)\r?\n```\s*$'
    fence_match = re.match(fence_pattern, text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    # Partial code fences at start/end
    if text.startswith("```"):
        first_line_end = text.find("\n")
        if first_line_end != -1:
            rest = text[first_line_end + 1:]
            if rest.rstrip().endswith("```"):
                rest = rest.rstrip()[:-3]
            text = rest

    # 6. Unescape literal \n if string has no real newlines but contains literal '\n'
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')

    return text



class WorkspaceSandbox:
    """
    Manages and enforces security sandboxing for the agent's workspace.
    Guarantees that all file and directory access is strictly contained inside the workspace.
    """

    def __init__(self, workspace_root: Path, diary: Optional[CodeDiary] = None):
        self.workspace_root = workspace_root.resolve()
        self.diary = diary
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.tracked_changes: List[Dict[str, Any]] = []

    def clear_tracked_changes(self) -> None:
        """Clears accumulated file changes for a new prompt turn."""
        self.tracked_changes.clear()

    def record_change(self, target_file: Path, old_content: str, new_content: str, action: str) -> None:
        """Computes unified diffs and records code modifications."""
        display = self._get_display_path(target_file)
        if display == "CHANGES_LOG.md" or display.endswith("/CHANGES_LOG.md") or target_file.name == "CHANGES_LOG.md":
            return
        old_lines = old_content.splitlines(keepends=True) if old_content else []
        new_lines = new_content.splitlines(keepends=True) if new_content else []

        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{display}",
            tofile=f"b/{display}",
            n=3
        ))

        added_count = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        removed_count = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        diff_text = "".join(diff_lines)

        self.tracked_changes.append({
            "path": display,
            "abs_path": str(target_file.resolve()),
            "action": action,
            "added": added_count,
            "removed": removed_count,
            "diff": diff_text
        })

    def write_changes_log(self) -> Path:
        """Writes/updates CHANGES_LOG.md inside the workspace root with tracked unified diffs."""
        log_path = self.workspace_root / "CHANGES_LOG.md"
        if not self.tracked_changes:
            return log_path

        lines = [
            "# Project Code Changes Log",
            f"*Recorded on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "## Summary of Changed Files\n"
        ]

        for change in self.tracked_changes:
            action_badge = "🟢 `[NEW]`" if change["action"] == "NEW" else "🟡 `[MODIFY]`"
            diff_counts = []
            if change["added"] > 0:
                diff_counts.append(f"+{change['added']}")
            if change["removed"] > 0:
                diff_counts.append(f"-{change['removed']}")
            diff_str = f" ({', '.join(diff_counts)})" if diff_counts else ""
            file_url = Path(change["abs_path"]).as_uri()
            lines.append(f"- {action_badge} [{change['path']}]({file_url}){diff_str}")

        lines.append("\n## Detailed Unified Diffs\n")

        for change in self.tracked_changes:
            file_url = Path(change["abs_path"]).as_uri()
            lines.append(f"### [{change['path']}]({file_url})")
            if change["diff"]:
                lines.append(f"```diff\n{change['diff']}\n```\n")
            else:
                lines.append("*(No textual diff available)*\n")

        log_path.write_text("\n".join(lines), encoding="utf-8")
        return log_path

    def generate_changes_summary(self) -> str:
        """Generates a concise markdown summary block with embedded changes card data."""
        if not self.tracked_changes:
            return ""

        log_path = self.write_changes_log()
        log_url = log_path.as_uri()

        total_files = len(self.tracked_changes)
        total_added = sum(c["added"] for c in self.tracked_changes)
        total_removed = sum(c["removed"] for c in self.tracked_changes)

        files_meta = [
            {
                "path": c["path"],
                "abs_path": Path(c["abs_path"]).as_uri(),
                "action": c["action"],
                "added": c["added"],
                "removed": c["removed"]
            }
            for c in self.tracked_changes
        ]

        card_json = json.dumps({
            "total_files": total_files,
            "total_added": total_added,
            "total_removed": total_removed,
            "log_url": log_url,
            "files": files_meta
        })

        summary_lines = [
            f"\n<!-- CHANGES_CARD: {card_json} -->\n",
            "\n---\n### 📝 Code Changes Summary\n"
        ]

        for change in self.tracked_changes:
            action_badge = "🟢 `[NEW]`" if change["action"] == "NEW" else "🟡 `[MODIFY]`"
            diff_counts = []
            if change["added"] > 0:
                diff_counts.append(f"+{change['added']}")
            if change["removed"] > 0:
                diff_counts.append(f"-{change['removed']}")
            diff_str = f" ({', '.join(diff_counts)})" if diff_counts else ""
            file_url = Path(change["abs_path"]).as_uri()
            summary_lines.append(f"- {action_badge} [{change['path']}]({file_url}){diff_str}")

        summary_lines.append(f"\n📄 Detailed unified diffs saved to [CHANGES_LOG.md]({log_url}).")
        return "\n".join(summary_lines)

    def validate_and_resolve(self, relative_or_absolute_path: str) -> Path:
        """
        Validates and resolves a path, ensuring it strictly stays within the workspace sandbox.
        Rejects directory traversal (../), outside absolute paths, and external symlinks.
        
        Raises:
            PermissionError: If the path attempts to escape the workspace sandbox.
            ValueError: If the path is empty or invalid.
        """
        if not relative_or_absolute_path or not relative_or_absolute_path.strip():
            raise ValueError("Path argument cannot be empty.")

        cleaned_path = relative_or_absolute_path.strip()

        # If user passed an absolute path, verify it is inside the workspace
        candidate = Path(cleaned_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.workspace_root / candidate).resolve()

        # Enforce sandbox containment
        try:
            # Python 3.9+ is_relative_to
            is_inside = resolved.is_relative_to(self.workspace_root)
        except AttributeError:
            # Fallback for older python
            common = os.path.commonpath([str(resolved), str(self.workspace_root)])
            is_inside = (common == str(self.workspace_root))

        if not is_inside:
            raise PermissionError(
                f"Security Sandbox Violation: Access denied to '{relative_or_absolute_path}'. "
                f"Paths must remain strictly inside the workspace ({self.workspace_root})."
            )

        return resolved

    def _get_display_path(self, resolved_path: Path) -> str:
        """Returns path relative to workspace root for clean user display."""
        try:
            rel = resolved_path.relative_to(self.workspace_root)
            return rel.as_posix() if rel.as_posix() != "." else "."
        except ValueError:
            return resolved_path.name

    # --- Tool Implementations ---

    def list_files(self, directory: Optional[str] = None, path: Optional[str] = None, **kwargs: Any) -> str:
        """Lists files and directories inside the specified workspace directory."""
        target_str = directory if directory is not None else (path if path is not None else ".")
        try:
            target_dir = self.validate_and_resolve(target_str)
            if not target_dir.exists():
                err = f"Directory '{target_str}' does not exist."
                if self.diary:
                    self.diary.record("LIST_FILES", target_str, "FAILED", err)
                return err

            if not target_dir.is_dir():
                err = f"Path '{target_str}' is a file, not a directory."
                if self.diary:
                    self.diary.record("LIST_FILES", target_str, "FAILED", err)
                return err

            items = []
            for item in sorted(target_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                display_rel = self._get_display_path(item)
                if item.is_dir():
                    items.append(f"[DIR]  {display_rel}/")
                else:
                    size_bytes = item.stat().st_size
                    items.append(f"[FILE] {display_rel} ({size_bytes} bytes)")

            if not items:
                result = f"Directory '{self._get_display_path(target_dir)}' is empty."
            else:
                result = f"Contents of '{self._get_display_path(target_dir)}':\n" + "\n".join(items)

            if self.diary:
                self.diary.record("LIST_FILES", target_str, "SUCCESS", f"{len(items)} items listed")
            return result

        except Exception as e:
            err = f"Error listing directory '{target_str}': {str(e)}"
            if self.diary:
                self.diary.record("LIST_FILES", target_str, "ERROR", str(e))
            return err

    def read_file(self, path: Optional[str] = None, file_path: Optional[str] = None, **kwargs: Any) -> str:
        """Reads the content of a file within the workspace sandbox."""
        target_str = path if path is not None else (file_path if file_path is not None else "")
        try:
            target_file = self.validate_and_resolve(target_str)
            if not target_file.exists():
                err = f"File '{target_str}' does not exist."
                if self.diary:
                    self.diary.record("READ_FILE", target_str, "FAILED", err)
                return err

            if not target_file.is_file():
                err = f"Path '{target_str}' is a directory, not a file."
                if self.diary:
                    self.diary.record("READ_FILE", target_str, "FAILED", err)
                return err

            content = target_file.read_text(encoding="utf-8")
            if self.diary:
                self.diary.record("READ_FILE", target_str, "SUCCESS", f"Read {len(content)} characters")
            return f"--- Content of {self._get_display_path(target_file)} ---\n{content}\n--- End of file ---"

        except UnicodeDecodeError:
            err = f"File '{target_str}' could not be decoded as UTF-8 text."
            if self.diary:
                self.diary.record("READ_FILE", target_str, "ERROR", err)
            return err
        except Exception as e:
            err = f"Error reading file '{target_str}': {str(e)}"
            if self.diary:
                self.diary.record("READ_FILE", target_str, "ERROR", str(e))
            return err

    def create_directory(self, path: Optional[str] = None, directory: Optional[str] = None, **kwargs: Any) -> str:
        """Creates a directory within the workspace sandbox."""
        target_str = path if path is not None else (directory if directory is not None else "")
        try:
            target_dir = self.validate_and_resolve(target_str)
            target_dir.mkdir(parents=True, exist_ok=True)
            display = self._get_display_path(target_dir)
            msg = f"Directory '{display}' created successfully."
            if self.diary:
                self.diary.record("CREATE_DIRECTORY", display, "SUCCESS", "Directory created")
            return msg
        except Exception as e:
            err = f"Error creating directory '{target_str}': {str(e)}"
            if self.diary:
                self.diary.record("CREATE_DIRECTORY", target_str, "ERROR", str(e))
            return err

    def create_file(self, path: Optional[str] = None, content: Optional[str] = None, text: Optional[str] = None, **kwargs: Any) -> str:
        """Creates a new file with specified content within the workspace sandbox."""
        target_str = path if path is not None else ""
        raw_content = content if content is not None else (text if text is not None else "")
        content_str = sanitize_code_content(raw_content)
        try:
            target_file = self.validate_and_resolve(target_str)
            old_content = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
            action = "MODIFY" if target_file.exists() else "NEW"

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content_str, encoding="utf-8")
            display = self._get_display_path(target_file)
            self.record_change(target_file, old_content, content_str, action)

            msg = f"File '{display}' created successfully ({len(content_str)} bytes written)."
            if self.diary:
                self.diary.record("CREATE_FILE", display, "SUCCESS", f"Created file ({len(content_str)} chars)")
            return msg
        except Exception as e:
            err = f"Error creating file '{target_str}': {str(e)}"
            if self.diary:
                self.diary.record("CREATE_FILE", target_str, "ERROR", str(e))
            return err

    def edit_file(self, path: Optional[str] = None, content: Optional[str] = None, text: Optional[str] = None, **kwargs: Any) -> str:
        """Edits/overwrites an existing file with updated content within the workspace sandbox."""
        target_str = path if path is not None else ""
        raw_content = content if content is not None else (text if text is not None else "")
        content_str = sanitize_code_content(raw_content)
        try:
            target_file = self.validate_and_resolve(target_str)
            old_content = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
            action = "NEW" if not target_file.exists() else "MODIFY"

            if not target_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content_str, encoding="utf-8")
                display = self._get_display_path(target_file)
                self.record_change(target_file, old_content, content_str, action)
                msg = f"File '{display}' did not exist; created and wrote content ({len(content_str)} bytes)."
                if self.diary:
                    self.diary.record("EDIT_FILE", display, "SUCCESS", "File created via edit_file")
                return msg

            target_file.write_text(content_str, encoding="utf-8")
            display = self._get_display_path(target_file)
            self.record_change(target_file, old_content, content_str, action)
            msg = f"File '{display}' updated successfully ({len(content_str)} bytes written)."
            if self.diary:
                self.diary.record("EDIT_FILE", display, "SUCCESS", f"Updated file content ({len(content_str)} chars)")
            return msg
        except Exception as e:
            err = f"Error editing file '{target_str}': {str(e)}"
            if self.diary:
                self.diary.record("EDIT_FILE", target_str, "ERROR", str(e))
            return err

    def search_codebase(self, query: str = "", extension: Optional[str] = None, **kwargs: Any) -> str:
        """
        Searches text patterns/query across source files in the workspace.
        Ignores hidden/vendor directories (.git, node_modules, __pycache__, .venv, dist, build).
        """
        if not query or not str(query).strip():
            return "Search Error: Query string cannot be empty."

        q = str(query).strip().lower()
        ext_filter = extension.strip().lower() if extension and str(extension).strip() else None
        if ext_filter and not ext_filter.startswith('.'):
            ext_filter = f".{ext_filter}"

        ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode", "out"}
        matches = []
        max_matches = 50

        try:
            for root, dirs, files in os.walk(str(self.workspace_root)):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

                for f in files:
                    if f.startswith("."):
                        continue
                    file_path = Path(root) / f
                    if ext_filter and file_path.suffix.lower() != ext_filter:
                        continue

                    if file_path.stat().st_size > 1024 * 1024:
                        continue

                    try:
                        rel_display = self._get_display_path(file_path)
                        content_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                        for idx, line in enumerate(content_lines, 1):
                            if q in line.lower():
                                matches.append(f"{rel_display}:{idx}: {line.strip()}")
                                if len(matches) >= max_matches:
                                    break
                    except Exception:
                        pass
                    if len(matches) >= max_matches:
                        break
                if len(matches) >= max_matches:
                    break

            if not matches:
                result = f"No codebase matches found for query '{query}'."
            else:
                result = f"Found {len(matches)} match(es) for '{query}':\n" + "\n".join(matches)
                if len(matches) >= max_matches:
                    result += f"\n... (results capped at {max_matches} matches)"

            if self.diary:
                self.diary.record("SEARCH_CODEBASE", query, "SUCCESS", f"{len(matches)} matches found")
            return result

        except Exception as e:
            err = f"Error searching codebase for '{query}': {str(e)}"
            if self.diary:
                self.diary.record("SEARCH_CODEBASE", query, "ERROR", str(e))
            return err

    def inspect_project_structure(self, max_depth: int = 3, **kwargs: Any) -> str:
        """
        Recursively inspects directory trees up to max_depth and identifies key entry points & manifests.
        """
        ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode", "out"}
        manifests = {"package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "CMakeLists.txt", "Makefile", "Dockerfile"}
        entry_points = {"main.py", "app.py", "server.js", "index.js", "App.tsx", "App.jsx", "main.cpp", "Main.java", "main.go", "main.rs", "index.html"}

        found_manifests = []
        found_entry_points = []
        tree_lines = []

        def walk(dir_path: Path, current_depth: int, prefix: str = ""):
            if current_depth > max_depth:
                return

            try:
                children = sorted(list(dir_path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            except Exception:
                return

            for idx, child in enumerate(children):
                name = child.name
                if name.startswith(".") or name in ignored_dirs:
                    continue

                is_last = (idx == len(children) - 1)
                connector = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")

                if child.is_dir():
                    tree_lines.append(f"{prefix}{connector}{name}/")
                    walk(child, current_depth + 1, next_prefix)
                else:
                    rel_p = self._get_display_path(child)
                    if name in manifests:
                        found_manifests.append(rel_p)
                        tree_lines.append(f"{prefix}{connector}{name} [MANIFEST]")
                    elif name in entry_points:
                        found_entry_points.append(rel_p)
                        tree_lines.append(f"{prefix}{connector}{name} [ENTRY_POINT]")
                    else:
                        tree_lines.append(f"{prefix}{connector}{name}")

        try:
            tree_lines.append(f"Workspace Root ({self._get_display_path(self.workspace_root)}):")
            walk(self.workspace_root, 1)

            summary = [
                "\n".join(tree_lines),
                "\nKey Project Indicators:",
                f"- Manifests Found   : {', '.join(found_manifests) if found_manifests else 'None'}",
                f"- Entry Points Found: {', '.join(found_entry_points) if found_entry_points else 'None'}"
            ]
            res = "\n".join(summary)

            if self.diary:
                self.diary.record("INSPECT_PROJECT_STRUCTURE", str(self.workspace_root), "SUCCESS", "Tree generated")
            return res
        except Exception as e:
            err = f"Error inspecting project structure: {str(e)}"
            if self.diary:
                self.diary.record("INSPECT_PROJECT_STRUCTURE", str(self.workspace_root), "ERROR", str(e))
            return err


# --- Tool Definitions (Ollama / OpenAI Function Calling Schema) ---

FILESYSTEM_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
          "name": "list_files",
          "description": "List files and subdirectories inside a specific directory within the workspace sandbox.",
          "parameters": {
            "type": "object",
            "properties": {
              "directory": {
                "type": "string",
                "description": "The relative directory path inside the workspace to inspect. Use '.' for root workspace directory."
              }
            },
            "required": []
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "read_file",
          "description": "Read the text content of a file located inside the workspace sandbox.",
          "parameters": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "description": "The relative path to the file within the workspace."
              }
            },
            "required": ["path"]
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "create_directory",
          "description": "Create a new directory inside the workspace sandbox.",
          "parameters": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "description": "The relative path of the directory to create inside the workspace."
              }
            },
            "required": ["path"]
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "create_file",
          "description": "Create a new file with specified text content inside the workspace sandbox. Must provide the complete code or text.",
          "parameters": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "description": "The relative path of the file to create inside the workspace."
              },
              "content": {
                "type": "string",
                "description": "The complete text or code content to write into the file. Make sure all code lines and closing quotes/parentheses are fully included."
              }
            },
            "required": ["path", "content"]
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "edit_file",
          "description": "Edit or overwrite an existing file with new content inside the workspace sandbox.",
          "parameters": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "description": "The relative path to the existing file inside the workspace."
              },
              "content": {
                "type": "string",
                "description": "The complete updated text or code content to write to the file."
              }
            },
            "required": ["path", "content"]
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "search_codebase",
          "description": "Search text patterns or function names across all source files in the workspace.",
          "parameters": {
            "type": "object",
            "properties": {
              "query": {
                "type": "string",
                "description": "The search pattern, keyword, symbol, or string to search for."
              },
              "extension": {
                "type": "string",
                "description": "Optional file extension to restrict search (e.g. 'py', 'js', 'cpp', 'java')."
              }
            },
            "required": ["query"]
          }
        }
    },
    {
        "type": "function",
        "function": {
          "name": "inspect_project_structure",
          "description": "Recursively inspect the directory structure, manifests, and key entry points of the workspace.",
          "parameters": {
            "type": "object",
            "properties": {
              "max_depth": {
                "type": "integer",
                "description": "Maximum directory depth to walk (default: 3)."
              }
            },
            "required": []
          }
        }
    }
]

