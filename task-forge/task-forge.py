import json as _json
import os
import re
import subprocess
import threading
import uuid
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import github_helper
import status_history as _status_history
import store_state
import story_builder
from queue_manager import AnalysisQueue, ImplementQueue

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_config_value(key: str) -> str | None:
    config = _REPO_ROOT / "task-forge" / "config.md"
    try:
        for line in config.read_text(encoding="utf-8").splitlines():
            if key in line and "`" in line:
                m = re.search(r"`([^`]+)`", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _load_github_repo() -> str:
    value = _load_config_value("Main_repo")
    if value and "/" in value:
        return value
    raise RuntimeError("Main_repo není nakonfigurován v task-forge/config.md")


def _load_max_workers() -> int:
    value = _load_config_value("max_workers")
    try:
        return max(1, int(value)) if value else 1
    except (ValueError, TypeError):
        return 1


_GITHUB_REPO = _load_github_repo()
_analysis_queue = AnalysisQueue(max_workers=_load_max_workers())
_implement_queue = ImplementQueue(max_workers=1)

app = Flask(__name__, static_folder=str(_STATIC_DIR))


@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


_REQUIRED_FIELDS = ("name", "epic", "role", "what", "how")


@app.get("/api/config")
def get_config():
    return jsonify({"project_name": _load_config_value("project_name")})


@app.get("/")
def home():
    return send_from_directory(str(_STATIC_DIR), "home.html")


@app.get("/list")
def issue_list():
    return send_from_directory(str(_STATIC_DIR), "list.html")


@app.get("/create-story")
def create_story():
    return send_from_directory(str(_STATIC_DIR), "index.html")


@app.get("/create-story-2")
def create_story_2():
    return send_from_directory(str(_STATIC_DIR), "create-story-2.html")


@app.get("/create-bug")
def create_bug():
    return send_from_directory(str(_STATIC_DIR), "bug.html")


@app.get("/us-<int:issue_number>")
def story_detail(issue_number):
    return send_from_directory(str(_STATIC_DIR), "story-detail.html")


@app.get("/bug-<int:issue_number>")
def bug_detail(issue_number):
    return send_from_directory(str(_STATIC_DIR), "bug-detail.html")


@app.get("/api/issues/<int:issue_number>")
def get_issue(issue_number):
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO,
             "--json", "number,title,labels,updatedAt,body,state"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502
    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip() or "Issue nenalezena."}), 404
    try:
        issue = _json.loads(result.stdout)
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup."}), 502

    labels = [l["name"] for l in issue.get("labels", [])]
    body = issue.get("body") or ""
    epic_match = re.search(r"(?:^- Epic:|^epic:)\s*([^\n]+)", body, re.MULTILINE)
    role_match = re.search(r"(?:^- Role:|^role:)\s*([^\n]+)", body, re.MULTILINE)
    status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
    updated = issue.get("updatedAt", "")

    wiki_path = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    wiki_content = wiki_path.read_text(encoding="utf-8") if wiki_path.exists() else None

    bug_status = status_match.group(1).strip() if status_match else ""
    return jsonify({
        "id": issue["number"],
        "title": issue["title"],
        "labels": labels,
        "state": issue.get("state", "OPEN").upper(),
        "epic": epic_match.group(1).strip() if epic_match else "",
        "role": role_match.group(1).strip() if role_match else "",
        "story_status": bug_status,
        "status": bug_status,
        "date": updated[:10] if updated else "",
        "body": body,
        "wiki": wiki_content,
        "wiki_path": f"wiki/stories/US-{issue_number:03d}.md",
    }), 200


def _remove_from_story_register(issue_number: int) -> None:
    register_path = _REPO_ROOT / ".memory-system" / "V2-shared-truth" / "story_register.md"
    try:
        content = register_path.read_text(encoding="utf-8")
        pattern = rf"^\| US-{issue_number:03d} \|[^\n]*\n?"
        updated = re.sub(pattern, "", content, flags=re.MULTILINE)
        if updated != content:
            register_path.write_text(updated, encoding="utf-8")
    except Exception:
        pass


