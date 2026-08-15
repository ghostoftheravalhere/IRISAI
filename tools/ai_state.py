"""IRIS AI V4 — AI State CLI Helper.

Reads and outputs .ai coordination files for local developer and agent use.
Does not require external APIs, credentials, or network connections.
"""

from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parent.parent / ".ai"


def _read_file(filename: str) -> str:
    filepath = AI_DIR / filename
    if not filepath.exists():
        return f"Error: File '{filepath}' does not exist."
    return filepath.read_text(encoding="utf-8")


def show_status() -> None:
    """Print high-level status summary from handoff and current state."""
    print("=== IRIS AI V4 — Current Handoff ===")
    print(_read_file("handoff.md"))
    print("\n=== Verification Baseline ===")
    print(_read_file("verification.md"))


def show_current() -> None:
    """Print current repository state."""
    print(_read_file("current_state.md"))


def show_handoff() -> None:
    """Print latest completed handoff."""
    print(_read_file("handoff.md"))


def show_next() -> None:
    """Print task queue next task."""
    queue_content = _read_file("task_queue.md")
    if "## NEXT TASK" in queue_content:
        section = queue_content.split("## NEXT TASK")[1].split("## ")[0].strip()
        print("=== NEXT PENDING TASK ===")
        print(section)
    else:
        print(queue_content)


def show_queue() -> None:
    """Print full task queue."""
    print(_read_file("task_queue.md"))


def show_rules() -> None:
    """Print permanent agent rules."""
    print(_read_file("agent_rules.md"))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/ai_state.py [status|current|handoff|next|queue|rules]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "status":
        show_status()
    elif cmd == "current":
        show_current()
    elif cmd == "handoff":
        show_handoff()
    elif cmd == "next":
        show_next()
    elif cmd in ("queue", "task_queue"):
        show_queue()
    elif cmd == "rules":
        show_rules()
    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: status, current, handoff, next, queue, rules")
        sys.exit(1)


if __name__ == "__main__":
    main()
