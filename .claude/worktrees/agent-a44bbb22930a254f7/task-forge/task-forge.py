import json as _json
import os
import re
import subprocess
import threading
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import github_helper
import store_state
import story_builder

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_github_repo() -> str:
    config = _REPO_ROOT / ".claude" / "config.md"
    try:
        import re as _re
        for line in config.read_text(encoding="utf-8").splitlines():
            if "Main_repo" in line and "`" in line:
                m = _re.search(r"`([^`]+/[^`]+)`", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return "raadvit/PreciousMetals_backend"


_GITHUB_REPO = _load_github_repo()

app = Flask(__name__, static_folder=str(_STATIC_DIR))

_REQUIRED_FIELDS = ("name", "epic", "role", "what", "how")


@app.get("/")
def index():
    return send_from_directory(str(_STATIC_DIR), "index.html")


@app.get("/bug/new")
def bug_new():
    return send_from_directory(str(_STATIC_DIR), "bug.html")


@app.post("/api/submit-bug")
def submit_bug():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Chybí tělo požadavku (JSON)."}), 400

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

    session_id = str(uuid.uuid4())
    store_state.create_session(session_id, form_data)

    t = threading.Thread(
        target=story_builder.run_team_validation,
        args=(session_id, form_data, store_state),
        daemon=True,
    )
    t.start()

    return jsonify({"session_id": session_id}), 202


@app.get("/api/session")
def get_session():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "Chybí parametr session_id."}), 400

    session = store_state.get_session(session_id)
    if session is None:
        return jsonify({"error": "Session nenalezena."}), 404

    response = dict(session)
    response["review_summary"] = session.get("review_summary", "")
    response["review_comments"] = session.get("review_comments", [])
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


def _build_draft_body(data: dict) -> str:
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
        "- Status: draft",
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


def _build_bug_body(data: dict) -> str:
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


@app.post("/api/save")
def save():
    data, files = _parse_request()
    if not data:
        return jsonify({"error": "Chybí tělo požadavku."}), 400

    _normalize_role(data)

    if not str(data.get("name", "")).strip():
        return jsonify({"error": "Chybí povinné pole: name"}), 422

    body = _build_draft_body(data)
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

    body = _build_draft_body(data)

    try:
        result = github_helper.update_story(
            issue_number=issue_number,
            title=name,
            body=body,
            wiki_path=wiki_path,
            repo_root=str(_REPO_ROOT),
            files=files,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"issue_url": result["issue_url"], "wiki_path": result["wiki_path"]}), 200


@app.get("/api/issues")
def get_issues():
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", _GITHUB_REPO, "--state", "open",
             "--json", "number,title,labels,updatedAt,body", "--limit", "100"],
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
        epic_match = re.search(r"- Epic:\s*(.+)", body)
        epic = epic_match.group(1).strip() if epic_match else ""
        status_match = re.search(r"- Status:\s*(.+)", body)
        story_status = status_match.group(1).strip() if status_match else ""

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
            "wiki_path": f"wiki/stories/US-{issue['number']:03d}.md",
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


@app.get("/api/eur-rate")
def eur_rate():
    url = "https://www.cnb.cz/cs/financni_trhy/devizovy_trh/kurzy_devizoveho_trhu/denni_kurz.xml"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        radek = root.find('.//*[@kod="EUR"]')
        if radek is None:
            return jsonify({"error": "unavailable"}), 502
        kurz_str = radek.get("kurz", "").replace(",", ".")
        rate = round(float(kurz_str), 2)
        return jsonify({"rate": rate}), 200
    except Exception:
        return jsonify({"error": "unavailable"}), 502


if __name__ == "__main__":
    app.run(port=5001, debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true')