@app.delete("/api/issues/<int:issue_number>")
def delete_issue(issue_number):
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO, "--json", "labels"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout při načítání issue."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502
    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip() or "Issue nenalezena."}), 404
    try:
        issue_data = _json.loads(result.stdout)
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup."}), 502

    labels = [l["name"] for l in issue_data.get("labels", [])]
    if "user story" in labels:
        wiki_path = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    elif "bug" in labels:
        wiki_path = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    else:
        return jsonify({"error": "Neznámý typ issue (chybí label 'user story' nebo 'bug')."}), 422

    backup = wiki_path.read_text(encoding="utf-8") if wiki_path.exists() else None
    wiki_path.unlink(missing_ok=True)

    try:
        close_result = subprocess.run(
            ["gh", "issue", "close", str(issue_number), "--repo", _GITHUB_REPO],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        if backup is not None:
            wiki_path.write_text(backup, encoding="utf-8")
        return jsonify({"error": "Timeout při uzavírání issue."}), 502
    except FileNotFoundError:
        if backup is not None:
            wiki_path.write_text(backup, encoding="utf-8")
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if close_result.returncode != 0:
        if backup is not None:
            wiki_path.write_text(backup, encoding="utf-8")
        return jsonify({"error": close_result.stderr.strip() or "gh issue close selhal."}), 502

    _remove_from_story_register(issue_number)
    return jsonify({"ok": True}), 200


@app.post("/api/stories/<int:issue_number>/archive")
def archive_story(issue_number):
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO, "--json", "labels"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout při načítání issue."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502
    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip() or "Issue nenalezena."}), 404
    try:
        labels = [l["name"] for l in _json.loads(result.stdout).get("labels", [])]
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup."}), 502
    if "user story" not in labels:
        return jsonify({"error": "Issue není typu 'user story'."}), 404

    # 1. Zavřít GitHub issue
    try:
        close_r = subprocess.run(
            ["gh", "issue", "close", str(issue_number), "--repo", _GITHUB_REPO],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
        if close_r.returncode != 0:
            app.logger.warning("gh issue close #%s selhal: %s", issue_number, close_r.stderr.strip())
    except Exception as e:
        app.logger.warning("gh issue close #%s exception: %s", issue_number, e)

    wiki_src = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    if not wiki_src.exists():
        return jsonify({"ok": True, "skipped": "no_wiki"}), 200

    # 2. git mv + commit
    archived_dir = _REPO_ROOT / "wiki" / "stories-archived"
    archived_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = archived_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
        subprocess.run(["git", "add", str(gitkeep)], cwd=str(_REPO_ROOT))

    wiki_dst = archived_dir / f"US-{issue_number:03d}.md"
    mv = subprocess.run(
        ["git", "mv", str(wiki_src), str(wiki_dst)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    if mv.returncode != 0:
        return jsonify({"error": mv.stderr.strip() or "git mv selhal."}), 502

    assets_src = _REPO_ROOT / "wiki" / "stories" / "assets" / f"US-{issue_number:03d}"
    if assets_src.exists():
        assets_dst = archived_dir / "assets" / f"US-{issue_number:03d}"
        assets_dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "mv", str(assets_src), str(assets_dst)],
            cwd=str(_REPO_ROOT),
        )

    commit = subprocess.run(
        ["git", "commit", "-m", f"[US-{issue_number:03d}] archivace story"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    if commit.returncode != 0:
        subprocess.run(["git", "mv", str(wiki_dst), str(wiki_src)], cwd=str(_REPO_ROOT))
        return jsonify({"error": commit.stderr.strip() or "git commit selhal."}), 502

    return jsonify({"ok": True, "archived_path": f"wiki/stories-archived/US-{issue_number:03d}.md"}), 200


@app.get("/preview")
def preview():
    return send_from_directory(str(_STATIC_DIR), "preview.html")


@app.get("/style-guide/<path:filename>")
def style_guide_static(filename):
    return send_from_directory(str(_REPO_ROOT / "wiki" / "style-guide"), filename)


@app.get("/style-guide-2/<path:filename>")
def style_guide_2_static(filename):
    return send_from_directory(str(_REPO_ROOT / "wiki" / "style-guide-2"), filename)


@app.post("/api/submit-bug")
def submit_bug():
    data, files = _parse_request()
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    _REQUIRED_BUG_FIELDS = ("name", "epic", "role", "what_happened", "expected")
    missing = [f for f in _REQUIRED_BUG_FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Chybí povinná pole: {', '.join(missing)}"}), 422

    body = _build_bug_body(data)
    name = str(data.get("name", "")).strip()
    epic = str(data.get("epic", "")).strip()

    try:
        result = github_helper.create_story(
            title=name,
            body=body,
            epic=epic,
            repo_root=str(_REPO_ROOT),
            files=files,
            labels=["bug"],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    issue_url = result["issue_url"]
    match = re.search(r"/issues/(\d+)$", issue_url)
    issue_number = int(match.group(1)) if match else None

    return jsonify({"issue_url": issue_url, "issue_number": issue_number}), 200


@app.post("/api/submit")
def submit():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    raw_role = data.get("role", "")
    if isinstance(raw_role, list):
        data["role"] = ", ".join(str(r).strip() for r in raw_role if str(r).strip())
    else:
        data["role"] = str(raw_role).strip()

    missing = [f for f in _REQUIRED_FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Chybí povinná pole: {', '.join(missing)}"}), 422

    try:
        existing_issue_number = int(data.get("issue_number", 0)) or None
    except (TypeError, ValueError):
        existing_issue_number = None

    form_data = {
        "name": str(data.get("name", "")).strip(),
        "epic": str(data.get("epic", "")).strip(),
        "role": data["role"],
        "what": str(data.get("what", "")).strip(),
        "how": str(data.get("how", "")).strip(),
        "scope": str(data.get("scope", "")).strip(),
        "deps": str(data.get("deps", "")).strip(),
        "ac": str(data.get("ac", "")).strip(),
        "issue_number": existing_issue_number,
        "wiki_path": str(data.get("wiki_path", "")).strip() or None,
    }

    # Uložit draft do GitHubu PŘED spuštěním validace
    try:
        draft_body = story_builder.build_draft_body(form_data)
        existing_issue = form_data.get("issue_number")
        existing_wiki = form_data.get("wiki_path")
        if existing_issue and existing_wiki:
            saved = github_helper.update_story(
                issue_number=int(existing_issue),
                title=form_data["name"],
                body=draft_body,
                wiki_path=existing_wiki,
                repo_root=str(_REPO_ROOT),
            )
        else:
            saved = github_helper.create_story(
                title=form_data["name"],
                body=draft_body,
                epic=form_data.get("epic", ""),
                repo_root=str(_REPO_ROOT),
                labels=["user story"],
            )
        issue_number = int(saved["issue_url"].split("/")[-1])
        form_data["issue_number"] = issue_number
        form_data["wiki_path"] = saved["wiki_path"]
    except Exception as e:
        return jsonify({"error": f"Nepodařilo se uložit story: {e}"}), 500

    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, form_data)

    t = threading.Thread(
        target=story_builder.run_team_validation,
        args=(session_id, form_data, store_state),
        daemon=True,
    )
    t.start()

    return jsonify({
        "session_id": session_id,
        "issue_number": form_data["issue_number"],
        "issue_url": saved["issue_url"],
        "wiki_path": form_data["wiki_path"],
    }), 202


_READY_FOR_TESTING_STATUSES = {
    "ready_for_testing", "ready-for-testing", "ready for testing",
    "ready-for-pr", "done",
}

@app.get("/api/session")
def get_session():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "Chybí parametr session_id."}), 400

    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404

    # Analyzační session — sleduj stav wiki souboru pro live progress
    if session.get("status") == "analyzing":
        wiki_path = session.get("wiki_path") or session.get("form_data", {}).get("wiki_path")
        if wiki_path:
            full_path = _REPO_ROOT / wiki_path
            try:
                body = full_path.read_text(encoding="utf-8")
                m = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
                wiki_status = m.group(1).strip() if m else "draft"
                phase_map = {
                    "conflict-check": "conflict-check-start",
                    "ready-for-arch": "arch-review-start",
                    "validated":      "done",
                    "blocked":        "blocked",
                }
                new_phase = phase_map.get(wiki_status)
                if new_phase == "done":
                    store_state.update_session(session_id, status="done", validation_phase="done")
                    session = store_state.get_session(session_id)
                elif new_phase == "blocked":
                    store_state.update_session(session_id, status="error", error="Story blokována konfliktem.")
                    session = store_state.get_session(session_id)
                elif new_phase and new_phase != session.get("validation_phase"):
                    store_state.update_session(session_id, validation_phase=new_phase)
                    session = store_state.get_session(session_id)
            except Exception:
                pass

    # Pokud session uvízla na in_development, zkontroluj skutečný stav story ze souboru
    if session.get("status") == "in_development":
        wiki_path = session.get("wiki_path") or session.get("form_data", {}).get("wiki_path")
        if wiki_path:
            full_path = _REPO_ROOT / wiki_path
            try:
                body = full_path.read_text(encoding="utf-8")
                m = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
                if m and m.group(1).strip() in _READY_FOR_TESTING_STATUSES:
                    store_state.update_session(session_id, status="done",
                                               validation_phase="ready_for_testing-start")
                    session = store_state.get_session(session_id)
            except Exception:
                pass

    response = dict(session)
    response["review_summary"] = session.get("review_summary", "")
    response["review_comments"] = session.get("review_comments", [])
    response["messages"] = session.get("messages", [])
    return jsonify(response), 200


@app.post("/api/review-confirm")
def review_confirm():
    return jsonify({"error": "Endpoint nahrazen /api/submit (nový validační pipeline)."}), 410


@app.post("/api/review-comment")
def review_comment():
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id", "")).strip()
    comment = str(data.get("comment", "")).strip()
    if not comment:
        return jsonify({"error": "Komentář nesmí být prázdný."}), 422
    session = store_state.get_session(session_id)
    if not session:
        return jsonify({"error": "Session nenalezena."}), 404
    if not store_state.compare_and_set_status(session_id, "reviewing", "processing"):
        return jsonify({"error": "Session není ve stavu reviewing."}), 409
    comment_id = store_state.add_review_comment(session_id, comment)
    form_data = session["form_data"]
    thread = threading.Thread(
        target=story_builder.run_review_comment,
        args=(session_id, comment_id, comment, form_data, store_state),
        daemon=True,
    )
    thread.start()
    return jsonify({"ok": True})


@app.post("/api/answer")
def answer():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    session_id = str(data.get("session_id", "")).strip()
    question_id = str(data.get("question_id", "")).strip()
    answer_text = str(data.get("answer", "")).strip()

    if not session_id or not question_id:
        return jsonify({"error": "Chybí session_id nebo question_id."}), 422

    if not answer_text:
        return jsonify({"error": "Odpověď nesmí být prázdná."}), 422

    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404

    if session["status"] != "asking_questions":
        return jsonify({"error": f"Session není ve stavu asking_questions (aktuální: {session['status']})."}), 409

    found = store_state.set_answer(session_id, question_id, answer_text)
    if not found:
        return jsonify({"error": "Otázka s daným ID nenalezena."}), 404

    if store_state.all_questions_answered(session_id):
        session = store_state.get_session(session_id)
        if not session.get("validation_phase"):
            store_state.update_session(session_id, status="building")

    return jsonify({"ok": True}), 200


@app.post("/api/session/<session_id>/push")
def session_push(session_id):
    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404
    data = request.get_json(silent=True) or {}
    msg_type = data.get("type", "message")
    text = str(data.get("text", "")).strip()
    agent = str(data.get("agent", "agent"))
    if not text:
        return jsonify({"error": "Chybí text."}), 422
    if msg_type == "question":
        qid = str(data.get("question_id", "")).strip() or str(uuid.uuid4())
        store_state.push_question(session_id, qid, text, agent)
    else:
        store_state.push_message(session_id, text, agent)
    return jsonify({"ok": True}), 200


@app.get("/api/session/<session_id>/answer/<question_id>")
def session_get_answer(session_id, question_id):
    return jsonify(store_state.get_answer(session_id, question_id)), 200


@app.get("/api/sessions/pending")
def sessions_pending():
    return jsonify(store_state.get_pending_question_sessions()), 200


@app.post("/api/confirm")
def confirm():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return jsonify({"error": "Chybí session_id."}), 422

    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404

    if session["status"] != "preview":
        return jsonify({"error": f"Potvrzení je možné pouze ve stavu preview (aktuální: {session['status']})."}), 409

    store_state.update_session(session_id, status="building")
    return jsonify({"ok": True}), 200


@app.post("/api/implement")
def implement():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400

    # Ověř, že issue existuje a je typu "user story"
    try:
        issue_info = story_builder._get_issue_info(issue_number, str(_REPO_ROOT))
    except RuntimeError as e:
        app.logger.error("_get_issue_info failed for issue %s: %s", issue_number, e)
        return jsonify({"error": "Nepodařilo se načíst issue ze GitHub."}), 500

    labels = [lb["name"] for lb in issue_info.get("labels", [])]
    is_story = "user story" in labels
    is_bug   = "bug" in labels
    if not is_story and not is_bug:
        return jsonify({"error": "Issue není typu 'user story' nebo 'bug'."}), 400

    body = issue_info.get("body") or ""
    status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
    story_status = status_match.group(1).strip() if status_match else ""
    allowed_statuses = {"new"} if is_bug else {"ready-for-arch", "validated"}
    if story_status not in allowed_statuses:
        label = "Bug musí být ve stavu new" if is_bug else "Story musí být ve stavu ready-for-arch nebo validated"
        return jsonify({"error": f"{label} (aktuální stav: '{story_status}')."}), 400

    wiki_path = f"wiki/stories/US-{issue_number:03d}.md"
    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, {
        "issue_number": issue_number,
        "wiki_path": wiki_path,
        "name": issue_info.get("title", ""),
    })

    def _update_status():
        story_builder.update_issue_status_in_development(issue_number, wiki_path, str(_REPO_ROOT))
        store_state.update_session(session_id, validation_phase="development-start",
                                   impl_plan_in_analysis=story_builder._get_impl_plan_in_analysis())

    try:
        position = _implement_queue.submit(
            session_id, issue_number,
            story_builder.launch_implement_agent, _update_status, store_state,
        )
    except ValueError as e:
        store_state.update_session(session_id, status="error", error=str(e))
        return jsonify({"error": str(e)}), 409

    try:
        story_builder.update_issue_status_in_development(issue_number, wiki_path, str(_REPO_ROOT))
    except Exception as e:
        app.logger.warning("Nepodařilo se nastavit status in_development: %s", e)

    return jsonify({"success": True, "session_id": session_id, "queue_position": position}), 202


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400

    wiki_path = f"wiki/stories/US-{issue_number:03d}.md"
    full_wiki = _REPO_ROOT / wiki_path
    if not full_wiki.exists():
        return jsonify({"error": f"Wiki soubor {wiki_path} neexistuje."}), 404

    try:
        content = full_wiki.read_text(encoding="utf-8")
        content = re.sub(r"^- Status: .+$", "- Status: draft", content, flags=re.MULTILINE)
        full_wiki.write_text(content, encoding="utf-8")
    except Exception as e:
        app.logger.warning("Nepodařilo se nastavit status draft ve wiki: %s", e)

    try:
        view_result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO, "--json", "body"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
        )
        if view_result.returncode == 0:
            issue_body = _json.loads(view_result.stdout).get("body", "") or ""
            updated_body = re.sub(r"(?m)^(- Status:)\s*.+$", r"\1 draft", issue_body)
            if updated_body == issue_body:
                updated_body = f"- Status: draft\n{issue_body}"
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", updated_body],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
            )
    except Exception as e:
        app.logger.warning("Nepodařilo se nastavit status draft v GitHub issue: %s", e)

    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, {
        "issue_number": issue_number,
        "wiki_path": wiki_path,
        "name": data.get("name", ""),
    })

    position = _analysis_queue.submit(
        session_id, issue_number,
        story_builder.launch_analyze_agent, store_state,
    )

    return jsonify({"session_id": session_id, "issue_number": issue_number, "queue_position": position}), 202


