import threading
import uuid


_store: dict[str, dict] = {}
_lock = threading.Lock()

# Stavy session: waiting_for_validation, reviewing, processing, asking_questions,
#                building, preview, done, error


def create_session(session_id: str, form_data: dict) -> dict:
    session = {
        "status": "waiting_for_validation",
        "form_data": form_data,
        "questions": [],
        "messages": [],
        "preview": None,
        "result": None,
        "error": None,
        "review_comments": [],
        "review_summary": "",
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "validation_phase": None,
        "validation_agent": None,
    }
    with _lock:
        _store[session_id] = session
    return session


def get_session(session_id: str) -> dict | None:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return None
        return dict(session)


def update_session(session_id: str, **kwargs) -> None:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return
        session.update(kwargs)


def increment_cost(session_id: str, cost_usd: float) -> None:
    if not cost_usd:
        return
    with _lock:
        session = _store.get(session_id)
        if session is not None:
            session["total_cost_usd"] = round(session.get("total_cost_usd", 0.0) + cost_usd, 6)


def compare_and_set_status(session_id: str, expected: str, new: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None or session["status"] != expected:
            return False
        session["status"] = new
        return True


def set_answer(session_id: str, question_id: str, answer: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return False
        for question in session["questions"]:
            if question["id"] == question_id:
                question["answer"] = answer
                return True
        return False


def add_review_comment(session_id: str, text: str) -> str | None:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return None
        comment_id = str(uuid.uuid4())
        session["review_comments"].append({"id": comment_id, "text": text, "reply": None})
        return comment_id


def set_review_reply(session_id: str, comment_id: str, reply: str) -> None:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return
        for comment in session["review_comments"]:
            if comment["id"] == comment_id:
                comment["reply"] = reply
                return


def push_message(session_id: str, text: str, agent: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return False
        session.setdefault("messages", []).append({
            "id": str(uuid.uuid4()),
            "text": text,
            "agent": agent,
        })
        return True


def push_question(session_id: str, question_id: str, text: str, agent: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return False
        session.setdefault("questions", []).append({
            "id": question_id,
            "text": text,
            "answer": None,
            "agent": agent,
        })
        session["status"] = "asking_questions"
        session["validation_agent"] = agent
        return True


def get_answer(session_id: str, question_id: str) -> dict:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return {"answered": False}
        for q in session.get("questions", []):
            if q["id"] == question_id:
                if q.get("answer") is not None:
                    return {"answered": True, "answer": q["answer"]}
                return {"answered": False}
        return {"answered": False}


def get_pending_question_sessions() -> list:
    with _lock:
        result = []
        for sid, session in _store.items():
            if session.get("status") == "asking_questions":
                fd = session.get("form_data", {})
                unanswered = [q for q in session.get("questions", []) if q.get("answer") is None]
                if unanswered:
                    result.append({
                        "session_id": sid,
                        "issue_number": fd.get("issue_number"),
                        "questions": unanswered,
                    })
        return result


def all_questions_answered(session_id: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return False
        questions = session.get("questions", [])
        if not questions:
            return True
        return all(q.get("answer") is not None for q in questions)


def all_sessions() -> dict:
    with _lock:
        return {sid: dict(s) for sid, s in _store.items()}


def get_session_by_issue(issue_number: int) -> dict | None:
    with _lock:
        for sid, session in _store.items():
            fd = session.get("form_data", {})
            if (fd.get("issue_number") == issue_number
                    and session.get("status") not in ("done", "error")):
                return {"session_id": sid, "status": session["status"]}
    return None
