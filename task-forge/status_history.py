#!/usr/bin/env python3
"""Správa status_history a metrik ve wiki souborech.

Příkazy:
  python3 task-forge/status_history.py append  wiki/stories/US-083.md validated
  python3 task-forge/status_history.py metrics wiki/stories/US-083.md
"""
import sys
import re
import pathlib
from datetime import datetime


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def append(wiki_path: str, status: str) -> None:
    """Přidá {status, ts} záznam do status_history ve frontmatteru."""
    p = pathlib.Path(wiki_path)
    if not p.exists():
        return
    content = p.read_text(encoding="utf-8")
    ts = datetime.now().isoformat(timespec='seconds')
    entry = f"  - status: {status}\n    ts: \"{ts}\""
    if "status_history:" in content:
        content = re.sub(
            r"(status_history:(?:\n  - [^\n]+(?:\n    [^\n]+)*)*)",
            lambda m: m.group(0) + "\n" + entry,
            content, count=1,
        )
    elif re.search(r"^status: ", content, re.MULTILINE):
        content = re.sub(
            r"^(status: [^\n]+)",
            r"\1\nstatus_history:\n" + entry,
            content, flags=re.MULTILINE, count=1,
        )
    else:
        # Starý formát bez YAML frontmatteru (bugy): "- Status: ..."
        content = re.sub(
            r"^(- Status: [^\n]+)",
            r"\1\nstatus_history:\n" + entry,
            content, flags=re.MULTILINE, count=1,
        )
    p.write_text(content, encoding="utf-8")


def update_cycle_time(wiki_path: str) -> None:
    """Přepočítá cycle time ze status_history a zapíše do ## Metriky."""
    p = pathlib.Path(wiki_path)
    if not p.exists():
        return
    content = p.read_text(encoding="utf-8")

    # Parsuj timestamps ze status_history
    timestamps = re.findall(r'ts: "([^"]+)"', content)
    if len(timestamps) < 2:
        return

    try:
        t_start = datetime.fromisoformat(timestamps[0])
        t_end   = datetime.fromisoformat(timestamps[-1])
        duration = _format_duration((t_end - t_start).total_seconds())
    except Exception:
        return

    cycle_line = f"- Cycle time: {duration} ({timestamps[0][:10]} → {timestamps[-1][:10]})"

    if "## Metriky" in content:
        # Přepiš nebo přidej řádek Cycle time
        if "- Cycle time:" in content:
            content = re.sub(r"- Cycle time:.*", cycle_line, content)
        else:
            # Vlož před řádek Celkem
            content = re.sub(
                r"(- Celkem:)",
                cycle_line + "\n\\1",
                content,
            )
    else:
        content += f"\n## Metriky\n{cycle_line}\n- Celkem: $0.0000\n"

    p.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    path = sys.argv[2]
    if cmd == "append" and len(sys.argv) >= 4:
        append(path, sys.argv[3])
    elif cmd == "metrics":
        update_cycle_time(path)
    else:
        # Zpětná kompatibilita: status_history.py <path> <status>
        if len(sys.argv) >= 3 and cmd.endswith(".md"):
            append(sys.argv[1], sys.argv[2])
        else:
            print(__doc__)