@app.get("/api/done")
def done():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "Chybí parametr session_id."}), 400

    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404

    status = session["status"]

    if status == "done":
        return jsonify({"status": "done", "result": session.get("result")}), 200

    if status == "error":
        return jsonify({"status": "error", "error": session.get("error")}), 500

    return jsonify({"status": status}), 202


def _parse_request():
    content_type = request.content_type or ''
    if 'multipart' in content_type:
        try:
            data = _json.loads(request.form.get('data', '{}'))
        except Exception:
            data = {}
        return data, request.files.getlist('files')
    return request.get_json(silent=True) or {}, []


def _build_draft_body(data: dict, status: str = "draft") -> str:
    today = date.today().isoformat()
    name = str(data.get("name", "")).strip()
    epic = str(data.get("epic", "")).strip()
    role = data.get("role", "")
    why = str(data.get("why", "")).strip()
    what = str(data.get("what", "")).strip()
    how = str(data.get("how", "")).strip()
    scope = str(data.get("scope", "")).strip()
    deps = str(data.get("deps", "")).strip()
    ac = str(data.get("ac", "")).strip()

    lines = [
        f"# {name}",
        "",
        f"- Epic: {epic}",
        f"- Role: {role}",
        f"- Status: {status}",
        "- GitHub: ",
        f"- Vytvořeno: {today}",
        f"- Změněno: {today}",
    ]

    if why:
        lines += ["", "## Why / Business Goal", why]
    if what:
        lines += ["", "## Co se zobrazuje", what]
    if how:
        lines += ["", "## Jak se to chová", how]
    if scope:
        lines += ["", "## Rizikové situace", scope]
    if deps:
        lines += ["", "## Otevřené otázky", deps]
    if ac:
        lines += ["", "## Acceptance criteria", ac]

    return "\n".join(lines)


