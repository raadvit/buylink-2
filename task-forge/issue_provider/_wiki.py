"""Sdílené wiki/git helpery napříč providery (provider-agnostic)."""

import pathlib
import re
import subprocess
import sys


_DONE_STATUSES = {
    "done",
    "ready_for_testing",
    "ready-for-testing",
    "ready for testing",
    "ready-for-pr",
}


def git_commit_wiki(wiki_path_str: str, root: pathlib.Path, message: str) -> None:
    """Commitne wiki soubor do gitu. Non-fatal — chyba se loguje ale nezastaví pipeline."""
    try:
        subprocess.run(
            ["git", "add", wiki_path_str], cwd=str(root), capture_output=True, timeout=15
        )
        subprocess.run(
            ["git", "commit", "-m", message], cwd=str(root), capture_output=True, timeout=15
        )
    except Exception as e:
        print(f"[issue_provider] Varování: git commit wiki selhal: {e}", file=sys.stderr)


def delete_if_done(wiki_path: pathlib.Path, root: pathlib.Path, body: str) -> None:
    """Pokud je story dokončena: smaže lokální soubor a commitne smazání do gitu."""
    m = re.search(r"- Status:\s*([^\n]+)", body)
    if not (m and m.group(1).strip().lower() in _DONE_STATUSES):
        return
    relative = str(wiki_path.relative_to(root))
    story_id = wiki_path.stem
    try:
        subprocess.run(
            ["git", "rm", "-f", relative],
            cwd=str(root), capture_output=True, timeout=15,
        )
        subprocess.run(
            ["git", "commit", "-m", f"[{story_id}] wiki: story dokončena, smazána z working tree"],
            cwd=str(root), capture_output=True, timeout=15,
        )
    except Exception as e:
        print(f"[issue_provider] Varování: git rm wiki selhal: {e}", file=sys.stderr)


def is_task_forge_epic(epic: str) -> bool:
    return epic.strip().lower().replace("-", " ") == "task forge"


def assets_info(root: pathlib.Path, story_id: str, epic: str) -> tuple[pathlib.Path, str]:
    """Returns (assets_dir, md_link_prefix) based on epic."""
    if is_task_forge_epic(epic or ""):
        return root / "wiki" / "stories-task-forge" / story_id, f"../stories-task-forge/{story_id}"
    return root / "wiki" / "stories" / "assets" / story_id, f"assets/{story_id}"


def save_files_to_assets(files, assets_dir: pathlib.Path) -> list:
    assets_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        filename = getattr(f, "filename", None)
        if not filename:
            continue
        filename = pathlib.Path(filename).name
        filename = re.sub(r"[^\w.\-() ]", "_", filename)
        if not filename or filename.startswith("."):
            continue
        dest = assets_dir / filename
        f.save(str(dest))
        saved.append(filename)
    return saved


def attachments_section(saved: list, md_prefix: str) -> str:
    lines = ["", "", "## Přílohy"]
    for fname in saved:
        lines.append(f"- [{fname}]({md_prefix}/{fname})")
    return "\n".join(lines)


def extract_existing_attachments(content: str) -> str:
    m = re.search(r"(\n\n## Přílohy\n.*)", content, re.DOTALL)
    return m.group(1) if m else ""


def next_story_number(stories_dir: pathlib.Path) -> int:
    highest = 0
    if stories_dir.exists():
        for md_file in stories_dir.glob("US-*.md"):
            match = re.match(r"US-(\d+)\.md$", md_file.name)
            if match:
                num = int(match.group(1))
                if num > highest:
                    highest = num
    return highest + 1
