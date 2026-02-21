"""Task Linking Engine — maps messages to tasks to prevent duplicate creation."""

from typing import Optional, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class MessageTaskLink:
    """A message-to-task link record."""
    message_id: str
    task_id: str
    linked_at: datetime
    workspace_id: str
    project_id: Optional[str] = None


class TaskLinkingEngine:
    """Bidirectional message↔task mapping with optional persistence."""

    def __init__(self, persistence_file: Optional[str] = None):
        """persistence_file: path for JSON persistence; None = memory-only."""
        self.message_to_task: Dict[str, str] = {}
        self.task_to_messages: Dict[str, Set[str]] = {}
        self.links: Dict[str, MessageTaskLink] = {}
        self.persistence_file = persistence_file

        if self.persistence_file and os.path.exists(self.persistence_file):
            self._load_from_persistence()
    
    def link_message_to_task(
        self,
        message_id: str,
        task_id: str,
        workspace_id: str,
        project_id: Optional[str] = None
    ) -> None:
        """Link a message to a task (bidirectional)."""
        self.message_to_task[message_id] = task_id
        if task_id not in self.task_to_messages:
            self.task_to_messages[task_id] = set()
        self.task_to_messages[task_id].add(message_id)
        self.links[message_id] = MessageTaskLink(
            message_id=message_id,
            task_id=task_id,
            linked_at=datetime.now(),
            workspace_id=workspace_id,
            project_id=project_id
        )
        if self.persistence_file:
            self._save_to_persistence()
    
    def get_task_by_message(self, message_id: str) -> Optional[str]:
        """Return task ID linked to message, or None."""
        return self.message_to_task.get(message_id)

    def get_messages_by_task(self, task_id: str) -> Set[str]:
        """Return all message IDs linked to a task."""
        return self.task_to_messages.get(task_id, set()).copy()

    def unlink_message(self, message_id: str) -> bool:
        """Remove message-task link. Returns True if removed."""
        if message_id not in self.message_to_task:
            return False
        task_id = self.message_to_task[message_id]
        del self.message_to_task[message_id]
        if task_id in self.task_to_messages:
            self.task_to_messages[task_id].discard(message_id)
            if not self.task_to_messages[task_id]:
                del self.task_to_messages[task_id]
        if message_id in self.links:
            del self.links[message_id]
        if self.persistence_file:
            self._save_to_persistence()
        return True

    def get_link_details(self, message_id: str) -> Optional[MessageTaskLink]:
        """Return link details for a message."""
        return self.links.get(message_id)

    def clear_workspace_links(self, workspace_id: str, project_id: Optional[str] = None) -> int:
        """Remove all links for a workspace/project. Returns count removed."""
        to_remove = [
            mid for mid, link in self.links.items()
            if link.workspace_id == workspace_id and (
                project_id is None or link.project_id == project_id
            )
        ]
        for mid in to_remove:
            self.unlink_message(mid)
        return len(to_remove)

    def get_stats(self) -> Dict[str, int]:
        """Return link counts for monitoring."""
        return {
            "total_message_links": len(self.message_to_task),
            "total_tasks_with_links": len(self.task_to_messages),
            "total_link_records": len(self.links)
        }
    
    def _save_to_persistence(self) -> None:
        """Save state to JSON file."""
        try:
            data = {
                "message_to_task": self.message_to_task,
                "task_to_messages": {k: list(v) for k, v in self.task_to_messages.items()},
                "links": {
                    k: {
                        "message_id": v.message_id,
                        "task_id": v.task_id,
                        "linked_at": v.linked_at.isoformat(),
                        "workspace_id": v.workspace_id,
                        "project_id": v.project_id
                    }
                    for k, v in self.links.items()
                }
            }
            os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save links: {e}")

    def _load_from_persistence(self) -> None:
        """Load state from JSON file."""
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            self.message_to_task = data.get("message_to_task", {})
            self.task_to_messages = {k: set(v) for k, v in data.get("task_to_messages", {}).items()}
            for message_id, ld in data.get("links", {}).items():
                self.links[message_id] = MessageTaskLink(
                    message_id=ld["message_id"],
                    task_id=ld["task_id"],
                    linked_at=datetime.fromisoformat(ld["linked_at"]),
                    workspace_id=ld["workspace_id"],
                    project_id=ld.get("project_id")
                )
        except Exception as e:
            print(f"Warning: Failed to load links: {e}")
            self.__init__(self.persistence_file)


# Module-level convenience functions using a default engine instance
default_task_linker = TaskLinkingEngine()


def link_message_to_task(
    message_id: str,
    task_id: str,
    workspace_id: str = "default",
    project_id: Optional[str] = None
) -> None:
    """Link a message to a task using the default engine."""
    default_task_linker.link_message_to_task(message_id, task_id, workspace_id, project_id)


def get_task_by_message(message_id: str) -> Optional[str]:
    """Return the task ID linked to a message, or None."""
    return default_task_linker.get_task_by_message(message_id)