def _build_bug_body(data: dict, status: str = "new") -> str:
    name = str(data.get("name", "")).strip()
    epic = str(data.get("epic", "")).strip()
    role = str(data.get("role", "")).strip()
    what_happened = str(data.get("what_happened", "")).strip()
    expected = str(data.get("expected", "")).strip()
    steps = str(data.get("steps", "")).strip()
    details = str(data.get("details", "")).strip()

    lines = [
        f"# {name}",
        "",
        f"- Epic: {epic}",
        f"- Role: {role}",
        f"- Status: {status}",
        "",
        "## Co se stalo",
        what_happened,
        "",
        "## Očekávaný výsledek",
        expected,
    ]

    if steps:
        lines += ["", "## Kroky k reprodukci", steps]

    if details:
        lines += ["", "## Další detaily", details]

    return "\n".join(lines)


def _normalize_role(data: dict) -> None:
    raw_role = data.get("role", "")
    if isinstance(raw_role, list):
        data["role"] = ", ".join(str(r).strip() for r in raw_role if str(r).strip())
    else:
        data["role"] = str(raw_role).strip()


@app.post("/api/update-bug")
def update_bug():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    _normalize_role(data)

    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0

    _REQUIRED_BUG_FIELDS = ("name", "epic", "role", "what_happened", "expected")
    missing = [f for f in _REQUIRED_BUG_FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Chybí povinná pole: {', '.join(missing)}"}), 422
    if not issue_number:
        return jsonify({"error": "Chybí issue_number."}), 422

    current_status = "new"
    try:
        view_result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO, "--json", "body"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
        if view_result.returncode == 0:
            current_body = _json.loads(view_result.stdout).get("body", "")
            sm = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", current_body, re.MULTILINE)
            if sm:
                current_status = sm.group(1).strip()
    except Exception:
        pass

    body = _build_bug_body(data, status=current_status)
    name = str(data.get("name", "")).strip()

    try:
        result = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO,
             "--title", name, "--body", body],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip() or "gh issue edit selhal."}), 502

    return jsonify({"issue_url": f"https://github.com/{_GITHUB_REPO}/issues/{issue_number}"}), 200


