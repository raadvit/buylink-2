"""GitHubProvider — implementace `IssueProvider` přes `gh` CLI.

Logika je převzata 1:1 ze starého `task-forge/github_helper.py` (US-188 refactor).
"""

from __future__ import annotations

import json as _json
import os
import pathlib
import re
import subprocess
import sys

from . import _wiki


def _github_repo() -> str:
    return os.environ.get("GITHUB_REPO", "")


class GitHubProvider:
    """Provider nad `gh` CLI. Aktivní pokud `TARGET_SYSTEM=github` (default)."""

    # ── create / update / attach ────────────────────────────────────────────

    def create_story(
        self,
        title: str,
        body: str,
        epic: str,
        repo_root: str,
        files=None,
        labels: list[str] | None = None,
    ) -> dict:
        root = pathlib.Path(repo_root)
        stories_dir = root / "wiki" / "stories"
        stories_dir.mkdir(parents=True, exist_ok=True)

        repo = _github_repo()
        cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
        for label in labels or []:
            cmd += ["--label", label]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=repo_root, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Příkaz 'gh' nebyl nalezen. Nainstaluj GitHub CLI (https://cli.github.com/)."
            )
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
                raise RuntimeError(
                    f"Nepodařilo se parsovat URL issue z výstupu: {result.stdout.strip()}"
                )

        issue_number_match = re.search(r"/issues/(\d+)$", issue_url)
        issue_number = issue_number_match.group(1) if issue_number_match else None

        story_id = (
            f"US-{int(issue_number):03d}"
            if issue_number
            else f"US-{_wiki.next_story_number(stories_dir):03d}"
        )
        wiki_path = stories_dir / f"{story_id}.md"

        updated_body = body
        if issue_number:
            updated_body = re.sub(
                r"(- GitHub:\s*).*", rf"\g<1>#{issue_number}", body, count=1
            )
            if updated_body == body:
                updated_body = body.replace(
                    "- Status:", f"- GitHub: #{issue_number}\n- Status:", 1
                )
        wiki_path.write_text(updated_body, encoding="utf-8")

        if files:
            assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
            saved = _wiki.save_files_to_assets(files, assets_dir)
            if saved:
                final_body = updated_body + _wiki.attachments_section(saved, md_prefix)
                wiki_path.write_text(final_body, encoding="utf-8")
                if issue_number:
                    edit_result = subprocess.run(
                        [
                            "gh", "issue", "edit", issue_number, "--repo", repo,
                            "--body", final_body,
                        ],
                        capture_output=True, text=True, cwd=repo_root, timeout=30,
                    )
                    if edit_result.returncode != 0:
                        print(
                            f"[github] Varování: nepodařilo se aktualizovat issue body: "
                            f"{edit_result.stderr.strip()}",
                            file=sys.stderr,
                        )

        relative_wiki_path = str(wiki_path.relative_to(root))
        _wiki.git_commit_wiki(relative_wiki_path, root, f"[{story_id}] wiki: vytvoření story")
        _wiki.delete_if_done(wiki_path, root, updated_body)

        issue_number_int = int(issue_number) if issue_number else None
        return {
            "issue_url": issue_url,
            "issue_number": issue_number_int,
            "wiki_path": relative_wiki_path,
        }

    def update_story(
        self,
        issue_number: int,
        title: str,
        body: str,
        wiki_path: str,
        repo_root: str,
        files=None,
        epic: str = "",
    ) -> dict:
        root = pathlib.Path(repo_root)
        full_path = (root / wiki_path).resolve()
        if not full_path.is_relative_to(root.resolve()):
            raise ValueError(f"wiki_path vede mimo repo root: {wiki_path}")
        story_id = pathlib.Path(wiki_path).stem
        repo = _github_repo()

        body_with_issue = re.sub(r"(- GitHub:\s*).*", rf"\g<1>#{issue_number}", body, count=1)
        if body_with_issue == body:
            body_with_issue = body.replace(
                "- Status:", f"- GitHub: #{issue_number}\n- Status:", 1
            )
        body = body_with_issue

        existing_attachments = ""
        if full_path.exists():
            existing_attachments = _wiki.extract_existing_attachments(
                full_path.read_text(encoding="utf-8")
            )

        final_body = body + existing_attachments

        if files:
            assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
            saved = _wiki.save_files_to_assets(files, assets_dir)
            if saved:
                new_section = _wiki.attachments_section(saved, md_prefix)
                if existing_attachments:
                    new_links = "\n".join(
                        f"- [{fname}]({md_prefix}/{fname})" for fname in saved
                    )
                    final_body = body + existing_attachments.rstrip() + "\n" + new_links
                else:
                    final_body = body + new_section

        full_path.write_text(final_body, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    "gh", "issue", "edit", str(issue_number), "--repo", repo,
                    "--title", title, "--body", final_body,
                ],
                capture_output=True, text=True, cwd=repo_root, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Příkaz 'gh' nebyl nalezen. Nainstaluj GitHub CLI (https://cli.github.com/)."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Úprava GitHub issue trvala příliš dlouho (timeout 30s).")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Příkaz 'gh issue edit' selhal: {stderr or 'neznámá chyba'}")

        _wiki.git_commit_wiki(wiki_path, root, f"[{story_id}] wiki: aktualizace")
        _wiki.delete_if_done(full_path, root, final_body)
        return {
            "issue_url": f"https://github.com/{repo}/issues/{issue_number}",
            "issue_number": int(issue_number),
            "wiki_path": wiki_path,
        }

    def attach_files_to_story(
        self,
        issue_number: int,
        wiki_path: str,
        repo_root: str,
        files,
        epic: str = "",
    ) -> None:
        root = pathlib.Path(repo_root)
        full_path = root / wiki_path
        story_id = pathlib.Path(wiki_path).stem
        repo = _github_repo()

        if not full_path.exists():
            raise RuntimeError(f"Wiki soubor nenalezen: {wiki_path}")

        assets_dir, md_prefix = _wiki.assets_info(root, story_id, epic)
        saved = _wiki.save_files_to_assets(files, assets_dir)
        if not saved:
            return

        current_content = full_path.read_text(encoding="utf-8")
        existing_att = _wiki.extract_existing_attachments(current_content)
        new_links = "\n".join(f"- [{fname}]({md_prefix}/{fname})" for fname in saved)

        if existing_att:
            base = current_content[: current_content.rfind(existing_att)]
            final_content = base.rstrip() + existing_att.rstrip() + "\n" + new_links + "\n"
        else:
            final_content = current_content.rstrip() + "\n\n## Přílohy\n" + new_links + "\n"

        full_path.write_text(final_content, encoding="utf-8")

        try:
            subprocess.run(
                [
                    "gh", "issue", "edit", str(issue_number), "--repo", repo,
                    "--body", final_content,
                ],
                capture_output=True, text=True, cwd=repo_root, timeout=30,
            )
        except Exception as e:
            print(
                f"[github] Varování: nepodařilo se aktualizovat issue body: {e}",
                file=sys.stderr,
            )

    # ── read / status (společný kontrakt s JIRA) ────────────────────────────

    def list_issues(self, state: str) -> list[dict]:
        if state not in ("open", "closed", "all"):
            state = "open"
        repo = _github_repo()
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "list", "--repo", repo, "--state", state,
                    "--json", "number,title,labels,updatedAt,body,state", "--limit", "200",
                ],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError("gh CLI nenalezeno.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout při načítání issues.")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Chyba při načítání issues.")
        try:
            return _json.loads(result.stdout)
        except Exception:
            raise RuntimeError("Nepodařilo se zparsovat výstup gh CLI.")

    def get_issue(self, issue_number: int) -> dict:
        repo = _github_repo()
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "view", str(issue_number), "--repo", repo,
                    "--json", "number,title,labels,updatedAt,body,state",
                ],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError("gh CLI nenalezeno.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout.")
        if result.returncode != 0:
            raise FileNotFoundError(result.stderr.strip() or "Issue nenalezena.")
        try:
            return _json.loads(result.stdout)
        except Exception:
            raise RuntimeError("Nepodařilo se zparsovat výstup gh CLI.")

    def update_body(self, issue_number: int, body: str) -> None:
        repo = _github_repo()
        try:
            result = subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", repo, "--body", body],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError("gh CLI nenalezeno.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout při aktualizaci issue body.")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "gh issue edit selhal.")

    def close_issue(self, issue_number: int) -> None:
        repo = _github_repo()
        subprocess.run(
            ["gh", "issue", "close", str(issue_number), "--repo", repo],
            capture_output=True, text=True, timeout=30,
        )

    def transition_status(self, issue_number: int, status: str) -> None:
        # GitHub nemá native transitions — jen close pokud `done`/`cancelled`.
        if status in {"done", "cancelled"}:
            self.close_issue(issue_number)

    def archive_issue(self, issue_number: int) -> None:
        self.close_issue(issue_number)
