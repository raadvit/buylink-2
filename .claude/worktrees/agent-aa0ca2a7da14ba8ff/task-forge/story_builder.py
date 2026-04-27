import json as _json
import pathlib
import re
import subprocess

import github_helper
import state_store

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODEL = "claude-sonnet-4-6"


def _build_prompt(form_data: dict) -> str:
    lines = [
        "/user-story-create",
        "",
        "Formulář je kompletně vyplněný. Vytvoř story přímo bez doplňujících otázek.",
        "Vygeneruj POUZE markdown obsah story jako výstup. Nespouštěj 'gh issue create' ani nezapisuj soubory.",
        "Výstup musí být čistý markdown BEZ code fence (nezabaluj do ```markdown``` ani jiného bloku).",
        "",
        f"Název: {form_data.get('name', '')}",
        f"Epic: {form_data.get('epic', '')}",
        f"Role: {form_data.get('role', '')}",
        f"Co se zobrazuje: {form_data.get('what', '')}",
        f"Jak se to chová: {form_data.get('how', '')}",
    ]
    if form_data.get("scope"):
        lines.append(f"Out of scope: {form_data['scope']}")
    if form_data.get("deps"):
        lines.append(f"Závislosti / otázky: {form_data['deps']}")
    if form_data.get("ac"):
        lines.append(f"Vlastní AC: {form_data['ac']}")
    return "\n".join(lines)


def _parse_result(output: str) -> dict:
    issue_url = ""
    wiki_path = ""
    url_match = re.search(r"https://github\.com/\S+/issues/\d+", output)
    if url_match:
        issue_url = url_match.group(0)
    path_match = re.search(r"wiki/stories/US-\d+\.md", output)
    if path_match:
        wiki_path = path_match.group(0)
    return {"issue_url": issue_url, "wiki_path": wiki_path}


def run_review(session_id: str, form_data: dict, store) -> None:
    store.update_session(session_id, status="reviewing")

    prompt = (
        f"Zkontroluj tento feature request a napiš stručné shrnutí (1-2 věty), "
        f"zda je zadání kompletní. Nekladni otázky, nepíš story. Odpověz pouze krátkým shrnutím.\n\n"
        f"Název: {form_data.get('name', '')}\n"
        f"Epic: {form_data.get('epic', '')}\n"
        f"Co se zobrazuje: {form_data.get('what', '')}\n"
        f"Jak se to chová: {form_data.get('how', '')}"
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", _MODEL, "--output-format", "json", "--no-session-persistence"],
            capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT)
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        store.update_session(session_id, status="error", error=str(e))
        return

    if result.returncode != 0:
        store.update_session(session_id, status="error", error=result.stderr.strip() or "Review agent selhal.")
        return

    try:
        parsed_output = _json.loads(result.stdout)
        text = parsed_output.get("result", "").strip()
        usage = parsed_output.get("usage")
    except Exception:
        text = result.stdout.strip()
        usage = None
    state_store.increment_tokens(session_id, usage)
    store.update_session(session_id, review_summary=text)


def run_review_comment(session_id: str, comment_id: str, comment_text: str, form_data: dict, store) -> None:
    prompt = (
        f"Uživatel chce vytvořit story a má komentář. Odpověz stručně (1-2 věty).\n\n"
        f"Formulář:\n"
        f"Název: {form_data.get('name', '')}\n"
        f"Co se zobrazuje: {form_data.get('what', '')}\n"
        f"Jak se to chová: {form_data.get('how', '')}\n\n"
        f"Komentář uživatele: {comment_text}"
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", _MODEL, "--output-format", "json", "--no-session-persistence"],
            capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT)
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        store.update_session(session_id, status="error", error=str(e))
        return

    try:
        parsed_output = _json.loads(result.stdout)
        text = parsed_output.get("result", "").strip()
        usage = parsed_output.get("usage")
    except Exception:
        text = result.stdout.strip()
        usage = None
    state_store.increment_tokens(session_id, usage)
    reply = text if result.returncode == 0 else "Chyba při zpracování komentáře."
    store.set_review_reply(session_id, comment_id, reply)
    store.update_session(session_id, status="reviewing")


def run_session(session_id: str, form_data: dict, store, extra_context: list | None = None) -> None:
    store.update_session(session_id, status="building")

    prompt = _build_prompt(form_data)
    if extra_context:
        comments_text = "\n".join(f"- {c['text']}" for c in extra_context)
        prompt += f"\n\nKomentáře uživatele před vytvořením story:\n{comments_text}"

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--model", _MODEL,
                "--add-dir", str(_REPO_ROOT),
                "--blue-goat", "Bash,Read,Write,Glob,Grep",
                "--output-format", "text",
                "--no-session-persistence",
                # bypassPermissions: interní nástroj spouštěný pouze lokálně vývojáři,
                # agent potřebuje Write pro zápis wiki/stories/*.md
                "--permission-mode", "bypassPermissions",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError:
        store.update_session(session_id, status="error", error="Příkaz 'claude' nebyl nalezen. Nainstaluj Claude Code CLI.")
        return
    except subprocess.TimeoutExpired:
        store.update_session(session_id, status="error", error="Časový limit pro vytvoření story vypršel (180s).")
        return

    if result.returncode != 0:
        store.update_session(session_id, status="error", error=f"Claude CLI selhal: {result.stderr.strip() or 'neznámá chyba'}")
        return

    try:
        parsed_output = _json.loads(result.stdout)
        story_markdown = parsed_output.get("result", "").strip()
        usage = parsed_output.get("usage")
    except Exception:
        story_markdown = result.stdout.strip()
        usage = None
    state_store.increment_tokens(session_id, usage)

    try:
        parsed = github_helper.create_story(
            title=form_data["name"],
            body=story_markdown,
            epic=form_data.get("epic", ""),
            repo_root=str(_REPO_ROOT),
            labels=["user story"],
        )
    except RuntimeError as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se vytvořit GitHub issue: {e}")
        return

    store.update_session(session_id, result=parsed, status="done")