@app.post("/api/save")
def save():
    data, files = _parse_request()
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    _normalize_role(data)

    if not str(data.get("name", "")).strip():
        return jsonify({"error": "Chybí povinné pole: name"}), 422

    body = _build_draft_body(data, status="new")
    name = str(data.get("name", "")).strip()
    epic = str(data.get("epic", "")).strip()
    issue_type = str(data.get("type", "")).strip()
    labels = {"idea": ["idea"], "story": ["user story"], "bug": ["bug"]}.get(issue_type, [])

    try:
        result = github_helper.create_story(title=name, body=body, epic=epic, repo_root=str(_REPO_ROOT), files=files, labels=labels)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    issue_url = result["issue_url"]
    match = re.search(r"/issues/(\d+)$", issue_url)
    issue_number = int(match.group(1)) if match else None

    return jsonify({
        "issue_url": issue_url,
        "issue_number": issue_number,
        "wiki_path": result["wiki_path"],
    }), 200


@app.post("/api/update")
def update():
    data, files = _parse_request()
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    _normalize_role(data)

    name = str(data.get("name", "")).strip()
    wiki_path = str(data.get("wiki_path", "")).strip()
    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0

    # Validace wiki_path — musí být v wiki/stories/ (ochrana před path traversal)
    from pathlib import PurePosixPath
    try:
        normalized = str(PurePosixPath(wiki_path))
        if not normalized.startswith("wiki/stories/") or ".." in normalized:
            return jsonify({"error": "Neplatná wiki_path."}), 422
    except Exception:
        return jsonify({"error": "Neplatná wiki_path."}), 422

    errors = []
    if not name:
        errors.append("name")
    if not issue_number or issue_number <= 0:
        errors.append("issue_number")
    if not wiki_path:
        errors.append("wiki_path")
    if errors:
        return jsonify({"error": f"Chybí nebo neplatná pole: {', '.join(errors)}"}), 422

    current_status = str(data.get("story_status", "")).strip() or "draft"
    body = _build_draft_body(data, status=current_status)
    epic = str(data.get("epic", "")).strip()

    try:
        result = github_helper.update_story(
            issue_number=issue_number,
            title=name,
            body=body,
            wiki_path=wiki_path,
            repo_root=str(_REPO_ROOT),
            files=files,
            epic=epic,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"issue_url": result["issue_url"], "wiki_path": result["wiki_path"]}), 200


