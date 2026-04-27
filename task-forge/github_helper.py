import pathlib
import re
import subprocess


_GITHUB_REPO = "raadvit/PreciousMetals_backend"

_DONE_STATUSES = {"done", "ready_for_testing", "ready-for-testing", "ready for testing", "ready-for-pr"}


def _git_commit_wiki(wiki_path_str: str, root: pathlib.Path, message: str) -> None:
    """Commitne wiki soubor do gitu. Non-fatal — chyba se loguje ale nezastaví pipeline."""
    try:
        subprocess.run(["git", "add", wiki_path_str], cwd=str(root), capture_output=True, timeout=15)
        subprocess.run(["git", "commit", "-m", message], cwd=str(root), capture_output=True, timeout=15)
    except Exception as e:
        import sys
        print(f"[github_helper] Varování: git commit wiki selhal: {e}", file=sys.stderr)


def _delete_if_done(wiki_path: pathlib.Path, root: pathlib.Path, body: str) -> None:
    """Pokud je story dokončena: smaže lokální soubor a commitne smazání do gitu."""
    m = re.search(r"- Status:\s*([^\n]+)", body)
    if not (m and m.group(1).strip().lower() in _DONE_STATUSES):
        return
    relative = str(wiki_path.relative_to(root))
    story_id = wiki_path.stem
    try:
        subprocess.run(["git", "rm", "-f", relative], cwd=str(root), capture_output=True, timeout=15)
        subprocess.run(["git", "commit", "-m", f"[{story_id}] wiki: story dokončena, smazána z working tree"],
                       cwd=str(root), capture_output=True, timeout=15)
    except Exception as e:
        import sys
        print(f"[github_helper] Varování: git rm wiki selhal: {e}", file=sys.stderr)


def _is_task_forge_epic(epic: str) -> bool:
    return epic.strip().lower().replace('-', ' ') == 'task forge'


def _assets_info(root: pathlib.Path, story_id: str, epic: str) -> tuple[pathlib.Path, str]:
    """Returns (assets_dir, md_link_prefix) based on epic."""
    if _is_task_forge_epic(epic or ''):
        return root / "wiki" / "stories-task-forge" / story_id, f"../stories-task-forge/{story_id}"
    return root / "wiki" / "stories" / "assets" / story_id, f"assets/{story_id}"


def _save_files_to_assets(files, assets_dir: pathlib.Path) -> list:
    assets_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        filename = getattr(f, 'filename', None)
        if not filename:
            continue
        filename = pathlib.Path(filename).name
        filename = re.sub(r'[^\w.\-() ]', '_', filename)
        if not filename or filename.startswith('.'):
            continue
        dest = assets_dir / filename
        f.save(str(dest))
        saved.append(filename)
    return saved


def _attachments_section(saved: list, md_prefix: str) -> str:
    lines = ['', '', '## Přílohy']
    for fname in saved:
        lines.append(f'- [{fname}]({md_prefix}/{fname})')
    return '\n'.join(lines)


def _extract_existing_attachments(content: str) -> str:
    m = re.search(r'(\n\n## Přílohy\n.*)', content, re.DOTALL)
    return m.group(1) if m else ''


def attach_files_to_story(issue_number: int, wiki_path: str, repo_root: str, files, epic: str = '') -> None:
    root = pathlib.Path(repo_root)
    full_path = root / wiki_path
    story_id = pathlib.Path(wiki_path).stem

    if not full_path.exists():
        raise RuntimeError(f"Wiki soubor nenalezen: {wiki_path}")

    assets_dir, md_prefix = _assets_info(root, story_id, epic)
    saved = _save_files_to_assets(files, assets_dir)
    if not saved:
        return

    current_content = full_path.read_text(encoding="utf-8")
    existing_att = _extract_existing_attachments(current_content)
    new_links = "\n".join(f"- [{fname}]({md_prefix}/{fname})" for fname in saved)

    if existing_att:
        base = current_content[:current_content.rfind(existing_att)]
        final_content = base.rstrip() + existing_att.rstrip() + "\n" + new_links + "\n"
    else:
        final_content = current_content.rstrip() + "\n\n## Přílohy\n" + new_links + "\n"

    full_path.write_text(final_content, encoding="utf-8")

    try:
        subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", final_content],
            capture_output=True, text=True, cwd=repo_root, timeout=30,
        )
    except Exception as e:
        import sys
        print(f"[github_helper] Varování: nepodařilo se aktualizovat issue body: {e}", file=sys.stderr)


def _next_story_number(stories_dir: pathlib.Path) -> int:
    highest = 0
    if stories_dir.exists():
        for md_file in stories_dir.glob("US-*.md"):
            match = re.match(r"US-(\d+)\.md$", md_file.name)
            if match:
                num = int(match.group(1))
                if num > highest:
                    highest = num
    return highest + 1


