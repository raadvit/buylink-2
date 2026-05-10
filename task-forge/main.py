import json as _json
import os
import re
import subprocess
import threading
import uuid
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _find_dotenv() -> Path | None:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        current = current.parent
    return None


def _load_dotenv() -> None:
    env_path = _find_dotenv()
    if env_path is None:
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k and k not in os.environ:
                os.environ[k] = v.strip()
    except Exception:
        pass
    if "REPO_ROOT" not in os.environ:
        os.environ["REPO_ROOT"] = str(env_path.parent)


_load_dotenv()
_REPO_ROOT = Path(os.environ.get("REPO_ROOT", str(Path(__file__).resolve().parents[1])))
_MEMORY_SYSTEM_DIR = _REPO_ROOT / os.environ.get("MEMORY_SYSTEM_DIR", ".memory-system")
_WIKI_ROOT = os.environ.get("WIKI_DIR", "wiki")
_WIKI_DIR = f"{_WIKI_ROOT}/stories"
_WIKI_ARCHIVED_DIR = f"{_WIKI_ROOT}/stories-archived"

import status_history as _status_history
import store_state
import story_builder
import wiki_chat
from issue_provider import get_provider
from issue_provider import _wiki as _wiki_helpers
from queue_manager import AnalysisQueue, ImplementQueue


_GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
_analysis_queue = AnalysisQueue(max_workers=max(1, int(os.environ.get("MAX_WORKERS", "1"))))
_implement_queue = ImplementQueue(max_workers=1)
_poller_event = threading.Event()

app = Flask(__name__, static_folder=str(_STATIC_DIR))


@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def _ensure_queue_labels() -> None:
    for name, color, desc in [
        ("queue-analysis", "fbca04", "Čeká na analýzu"),
        ("queue-development", "0075ca", "Čeká na implementaci"),
    ]:
        subprocess.run(
            ["gh", "label", "create", name, "--color", color, "--description", desc,
             "--repo", _GITHUB_REPO, "--force"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
        )


def _enqueue_analysis(issue_number: int, title: str) -> tuple[str, int]:
    wiki_path = f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    full_wiki = _REPO_ROOT / wiki_path
    if not full_wiki.exists():
        raise FileNotFoundError(f"Wiki soubor {wiki_path} neexistuje.")
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
    store_state.create_session(session_id, {"issue_number": issue_number, "wiki_path": wiki_path, "name": title})

    def _pre_start():
        try:
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO,
                 "--remove-label", "queue-analysis"],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
            )
        except Exception as e:
            app.logger.warning("Nepodařilo se odebrat label queue-analysis z #%d: %s", issue_number, e)

    position = _analysis_queue.submit(session_id, issue_number, story_builder.launch_analyze_agent, store_state, pre_start_fn=_pre_start)
    return session_id, position


def _enqueue_development(issue_number: int) -> tuple[str, int]:
    wiki_path = f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    full_wiki = _REPO_ROOT / wiki_path
    if not full_wiki.exists():
        try:
            issue_info = story_builder._get_issue_info(issue_number, str(_REPO_ROOT))
            full_wiki.parent.mkdir(parents=True, exist_ok=True)
            full_wiki.write_text(issue_info.get("body", ""), encoding="utf-8")
        except Exception as e:
            app.logger.warning("Nepodařilo se vytvořit wiki soubor pro #%d: %s", issue_number, e)
    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, {"issue_number": issue_number, "wiki_path": wiki_path, "name": ""})

    def _update_status():
        try:
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO,
                 "--remove-label", "queue-development"],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
            )
        except Exception as e:
            app.logger.warning("Nepodařilo se odebrat label queue-development z #%d: %s", issue_number, e)
        story_builder.update_issue_status_in_development(issue_number, wiki_path, str(_REPO_ROOT))
        store_state.update_session(session_id, validation_phase="development-start",
                                   impl_plan_in_analysis=story_builder._get_impl_plan_in_analysis())

    position = _implement_queue.submit(
        session_id, issue_number,
        story_builder.launch_implement_agent, _update_status, store_state,
    )
    return session_id, position


