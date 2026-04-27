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


def all_questions_answered(session_id: str) -> bool:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return False
        questions = session.get("questions", [])
        if not questions:
            return True
        return all(q.get("answer") is not None for q in questions)