def create_story(title: str, body: str, epic: str, repo_root: str, files=None, labels: list[str] | None = None) -> dict:
    root = pathlib.Path(repo_root)
    stories_dir = root / "wiki" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["gh", "issue", "create", "--repo", _GITHUB_REPO, "--title", title, "--body", body]
    for label in (labels or []):
        cmd += ["--label", label]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("Příkaz 'gh' nebyl nalezen. Nainstaluj GitHub CLI (https://cli.github.com/).")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Vytvoření GitHub issue trvalo příliš dlouho (timeout 30s).")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Příkaz 'gh issue create' selhal: {stderr or 'neznámá chyba'}")

    issue_url = result.stdout.strip()
    if not issue_url.startswith("http"):
        match = re.search(r"https://github\.com/\S+", issue_url)
        if match:
            issue_url = match.group(0)
        else:
            raise RuntimeError(f"Nepodařilo se parsovat URL issue z výstupu: {result.stdout.strip()}")

    issue_number_match = re.search(r"/issues/(\d+)$", issue_url)
    issue_number = issue_number_match.group(1) if issue_number_match else None

    # Název wiki souboru odpovídá GitHub issue číslu (source of truth)
    story_id = f"US-{int(issue_number):03d}" if issue_number else f"US-{_next_story_number(stories_dir):03d}"
    wiki_path = stories_dir / f"{story_id}.md"

    updated_body = body
    if issue_number:
        updated_body = re.sub(r"(- GitHub:\s*).*", rf"\g<1>#{issue_number}", body, count=1)
        if updated_body == body:
            updated_body = body.replace("- Status:", f"- GitHub: #{issue_number}\n- Status:", 1)
    wiki_path.write_text(updated_body, encoding="utf-8")

    if files:
        assets_dir, md_prefix = _assets_info(root, story_id, epic)
        saved = _save_files_to_assets(files, assets_dir)
        if saved:
            final_body = updated_body + _attachments_section(saved, md_prefix)
            wiki_path.write_text(final_body, encoding="utf-8")
            if issue_number:
                edit_result = subprocess.run(
                    ["gh", "issue", "edit", issue_number, "--repo", _GITHUB_REPO, "--body", final_body],
                    capture_output=True, text=True, cwd=repo_root, timeout=30,
                )
                if edit_result.returncode != 0:
                    print(f"[github_helper] Varování: nepodařilo se aktualizovat issue body: {edit_result.stderr.strip()}")

    relative_wiki_path = str(wiki_path.relative_to(root))
    _git_commit_wiki(relative_wiki_path, root, f"[{story_id}] wiki: vytvoření story")
    _delete_if_done(wiki_path, root, updated_body)
    return {"issue_url": issue_url, "wiki_path": relative_wiki_path}


def update_story(issue_number: int, title: str, body: str, wiki_path: str, repo_root: str, files=None, epic: str = '') -> dict:
    root = pathlib.Path(repo_root)
    full_path = (root / wiki_path).resolve()
    if not full_path.is_relative_to(root.resolve()):
        raise ValueError(f"wiki_path vede mimo repo root: {wiki_path}")
    story_id = pathlib.Path(wiki_path).stem

    # Zajistit že číslo issue zůstane v body (build_draft_body ho generuje prázdné)
    body_with_issue = re.sub(r"(- GitHub:\s*).*", rf"\g<1>#{issue_number}", body, count=1)
    if body_with_issue == body:
        body_with_issue = body.replace("- Status:", f"- GitHub: #{issue_number}\n- Status:", 1)
    body = body_with_issue

    existing_attachments = ''
    if full_path.exists():
        existing_attachments = _extract_existing_attachments(full_path.read_text(encoding='utf-8'))

    final_body = body + existing_attachments

    if files:
        assets_dir, md_prefix = _assets_info(root, story_id, epic)
        saved = _save_files_to_assets(files, assets_dir)
        if saved:
            new_section = _attachments_section(saved, md_prefix)
            if existing_attachments:
                new_links = '\n'.join(f'- [{fname}]({md_prefix}/{fname})' for fname in saved)
                final_body = body + existing_attachments.rstrip() + '\n' + new_links
            else:
                final_body = body + new_section

    full_path.write_text(final_body, encoding="utf-8")

    try:
        result = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--title", title, "--body", final_body],
            capture_output=True, text=True, cwd=repo_root, timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("Příkaz 'gh' nebyl nalezen. Nainstaluj GitHub CLI (https://cli.github.com/).")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Úprava GitHub issue trvala příliš dlouho (timeout 30s).")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Příkaz 'gh issue edit' selhal: {stderr or 'neznámá chyba'}")

    story_id = pathlib.Path(wiki_path).stem
    _git_commit_wiki(wiki_path, root, f"[{story_id}] wiki: aktualizace")
    _delete_if_done(full_path, root, final_body)
    return {
        "issue_url": f"https://github.com/{_GITHUB_REPO}/issues/{issue_number}",
        "wiki_path": wiki_path,
    }