@app.get("/api/issues")
def get_issues():
    state = request.args.get("state", "open")
    if state not in ("open", "closed", "all"):
        state = "open"
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", _GITHUB_REPO, "--state", state,
             "--json", "number,title,labels,updatedAt,body,state", "--limit", "200"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout při načítání issues."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip() or "Chyba při načítání issues."}), 502

    try:
        issues_raw = _json.loads(result.stdout)
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup gh CLI."}), 502
    parsed = []
    for issue in issues_raw:
        labels = [l["name"] for l in issue.get("labels", [])]
        if "idea" in labels:
            issue_type = "idea"
        elif "user story" in labels:
            issue_type = "story"
        elif "bug" in labels:
            issue_type = "bug"
        else:
            issue_type = "other"

        body = issue.get("body") or ""
        epic_match = re.search(r"(?:^- Epic:|^epic:)\s*([^\n]+)", body, re.MULTILINE)
        epic = epic_match.group(1).strip() if epic_match else ""
        status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
        story_status = status_match.group(1).strip() if status_match else ""

        cost_match = re.search(r"^- Celkem: \$([0-9]+\.[0-9]+)", body, re.MULTILINE)
        cost_usd = float(cost_match.group(1)) if cost_match else None

        dur_match = (
            re.search(r"^- Implementace:.*?· čas ([^\n·]+)", body, re.MULTILINE)
            or re.search(r"^- Analýza:.*?· čas ([^\n·]+)", body, re.MULTILINE)
            or re.search(r"^- Cycle time:\s*([^\n(]+?)(?:\s*\(|$)", body, re.MULTILINE)
        )
        duration_str = dur_match.group(1).strip() if dur_match else None

        updated = issue.get("updatedAt", "")
        date_str = updated[:10] if updated else ""

        parsed.append({
            "id": issue["number"],
            "title": issue["title"],
            "type": issue_type,
            "epic": epic,
            "date": date_str,
            "body": body,
            "story_status": story_status,
            "labels": labels,
            "state": issue.get("state", "OPEN").upper(),
            "wiki_path": f"wiki/stories/US-{issue['number']:03d}.md",
            "cost_usd": cost_usd,
            "duration_str": duration_str,
        })

    return jsonify(parsed), 200