def _process_queue() -> None:
    for label, queue_type in (("queue-analysis", "analysis"), ("queue-development", "development")):
        try:
            r = subprocess.run(
                ["gh", "issue", "list", "--repo", _GITHUB_REPO, "--label", label,
                 "--json", "number,title", "--limit", "20", "--state", "open"],
                capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=20,
            )
            if r.returncode != 0:
                continue
            issues = _json.loads(r.stdout or "[]")
        except Exception as e:
            app.logger.warning("Poller: chyba při čtení fronty %s: %s", label, e)
            continue
        active_issues = {
            s.get("form_data", {}).get("issue_number")
            for s in store_state.all_sessions().values()
            if s.get("status") not in ("done", "error")
        }
        for issue in issues:
            issue_number = issue.get("number")
            if not issue_number or issue_number in active_issues:
                continue
            try:
                if queue_type == "analysis":
                    _enqueue_analysis(issue_number, issue.get("title", ""))
                else:
                    _enqueue_development(issue_number)
            except Exception as e:
                app.logger.warning("Poller: nepodařilo se spustit agenta pro #%s: %s", issue_number, e)


def _poller_loop() -> None:
    _ensure_queue_labels()
    while True:
        _poller_event.wait(timeout=60)
        _poller_event.clear()
        try:
            _process_queue()
        except Exception as e:
            app.logger.error("Poller: neočekávaná chyba: %s", e)


_REQUIRED_FIELDS = ("name", "epic", "role", "what", "how")


@app.get("/api/config")
def get_config():
    return jsonify({"project_name": os.environ.get("PROJECT_NAME", "")})


@app.get("/wiki/<path:filename>")
def serve_wiki(filename):
    from flask import abort
    base = (_REPO_ROOT / "wiki").resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base) + os.sep):
        abort(403)
    return send_from_directory(str(base), filename)


@app.get("/")
def home():
    return send_from_directory(str(_STATIC_DIR), "home.html")


@app.get("/list")
def issue_list():
    return send_from_directory(str(_STATIC_DIR), "list.html")


@app.get("/login")
def login():
    return send_from_directory(str(_STATIC_DIR), "login.html")


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


@app.errorhandler(404)
def not_found(e):
    return send_from_directory(str(_STATIC_DIR), "404.html"), 404


_STATUS_ORDER = {
    "draft": 0, "new": 1, "clarify": 2, "needs-clarify": 2, "needs_clarify": 2,
    "ready-for-arch": 3, "validated": 4, "dev-plan": 5,
    "in-development": 6, "in_development": 6,
    "ready_for_testing": 7, "ready-for-testing": 7, "ready for testing": 7,
    "done": 8, "cancelled": 8, "blocked": 3,
}


def _pick_advanced_status(a: str, b: str) -> str:
    """Vrátí pokročilejší ze dvou statusů podle definovaného pořadí."""
    return a if _STATUS_ORDER.get(a, -1) >= _STATUS_ORDER.get(b, -1) else b


