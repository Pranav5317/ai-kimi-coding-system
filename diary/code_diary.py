import datetime
from pathlib import Path
from typing import Optional


class CodeDiary:
    """
    Manages simple audit logging of workspace actions to CODE_DIARY.md.
    Records events such as directory creation, file creation, file modification, and errors.
    """

    def __init__(self, diary_path: Path):
        self.diary_path = diary_path
        self._ensure_diary_initialized()

    def _ensure_diary_initialized(self) -> None:
        """Initializes the CODE_DIARY.md file with a header if it does not already exist."""
        if not self.diary_path.exists():
            header = (
                "# Code Diary - Workspace Activity Log\n\n"
                "This diary logs all filesystem and workspace actions performed by Agent 5 (Workspace/Runtime Manager).\n\n"
                "| Timestamp (UTC) | Action | Target Path | Status / Details |\n"
                "|---|---|---|---|\n"
            )
            self.diary_path.write_text(header, encoding="utf-8")

    def record(self, action: str, target_path: str, status: str, details: Optional[str] = None) -> None:
        """
        Appends an entry to the code diary.
        
        Args:
            action: E.g., 'CREATE_DIRECTORY', 'CREATE_FILE', 'EDIT_FILE', 'LIST_FILES', 'READ_FILE', 'ERROR'
            target_path: Path involved in the action
            status: 'SUCCESS' or 'FAILED'
            details: Extra details, error messages, or notes
        """
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        clean_details = (details or "").replace("\n", " ").replace("|", "\\|")
        if len(clean_details) > 100:
            clean_details = clean_details[:97] + "..."

        row = f"| {now} | `{action}` | `{target_path}` | **{status}**: {clean_details} |\n"
        
        try:
            with open(self.diary_path, "a", encoding="utf-8") as f:
                f.write(row)
        except Exception as e:
            # Fallback print if diary write fails
            print(f"[Warning] Failed to write to CODE_DIARY.md: {e}")