@app.post("/api/attach")
def attach_files():
    content_type = request.content_type or ''
    if 'multipart' not in content_type:
        return jsonify({"error": "multipart/form-data required"}), 400
    try:
        data = _json.loads(request.form.get('data', '{}'))
    except Exception:
        data = {}
    issue_number = data.get("issue_number")
    wiki_path = data.get("wiki_path", "")
    if not issue_number or not wiki_path:
        return jsonify({"error": "issue_number and wiki_path required"}), 422
    if not wiki_path.startswith("wiki/stories/") or ".." in wiki_path:
        return jsonify({"error": "invalid wiki_path"}), 422
    try:
        resolved = (_REPO_ROOT / wiki_path).resolve()
        if not str(resolved).startswith(str((_REPO_ROOT / "wiki" / "stories").resolve())):
            return jsonify({"error": "invalid wiki_path"}), 422
    except Exception:
        return jsonify({"error": "invalid wiki_path"}), 422
    files = request.files.getlist('files')
    if not files:
        return jsonify({"ok": True}), 200
    try:
        github_helper.attach_files_to_story(
            issue_number=int(issue_number),
            wiki_path=wiki_path,
            repo_root=str(_REPO_ROOT),
            files=files,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"ok": True}), 200



_BUG_STATUS_TRANSITIONS = {
    "new":               {"in_development", "cancelled"},
    "in_development":    {"ready_for_review", "blocked", "cancelled"},
    "ready_for_review":  {"in_development", "ready_for_testing", "blocked", "cancelled"},
    "ready_for_testing": {"in_development", "done", "blocked", "cancelled"},
    "done":              {"cancelled"},
    "blocked":           {"in_development", "cancelled"},
    "cancelled":         set(),
}

_BUG_VALID_STATUSES = set(_BUG_STATUS_TRANSITIONS.keys())