@app.get("/api/issues/<int:issue_number>")
def get_issue(issue_number):
    try:
        issue = get_provider().get_issue(issue_number)
    except FileNotFoundError as e:
        return jsonify({"error": str(e) or "Issue nenalezena."}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    labels = [l["name"] for l in issue.get("labels", [])]
    body = issue.get("body") or ""
    epic_match = re.search(r"(?:^- Epic:|^epic:)\s*([^\n]+)", body, re.MULTILINE)
    role_match = re.search(r"(?:^- Role:|^role:)\s*([^\n]+)", body, re.MULTILINE)
    status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
    updated = issue.get("updatedAt", "")

    wiki_path = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    wiki_content = wiki_path.read_text(encoding="utf-8") if wiki_path.exists() else None

    gh_status = status_match.group(1).strip() if status_match else ""
    wiki_status = ""
    if wiki_content:
        wiki_status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", wiki_content, re.MULTILINE)
        if wiki_status_match:
            wiki_status = wiki_status_match.group(1).strip()
    bug_status = _pick_advanced_status(gh_status, wiki_status)

    resp = jsonify({
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
        "wiki_path": f"{_WIKI_DIR}/US-{issue_number:03d}.md",
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp, 200


def _cleanup_memory_for_story(issue_number: int) -> None:
    """Odstraní story z story_register a vyčistí exkluzivní domain sekce."""
    register_path = _MEMORY_SYSTEM_DIR / "V2-shared-truth/story_register.md"
    domain_path = _MEMORY_SYSTEM_DIR / "V2-shared-truth/domain.md"
    try:
        content = register_path.read_text(encoding="utf-8")
        story_id = f"US-{issue_number:03d}"
        story_pattern = rf"^\| {re.escape(story_id)} \|[^\n]*\n?"

        # Extrahuj writes sekce mazané story
        writes_sections: set = set()
        row_match = re.search(story_pattern, content, re.MULTILINE)
        if row_match:
            cols = [c.strip() for c in row_match.group(0).split("|")]
            # | id | title | epic | status | reads | writes | depends_on | ...
            if len(cols) > 6 and cols[6] and cols[6] != "none":
                for s in cols[6].split(","):
                    s = s.strip()
                    if s.startswith("domain:"):
                        writes_sections.add(s[len("domain:"):])

        # Odstraň řádek z registru
        updated = re.sub(story_pattern, "", content, flags=re.MULTILINE)
        if updated != content:
            register_path.write_text(updated, encoding="utf-8")

        if not writes_sections:
            return

        # Zjisti sekce sdílené s ostatními stories
        shared: set = set()
        for m in re.finditer(r"^\|[^\n]+\n?", updated, re.MULTILINE):
            row = m.group(0)
            if "|---" in row or row.strip().startswith("| id "):
                continue
            cols = [c.strip() for c in row.split("|")]
            if len(cols) > 6 and cols[6] and cols[6] != "none":
                for s in cols[6].split(","):
                    s = s.strip()
                    if s.startswith("domain:"):
                        shared.add(s[len("domain:"):])

        # Odstraň výhradně mazané sekce z domain.md
        exclusive = writes_sections - shared
        if exclusive and domain_path.exists():
            domain = domain_path.read_text(encoding="utf-8")
            for sec in exclusive:
                domain = re.sub(
                    rf"<!-- SECTION: {re.escape(sec)} -->.*?<!-- /SECTION: {re.escape(sec)} -->\n?",
                    "",
                    domain,
                    flags=re.DOTALL,
                )
            domain_path.write_text(domain, encoding="utf-8")
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
        wiki_path = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    elif "bug" in labels:
        wiki_path = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
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

    _cleanup_memory_for_story(issue_number)
    return jsonify({"ok": True}), 200


@app.post("/api/stories/<int:issue_number>/archive")
def archive_story(issue_number):
    provider = get_provider()

    try:
        issue = provider.get_issue(issue_number)
    except FileNotFoundError as e:
        return jsonify({"error": str(e) or "Issue nenalezena."}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    labels = [l["name"] for l in issue.get("labels", [])]
    if "user story" not in labels:
        return jsonify({"error": "Issue není typu 'user story'."}), 400

    # 1. Archivovat issue v backing systému (GitHub: close, JIRA: noop dle workflow).
    try:
        provider.archive_issue(issue_number)
    except Exception as e:
        app.logger.warning("provider.archive_issue #%s selhal: %s", issue_number, e)

    wiki_src = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    if not wiki_src.exists():
        return jsonify({"ok": True, "skipped": "no_wiki"}), 200

    # 2. git mv + commit
    archived_dir = _REPO_ROOT / _WIKI_ARCHIVED_DIR
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

    assets_src = _REPO_ROOT / _WIKI_DIR / "assets" / f"US-{issue_number:03d}"
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

    return jsonify({"ok": True, "archived_path": f"{_WIKI_ARCHIVED_DIR}/US-{issue_number:03d}.md"}), 200


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
        result = get_provider().create_story(
            title=name,
            body=body,
            epic=epic,
            repo_root=str(_REPO_ROOT),
            files=files,
            labels=["bug"],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    issue_url = result["issue_url"]
    issue_number = result.get("issue_number")
    if issue_number is None:
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
        provider = get_provider()
        if existing_issue and existing_wiki:
            saved = provider.update_story(
                issue_number=int(existing_issue),
                title=form_data["name"],
                body=draft_body,
                wiki_path=existing_wiki,
                repo_root=str(_REPO_ROOT),
            )
        else:
            saved = provider.create_story(
                title=form_data["name"],
                body=draft_body,
                epic=form_data.get("epic", ""),
                repo_root=str(_REPO_ROOT),
                labels=["user story"],
            )
        issue_number = saved.get("issue_number")
        if issue_number is None:
            tail = saved["issue_url"].rsplit("/", 1)[-1]
            m = re.search(r"(\d+)$", tail)
            issue_number = int(m.group(1)) if m else 0
        form_data["issue_number"] = int(issue_number)
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
    if session.get("status") in ("analyzing", "asking_questions", "reviewing"):
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

    _sess = store_state.get_session(session_id)
    _wiki = (_sess or {}).get("wiki_path") or (_sess or {}).get("form_data", {}).get("wiki_path")
    if found and _wiki:
        wiki_chat.append_chat_message(_wiki, 'user', 'Uživatel', answer_text)

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
    _wiki = session.get("wiki_path") or session.get("form_data", {}).get("wiki_path")
    if _wiki:
        wiki_chat.append_chat_message(_wiki, 'agent', agent, text)
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


@app.post("/api/clarify")
def clarify():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400
    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400

    wiki_path = f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    full_wiki = _REPO_ROOT / wiki_path
    if not full_wiki.exists():
        return jsonify({"error": f"Wiki soubor {wiki_path} neexistuje."}), 404

    try:
        content = full_wiki.read_text(encoding="utf-8")
        content = re.sub(r"^- Status: .+$", "- Status: clarify", content, flags=re.MULTILINE)
        full_wiki.write_text(content, encoding="utf-8")
    except Exception as e:
        app.logger.warning("Nepodařilo se nastavit status clarify: %s", e)

    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, {
        "issue_number": issue_number,
        "wiki_path": wiki_path,
        "name": data.get("name", ""),
    })

    position = _analysis_queue.submit(
        session_id, issue_number,
        story_builder.launch_clarify_agent, store_state,
    )

    return jsonify({"session_id": session_id, "issue_number": issue_number, "queue_position": position}), 202


@app.post("/api/clarify/answers")
def clarify_answers():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400
    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400

    answers = data.get("answers", [])
    if not isinstance(answers, list):
        return jsonify({"error": "Pole answers musí být seznam."}), 400

    full_wiki = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    if not full_wiki.exists():
        return jsonify({"error": "Wiki soubor neexistuje."}), 404

    try:
        content = full_wiki.read_text(encoding="utf-8")
        for item in answers:
            idx = item.get("index")
            answer = (item.get("answer") or "").strip()
            if idx and answer:
                content = re.sub(
                    rf"^({re.escape(str(idx))}\. .+?)(\s*→.*)?$",
                    lambda m, a=answer: m.group(1) + f" → {a}",
                    content,
                    flags=re.MULTILINE,
                )
        full_wiki.write_text(content, encoding="utf-8")
    except Exception as e:
        app.logger.warning("Nepodařilo se zapsat odpovědi do wiki: %s", e)
        return jsonify({"error": str(e)}), 500

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
    allowed_statuses = {"new"} if is_bug else {"ready-for-arch", "validated", "dev-plan"}
    if story_status not in allowed_statuses:
        lbl = "Bug musí být ve stavu new" if is_bug else "Story musí být ve stavu dev-plan nebo validated"
        return jsonify({"error": f"{lbl} (aktuální stav: '{story_status}')."}), 400
    try:
        session_id, position = _enqueue_development(issue_number)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
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
    try:
        session_id, position = _enqueue_analysis(issue_number, data.get("name", ""))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
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


@app.post("/api/queue")
def enqueue():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400
    try:
        issue_number = int(data.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400
    queue_type = str(data.get("type", "")).strip()
    if queue_type not in ("analysis", "development"):
        return jsonify({"error": "Neplatný typ (očekáváno 'analysis' nebo 'development')."}), 400
    label = "queue-analysis" if queue_type == "analysis" else "queue-development"
    try:
        issue_info = story_builder._get_issue_info(issue_number, str(_REPO_ROOT))
    except RuntimeError:
        return jsonify({"error": "Nepodařilo se načíst issue ze GitHub."}), 500
    issue_labels = [lb["name"] for lb in issue_info.get("labels", [])]
    is_story = "user story" in issue_labels
    is_bug   = "bug" in issue_labels
    if queue_type == "development":
        if not is_story and not is_bug:
            return jsonify({"error": "Issue není typu 'user story' nebo 'bug'."}), 400
        body = issue_info.get("body") or ""
        status_match = re.search(r"(?:^- Status:|^status:)\s*([^\n]+)", body, re.MULTILINE)
        story_status = status_match.group(1).strip() if status_match else ""
        allowed_statuses = {"new"} if is_bug else {"ready-for-arch", "validated", "dev-plan"}
        if story_status not in allowed_statuses:
            lbl_err = "Bug musí být ve stavu new" if is_bug else "Story musí být ve stavu dev-plan nebo validated"
            return jsonify({"error": f"{lbl_err} (aktuální stav: '{story_status}')."}), 400
    else:
        wiki_path = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
        if not wiki_path.exists():
            return jsonify({"error": "Wiki soubor neexistuje."}), 404
    try:
        r = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--add-label", label],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=15,
        )
        if r.returncode != 0:
            return jsonify({"error": "Nepodařilo se přidat label do issue."}), 502
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout."}), 502
    except FileNotFoundError:
        return jsonify({"error": "gh CLI nenalezeno."}), 502
    _poller_event.set()
    return jsonify({"ok": True}), 200


@app.get("/api/session/by-issue")
def session_by_issue():
    try:
        issue_number = int(request.args.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number:
        return jsonify({"error": "Chybí parametr issue_number."}), 400
    result = store_state.get_session_by_issue(issue_number)
    if result is None:
        return jsonify({"error": "Žádná aktivní session."}), 404
    return jsonify(result), 200


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
    figma_url = str(data.get("figma_url", "")).strip()
    figma_image_path = str(data.get("figma_image_path", "")).strip()

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
    if figma_url:
        lines.append(f"- Figma: {figma_url}")
    if figma_image_path:
        lines.append(f"- Figma_image: {figma_image_path}")

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


def _insert_figma_image_path(wiki_path: str, issue_number: int | None, saved_path: str) -> None:
    """Vloží nebo aktualizuje řádek '- Figma_image:' v existujícím wiki souboru."""
    wiki_full = _REPO_ROOT / wiki_path
    try:
        current = wiki_full.read_text(encoding="utf-8")
        if re.search(r"^- Figma_image:", current, re.MULTILINE):
            new_wiki = re.sub(
                r"^- Figma_image:[^\n]*$", f"- Figma_image: {saved_path}",
                current, flags=re.MULTILINE, count=1,
            )
        elif re.search(r"^- Figma:", current, re.MULTILINE):
            new_wiki = re.sub(
                r"^(- Figma:[^\n]*)$", rf"\1\n- Figma_image: {saved_path}",
                current, flags=re.MULTILINE, count=1,
            )
        else:
            # Vlož před první ## sekci nebo na konec metadat
            new_wiki = re.sub(r"(\n\n##)", f"\n- Figma_image: {saved_path}\\1", current, count=1)
            if new_wiki == current:
                new_wiki = current.rstrip() + f"\n- Figma_image: {saved_path}\n"
        wiki_full.write_text(new_wiki, encoding="utf-8")
        if issue_number:
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO, "--body", new_wiki],
                capture_output=True, cwd=str(_REPO_ROOT), timeout=15,
            )
    except Exception as e:
        app.logger.warning("Nepodařilo se zapsat figma_image_path do wiki: %s", e)


_FIGMA_CDN_PREFIXES = (
    "https://figma-alpha-api.s3.amazonaws.com/",
    "https://s3-alpha-sig.figma.com/",
    "https://s3-alpha.figma.com/",
    "https://figma-production-assets.s3.amazonaws.com/",
    "https://lh3.googleusercontent.com/",
)

# Krátkodobá cache: CDN URL → bytes obrázku (platí po dobu běhu serveru)
_figma_image_cache: dict[str, bytes] = {}


def _save_figma_image_from_cdn(
    cdn_url: str, wiki_path: str, epic: str, issue_number: int | None = None
) -> str | None:
    """Uloží Figma obrázek do assets. Pokud je nastaven TARGET_SYSTEM=jira a issue_number,
    nahraje obrázek také jako přílohu Jira ticketu."""
    import urllib.request as _ur
    cached = _figma_image_cache.get(cdn_url)
    if not cached:
        if not any(cdn_url.startswith(p) for p in _FIGMA_CDN_PREFIXES):
            return None
        try:
            with _ur.urlopen(cdn_url, timeout=30, context=story_builder._ssl_context()) as resp:
                cached = resp.read()
        except Exception:
            return None
    story_id = Path(wiki_path).stem
    try:
        assets_dir, md_prefix = _wiki_helpers.assets_info(_REPO_ROOT, story_id, epic)
        assets_dir.mkdir(parents=True, exist_ok=True)
        filename = f"figma_{story_id}.png"
        dest = assets_dir / filename
        dest.write_bytes(cached)
        if issue_number is not None:
            try:
                get_provider().upload_attachment_bytes(issue_number, filename, cached)
            except Exception as e:
                app.logger.warning("Nepodařilo se nahrát figma obrázek jako přílohu: %s", e)
        return f"{md_prefix}/{filename}"
    except Exception:
        return None


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
        result = get_provider().create_story(title=name, body=body, epic=epic, repo_root=str(_REPO_ROOT), files=files, labels=labels)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    issue_url = result["issue_url"]
    wiki_path = result["wiki_path"]
    issue_number = result.get("issue_number")
    if issue_number is None:
        match = re.search(r"/issues/(\d+)$", issue_url)
        issue_number = int(match.group(1)) if match else None

    figma_cdn = str(data.get("figma_image_cdn_url", "")).strip()
    if figma_cdn:
        saved_path = _save_figma_image_from_cdn(figma_cdn, wiki_path, epic, issue_number)
        if saved_path:
            _insert_figma_image_path(wiki_path, issue_number, saved_path)

    return jsonify({
        "issue_url": issue_url,
        "issue_number": issue_number,
        "wiki_path": wiki_path,
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

    # Validace wiki_path — musí být v WIKI_DIR (ochrana před path traversal)
    from pathlib import PurePosixPath
    try:
        normalized = str(PurePosixPath(wiki_path))
        if not normalized.startswith(_WIKI_DIR + "/") or ".." in normalized:
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
    epic = str(data.get("epic", "")).strip()

    figma_cdn = str(data.get("figma_image_cdn_url", "")).strip()
    if figma_cdn and not data.get("figma_image_path"):
        saved_path = _save_figma_image_from_cdn(figma_cdn, wiki_path, epic, issue_number)
        if saved_path:
            data["figma_image_path"] = saved_path

    body = _build_draft_body(data, status=current_status)

    try:
        result = get_provider().update_story(
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
        issues_raw = get_provider().list_issues(state)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

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

        ana_match = re.search(r"^- Analýza:.*?· čas ([^\n·]+)", body, re.MULTILINE)
        impl_match = re.search(r"^- Implementace:.*?· čas ([^\n·]+)", body, re.MULTILINE)
        cycle_match = re.search(r"^- Cycle time:\s*([^\n(]+?)(?:\s*\(|$)", body, re.MULTILINE)
        ana_str = ana_match.group(1).strip() if ana_match else None
        impl_str = impl_match.group(1).strip() if impl_match else None

        def _dur_to_s(d: str) -> int:
            h = re.search(r'(\d+)h', d)
            m = re.search(r'(\d+)m', d)
            s = re.search(r'(\d+)s', d)
            return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(s.group(1)) if s else 0)

        def _fmt_s(t: int) -> str:
            return f"{t // 3600}h {(t % 3600) // 60}m" if t >= 3600 else f"{t // 60}m {t % 60}s"

        if ana_str and impl_str:
            duration_str = _fmt_s(_dur_to_s(ana_str) + _dur_to_s(impl_str))
            duration_detail = f"Analýza: {ana_str} + Implementace: {impl_str}"
        elif impl_str:
            duration_str = impl_str
            duration_detail = None
        elif ana_str:
            duration_str = ana_str
            duration_detail = None
        elif cycle_match:
            duration_str = cycle_match.group(1).strip()
            duration_detail = None
        else:
            duration_str = None
            duration_detail = None

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
            "wiki_path": f"{_WIKI_DIR}/US-{issue['number']:03d}.md",
            "cost_usd": cost_usd,
            "duration_str": duration_str,
            "duration_detail": duration_detail,
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
    if not wiki_path.startswith(_WIKI_DIR + "/") or ".." in wiki_path:
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
        get_provider().attach_files_to_story(
            issue_number=int(issue_number),
            wiki_path=wiki_path,
            repo_root=str(_REPO_ROOT),
            files=files,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"ok": True}), 200


@app.post("/api/figma-describe")
def figma_describe():
    data = request.get_json(silent=True) or {}
    figma_url = (data.get("figma_url") or "").strip()
    if not figma_url:
        return jsonify({"error": "Chybí figma_url"}), 400
    result = story_builder.run_figma_describe(figma_url)
    if not result or "error" in result:
        return jsonify({"error": (result or {}).get("error", "Chyba při načítání")}), 500
    image_bytes = result.pop("_image_bytes", None)
    cdn_url = result.get("image_url")
    if cdn_url and image_bytes:
        _figma_image_cache[cdn_url] = image_bytes
    return jsonify({
        "description": result.get("shows", result.get("text", "")),
        "behaves": result.get("behaves", ""),
        "image_url": cdn_url,
    })


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

    provider = get_provider()
    try:
        issue_data = provider.get_issue(issue_number)
    except FileNotFoundError as e:
        return jsonify({"error": str(e) or "Bug nenalezen."}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

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
        provider.update_body(issue_number, new_body)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    if new_status == "done":
        try:
            provider.transition_status(issue_number, "done")
        except Exception:
            pass

    # Bugy jsou uloženy jako wiki/stories/US-NNN.md (stejný formát jako stories)
    bug_wiki = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    if bug_wiki.exists():
        try:
            wc = bug_wiki.read_text(encoding="utf-8")
            wc = re.sub(r"(?m)^- Status: .+$", f"- Status: {new_status}", wc, count=1)
            wc = re.sub(r"(?m)^status: .+$", f"status: {new_status}", wc, count=1)
            bug_wiki.write_text(wc, encoding="utf-8")
            _status_history.append(str(bug_wiki), new_status)
            _status_history.update_cycle_time(str(bug_wiki))
            # Synchronizuj aktualizovaný obsah (včetně metrik) do issue body
            updated_wc = bug_wiki.read_text(encoding="utf-8")
            try:
                provider.update_body(issue_number, updated_wc)
            except Exception as e:
                app.logger.warning("Body sync selhal: %s", e)
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

    provider = get_provider()
    try:
        issue_data = provider.get_issue(issue_number)
    except FileNotFoundError as e:
        return jsonify({"error": str(e) or "Issue nenalezena."}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

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
        provider.update_body(issue_number, new_body)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    try:
        provider.transition_status(issue_number, new_status)
    except Exception as e:
        app.logger.warning("provider.transition_status #%s selhal: %s", issue_number, e)

    wiki_path = _REPO_ROOT / f"{_WIKI_DIR}/US-{issue_number:03d}.md"
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


@app.get("/api/chat")
def get_chat():
    try:
        issue_number = int(request.args.get("issue_number", 0))
    except (TypeError, ValueError):
        issue_number = 0
    if not issue_number or issue_number <= 0:
        return jsonify({"error": "Chybí nebo neplatné issue_number."}), 400
    wiki_path = f"{_WIKI_DIR}/US-{issue_number:03d}.md"
    return jsonify({"messages": wiki_chat.read_chat_messages(wiki_path)}), 200


_flask_debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
if not _flask_debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    threading.Thread(target=_poller_loop, daemon=True, name="tf-poller").start()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5001")), debug=_flask_debug)