@app.patch("/api/bugs/<int:issue_number>/status")
def update_bug_status(issue_number):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    new_status = str(data.get("status", "")).strip()
    if not new_status:
        return jsonify({"error": "Chybí pole 'status'."}), 400
    if new_status not in _BUG_VALID_STATUSES:
        return jsonify({"error": f"Neplatný status '{new_status}'."}), 400

    try:
        view_result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO,
             "--json", "number,title,labels,body"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if view_result.returncode != 0:
        return jsonify({"error": view_result.stderr.strip() or "Bug nenalezen."}), 404

    try:
        issue_data = _json.loads(view_result.stdout)
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup."}), 502

    labels = [l["name"] for l in issue_data.get("labels", [])]
    if "bug" not in labels:
        return jsonify({"error": "Issue není typu 'bug'."}), 400

    current_body = issue_data.get("body") or ""
    sm = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", current_body, re.MULTILINE)
    current_status = sm.group(1).strip() if sm else "new"

    allowed = _BUG_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return jsonify({
            "error": f"Přechod '{current_status}' → '{new_status}' není povolen."
        }), 400

    if sm:
        new_body = re.sub(
            r"(?:^(?:- Status:|status:))\s*[^\n]+",
            f"- Status: {new_status}",
            current_body,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        lines = current_body.split("\n")
        insert_idx = 1
        for i, line in enumerate(lines):
            if line.startswith("- Epic:") or line.startswith("- Role:"):
                insert_idx = i + 1
        lines.insert(insert_idx, f"- Status: {new_status}")
        new_body = "\n".join(lines)

    try:
        edit_result = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", new_body],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if edit_result.returncode != 0:
        return jsonify({"error": edit_result.stderr.strip() or "gh issue edit selhal."}), 502

    if new_status == "done":
        try:
            subprocess.run(
                ["gh", "issue", "close", str(issue_number), "--repo", _GITHUB_REPO],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
            )
        except Exception:
            pass

    # Bugy jsou uloženy jako wiki/stories/US-NNN.md (stejný formát jako stories)
    bug_wiki = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    if bug_wiki.exists():
        try:
            wc = bug_wiki.read_text(encoding="utf-8")
            wc = re.sub(r"(?m)^- Status: .+$", f"- Status: {new_status}", wc, count=1)
            wc = re.sub(r"(?m)^status: .+$", f"status: {new_status}", wc, count=1)
            bug_wiki.write_text(wc, encoding="utf-8")
            _status_history.append(str(bug_wiki), new_status)
            _status_history.update_cycle_time(str(bug_wiki))
            # Synchronizuj aktualizovaný obsah (včetně metrik) do GitHub issue body
            updated_wc = bug_wiki.read_text(encoding="utf-8")
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", updated_wc],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
            )
        except Exception as e:
            app.logger.warning("Nepodařilo se aktualizovat bug wiki: %s", e)

    return jsonify({"success": True, "status": new_status}), 200


_STORY_STATUS_TRANSITIONS = {
    "ready_for_testing": {"done"},
    "ready-for-testing": {"done"},
}


@app.patch("/api/issues/<int:issue_number>/status")
def update_story_status(issue_number):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

    new_status = str(data.get("status", "")).strip()
    if not new_status:
        return jsonify({"error": "Chybí pole 'status'."}), 400

    try:
        view_result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO,
             "--json", "number,title,labels,body"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if view_result.returncode != 0:
        return jsonify({"error": view_result.stderr.strip() or "Issue nenalezena."}), 404

    try:
        issue_data = _json.loads(view_result.stdout)
    except Exception:
        return jsonify({"error": "Nepodařilo se zparsovat výstup."}), 502

    labels = [l["name"] for l in issue_data.get("labels", [])]
    if "user story" not in labels:
        return jsonify({"error": "Issue není typu 'user story'."}), 400

    current_body = issue_data.get("body") or ""
    sm = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", current_body, re.MULTILINE)
    current_status = sm.group(1).strip() if sm else ""

    allowed = _STORY_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return jsonify({
            "error": f"Přechod '{current_status}' → '{new_status}' není povolen."
        }), 400

    new_body = re.sub(
        r"(?:^(?:- Status:|status:))\s*[^\n]+",
        f"- Status: {new_status}",
        current_body,
        count=1,
        flags=re.MULTILINE,
    )

    try:
        edit_result = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", new_body],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502

    if edit_result.returncode != 0:
        return jsonify({"error": edit_result.stderr.strip() or "gh issue edit selhal."}), 502

    try:
        subprocess.run(
            ["gh", "issue", "close", str(issue_number), "--repo", _GITHUB_REPO],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except Exception:
        pass

    wiki_path = _REPO_ROOT / f"wiki/stories/US-{issue_number:03d}.md"
    if wiki_path.exists():
        try:
            wiki_content = wiki_path.read_text(encoding="utf-8")
            wiki_content = re.sub(r"(?m)^- Status: .+$", f"- Status: {new_status}", wiki_content, count=1)
            wiki_content = re.sub(r"(?m)^status: .+$", f"status: {new_status}", wiki_content, count=1)
            wiki_path.write_text(wiki_content, encoding="utf-8")
            _status_history.append(str(wiki_path), new_status)
        except Exception as e:
            app.logger.warning("Nepodařilo se aktualizovat wiki: %s", e)

    return jsonify({"success": True, "status": new_status}), 200


if __name__ == "__main__":
    app.run(port=5005, debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true')
