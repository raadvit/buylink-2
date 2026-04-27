import json as _json
import pathlib
import re
import subprocess
import time
import uuid
from datetime import date

import github_helper
import store_state

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TOKEN_STRATEGY = _REPO_ROOT / "agents" / "token_strategy.md"


def _model_for_agent(agent_name: str) -> str:
    try:
        content = _TOKEN_STRATEGY.read_text(encoding="utf-8")
        for line in content.splitlines():
            if f"| {agent_name} " in line or f"| {agent_name}\t" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    return parts[-1]  # poslední sloupec = aktuální model
    except Exception:
        pass
    return "claude-haiku-4-5-20251001"

_V1_CONTEXT = _REPO_ROOT / ".memory-system" / "V1 - static context" / "context.md"
_V1_CONSTRAINTS = _REPO_ROOT / ".memory-system" / "V1 - static context" / "constraints.md"
_V1_STORY_TEMPLATE = _REPO_ROOT / ".memory-system" / "V1 - static context" / "story_template.md"
_V2_DOMAIN = _REPO_ROOT / ".memory-system" / "V2 - Shared Truth" / "domain_model.md"
_V2_REGISTER = _REPO_ROOT / ".memory-system" / "V2 - Shared Truth" / "story_register.md"
_AGENTS_DIR = _REPO_ROOT / "agents" / "team"


def _read_file(path: pathlib.Path, max_chars: int = 4000) -> str:
    try:
        content = path.read_text(encoding="utf-8")
        return content[:max_chars] if max_chars else content
    except Exception:
        return ""


def _agent_max_questions(agent_file: pathlib.Path, default: int = 3) -> int:
    content = _read_file(agent_file, max_chars=500)
    match = re.search(r"-\s*max_questions:\s*(\d+)", content)
    return int(match.group(1)) if match else default


_MAX_BUDGET_USD_PER_RUN = 0.50  # TODO: dočasné, pro testování — odstranit po ověření

def _call_claude(prompt: str, model: str, timeout: int = 60) -> dict | None:
    """Vrací {text, usage} nebo {error, usage} — nikdy None."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json",
             "--no-session-persistence", "--max-budget-usd", str(_MAX_BUDGET_USD_PER_RUN)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=None, text=True, timeout=timeout, cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError:
        return {"error": "claude_not_found"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}

    try:
        outer = _json.loads(result.stdout)
    except Exception:
        return {"error": result.stderr.strip() or "parse_error"}

    cost_usd = outer.get("total_cost_usd", 0.0) or 0.0

    if outer.get("is_error"):
        subtype = outer.get("subtype", "")
        errors = outer.get("errors", [])
        if subtype == "error_max_budget_usd" or any("budget" in e.lower() for e in errors):
            return {"error": "budget_exceeded", "cost_usd": cost_usd}
        return {"error": subtype or errors[0] if errors else "api_error", "cost_usd": cost_usd}

    if result.returncode != 0:
        return {"error": "nonzero_exit"}

    return {"text": outer.get("result", "").strip(), "cost_usd": cost_usd}


def _parse_agent_json(text: str) -> dict:
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return _json.loads(match.group())
    except Exception:
        pass
    return {}


def _ask_and_wait(session_id: str, store, questions: list[str], agent: str, timeout: int = 600) -> list[str] | None:
    q_list = [{"id": str(uuid.uuid4()), "text": q, "answer": None, "agent": agent} for q in questions]
    store.update_session(session_id, questions=q_list, status="asking_questions", validation_agent=agent)
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = store.get_session(session_id)
        if session is None or session.get("status") == "error":
            return None
        if store.all_questions_answered(session_id):
            session = store.get_session(session_id)
            answers = [q["answer"] for q in session.get("questions", [])]
            store.update_session(session_id, questions=[], validation_agent=None, status="reviewing")
            return answers
        time.sleep(1.5)
    return None


def _story_text(form_data: dict) -> str:
    lines = [
        f"Název: {form_data.get('name', '')}",
        f"Epic: {form_data.get('epic', '')}",
        f"Role: {form_data.get('role', '')}",
        f"Co se zobrazuje: {form_data.get('what', '')}",
        f"Jak se to chová: {form_data.get('how', '')}",
    ]
    for key, label in [("scope", "Rizikové situace"), ("deps", "Otevřené otázky"), ("ac", "Vlastní AC")]:
        if form_data.get(key):
            lines.append(f"{label}: {form_data[key]}")
    return "\n".join(lines)


def _agent_error_msg(agent: str, error: str) -> str:
    if error == "budget_exceeded":
        return f"{agent} si dal pauzu — došly tokeny (limit ${_MAX_BUDGET_USD_PER_RUN})."
    if error == "timeout":
        return f"{agent} nereagoval včas (timeout 60s)."
    if error == "claude_not_found":
        return "Claude CLI nenalezeno."
    return f"{agent} selhal: {error}"


def _run_product_owner(session_id: str, form_data: dict, store) -> str | None:
    store.update_session(session_id, status="reviewing", validation_phase="product_owner",
                         review_summary="Product Owner posuzuje zadání…")

    instructions = _read_file(_AGENTS_DIR / "product-owner.md")
    domain_model = _read_file(_V2_DOMAIN, max_chars=3000)
    story = _story_text(form_data)

    prompt = f"""{instructions}

---

Kontext projektu (domain model — etablované konvence, lifecycle, workflow):
{domain_model or "(prázdný)"}

---

Nový feature request:

{story}

---

Tvůj úkol (Fáze 1 — business zadání):
1. Pokud chybí klíčové byznys informace, polož max 4 otázky najednou.
   NEPTEJ SE na věci které jsou již definované v domain modelu výše — workflow, stavy, lifecycle, barvy, technické konvence.
   Ptej se POUZE na business záměr a scope konkrétního zadání.
2. Na základě zadání (+ odpovědí pokud byly) napiš kvalitní business popis story:
   - **Why / Business Goal**: proč tuto věc děláme, jaký problém řeší, business přínos
   - **Co se zobrazuje**: konkrétní UI prvky, pole, sekce, stavy viditelné uživateli
   - **Jak se to chová**: interakce, validace, podmíněná logika, stavy, pravidla
   Buď konkrétní — výstup čte vývojový tým, ne management.
3. Odhadni `reads_sections` a `writes_sections` pro Memory Contract.

AC, Test Cases a technické detaily vygeneruje Architekt — ty je negeneruj.

Odpověz POUZE validním JSON bez textu navíc:
- Máš-li otázky: {{"action": "ask", "questions": ["otázka 1", "otázka 2"], "summary": "stručné shrnutí"}}
- Je-li kompletní: {{
    "action": "complete",
    "summary": "stručné hodnocení",
    "why": "business goal a motivace",
    "what": "co se zobrazuje — konkrétní UI popis",
    "how": "jak se to chová — interakce, pravidla, validace",
    "reads_sections": [],
    "writes_sections": []
  }}"""

    po_model = _model_for_agent("product-owner")

    def _call_po(extra: str = "") -> dict | None:
        full_prompt = prompt + (f"\n\nDoplnění od uživatele:\n{extra}" if extra else "")
        r = _call_claude(full_prompt, po_model)
        store_state.increment_cost(session_id, r.get("cost_usd", 0.0))
        return r

    result = _call_po()
    if result.get("error"):
        store.update_session(session_id, status="error", error=_agent_error_msg("Product Owner", result["error"]))
        return None
    parsed = _parse_agent_json(result["text"])
    store.update_session(session_id, review_summary=f"[Product Owner] {parsed.get('summary', '')}")

    qa_pairs = []
    if parsed.get("action") == "ask" and parsed.get("questions"):
        max_q = _agent_max_questions(_AGENTS_DIR / "product-owner.md")
        answers = _ask_and_wait(session_id, store, parsed["questions"][:max_q], "Product Owner")
        if answers is None:
            store.update_session(session_id, status="error", error="Timeout při čekání na odpovědi Product Ownera.")
            return None
        qa_pairs = list(zip(parsed["questions"], answers))
        qa = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_pairs)
        # Druhé volání PO jen pro získání Memory Contract s doplněným kontextem
        result2 = _call_po(extra=qa)
        if not result2.get("error"):
            parsed = _parse_agent_json(result2["text"])

    return {
        "story_text": _story_text(form_data),
        "why": parsed.get("why", ""),
        "what": parsed.get("what", form_data.get("what", "")),
        "how": parsed.get("how", form_data.get("how", "")),
        "summary": parsed.get("summary", ""),
        "reads_sections": parsed.get("reads_sections", []),
        "writes_sections": parsed.get("writes_sections", []),
        "qa_pairs": qa_pairs,
    }


def _run_conflict_detector(session_id: str, story_context: str, store) -> dict:
    store.update_session(session_id, validation_phase="conflict_detector",
                         review_summary="Conflict Detector kontroluje závislosti…")

    instructions = _read_file(_AGENTS_DIR / "conflict-detector.md")
    domain_model = _read_file(_V2_DOMAIN)
    story_register = _read_file(_V2_REGISTER)

    prompt = f"""{instructions}

---

Story k posouzení:
{story_context}

Domain model (V2):
{domain_model or "(prázdný)"}

Story register:
{story_register or "(prázdný)"}

---

Zkontroluj konflikty a závislosti.
Odpověz POUZE validním JSON:
- OK: {{"action": "ok", "affected_stories": []}}
- Konflikt: {{"action": "conflict", "conflicts": [{{"typ": "...", "story": "...", "popis": "..."}}]}}"""

    result = _call_claude(prompt, _model_for_agent("conflict-detector"))
    store_state.increment_cost(session_id, result.get("cost_usd", 0.0))
    if result.get("error"):
        return {"action": "ok", "affected_stories": []}  # non-fatal, pokračuj
    parsed = _parse_agent_json(result["text"])
    return parsed if parsed.get("action") in ("ok", "conflict") else {"action": "ok", "affected_stories": []}


def _run_architect_phase1(session_id: str, po_data: dict, conflict_result: dict, store) -> dict | None:
    store.update_session(session_id, validation_phase="architect",
                         review_summary="Architekt přidává technické anotace…")

    instructions = _read_file(_AGENTS_DIR / "architekt.md")
    v1_context = _read_file(_V1_CONTEXT, max_chars=2000)
    v1_constraints = _read_file(_V1_CONSTRAINTS, max_chars=1000)
    domain_model = _read_file(_V2_DOMAIN)

    story_context = po_data.get("story_text", "")
    qa_context = ""
    if po_data.get("qa_pairs"):
        qa_context = "\n\nUpřesnění od zadavatele (odpovědi na dotazy PO):\n" + "\n".join(
            f"- Q: {q}\n  A: {a}" for q, a in po_data["qa_pairs"]
        )

    conflict_info = ""
    if conflict_result.get("action") == "conflict":
        conflict_info = "\n\nConflict Detector nalezl:\n" + "\n".join(
            f"- {c.get('typ', '')}: {c.get('popis', '')}"
            for c in conflict_result.get("conflicts", [])
        )

    prompt = f"""{instructions}

---

Kontext projektu (V1):
{v1_context or "(prázdný)"}

Omezení (V1):
{v1_constraints or "(prázdný)"}

Domain model (V2):
{domain_model or "(prázdný)"}

---

Story k technické anotaci (Fáze 1 — příprava, ne implementace):
{story_context}{qa_context}{conflict_info}

---

Tvůj úkol (Fáze 1 — technická anotace):
1. Doplň technické popisky: dotčené komponenty, závislosti, datový model.
2. Vygeneruj Acceptance Criteria (funkční + nefunkční podmínky) — zahrň kontext z upřesnění.
3. Vygeneruj Test Cases (happy path, negative, edge case, chybový stav).
4. Extrahuj doménové znalosti ze story a zapiš je do domain_model.md.
   Zapiš VŽDY pokud story definuje nebo upřesňuje:
   - stavy UI komponent a jejich vizuální reprezentaci (barvy, ikony, texty)
   - chování komponent (kdy se zobrazí, kdy zmizí, podmínky)
   - datové entity a jejich atributy
   - business pravidla a validace
   - API kontrakty a formáty dat
   Sekce používají tagging: <!-- SECTION: název -->...<!-- /SECTION: název -->
   Pokud existující sekce v domain_model je relevantní, rozšíř ji — nepřidávej duplicity.
   Prázdné pole vrať POUZE pokud story opravdu nepřináší žádnou novou doménovou znalost.
Neptej se na žádné otázky — pracuj s dostupným kontextem.

Odpověz POUZE validním JSON:
{{
    "action": "complete",
    "technical_notes": "technické poznámky",
    "acceptance_criteria": {{"functional": ["- [ ] AC1"], "non_functional": ["- [ ] AC1"]}},
    "test_cases": ["- [ ] Happy path: ...", "- [ ] Negative: ...", "- [ ] Edge case: ...", "- [ ] Chybový stav: ..."],
    "domain_model_updates": [{{"section": "název", "content": "<!-- SECTION: název -->\\n...\\n<!-- /SECTION: název -->"}}]
}}"""

    result = _call_claude(prompt, _model_for_agent("architekt"), timeout=90)
    store_state.increment_cost(session_id, result.get("cost_usd", 0.0))
    if result.get("error"):
        store.update_session(session_id, status="error", error=_agent_error_msg("Architekt", result["error"]))
        return None
    parsed = _parse_agent_json(result["text"])

    return {
        "technical_notes": parsed.get("technical_notes", ""),
        "acceptance_criteria": parsed.get("acceptance_criteria", {}),
        "test_cases": parsed.get("test_cases", []),
        "domain_model_updates": parsed.get("domain_model_updates", []),
    }


def _build_story_body(form_data: dict, po_data: dict, arch_data: dict, total_cost_usd: float = 0.0, cost_breakdown: dict | None = None) -> str:
    today = date.today().isoformat()
    name = form_data.get('name', '')

    token_lines = [f"- Validace cena: ${total_cost_usd:.4f}"]
    if cost_breakdown:
        for agent, cost in cost_breakdown.items():
            token_lines.append(f"  - {agent}: ${cost:.4f}")

    lines = [
        f"# {name}",
        "",
        "## Metadata",
        f"- Epic: {form_data.get('epic', '')}",
        f"- Role: {form_data.get('role', '')}",
        "- Status: validated",
        "- GitHub: ",
        f"- Vytvořeno: {today}",
        f"- Změněno: {today}",
        *token_lines,
        "",
        "---",
        "",
        "## Memory Contract",
        f"- `reads_sections`: {po_data.get('reads_sections', [])}",
        f"- `writes_sections`: {po_data.get('writes_sections', [])}",
        "- `affected_stories`: []",
        "",
        "---",
    ]

    if po_data.get("why"):
        lines += ["", "## Why / Business Goal", po_data["why"]]
    for key, heading, fallback in [
        ("what", "Co se zobrazuje", form_data.get("what", "")),
        ("how", "Jak se to chová", form_data.get("how", "")),
    ]:
        content = po_data.get(key) or fallback
        if content:
            lines += ["", f"## {heading}", content]
    for key, heading in [("scope", "Rizikové situace"), ("deps", "Otevřené otázky")]:
        if form_data.get(key):
            lines += ["", f"## {heading}", form_data[key]]

    ac = arch_data.get("acceptance_criteria", {})
    if ac:
        lines += ["", "## Acceptance Criteria", "", "### Funkční podmínky"]
        lines += ac.get("functional", ["- [ ] "])
        lines += ["", "### Nefunkční podmínky"]
        lines += ac.get("non_functional", ["- [ ] "])

    test_cases = arch_data.get("test_cases", [])
    if test_cases:
        lines += ["", "## Test Cases"]
        lines += test_cases

    if arch_data.get("technical_notes"):
        lines += ["", "## Technické poznámky (Architekt)", arch_data["technical_notes"]]

    return "\n".join(lines)


def _apply_domain_model_updates(updates: list) -> None:
    if not updates:
        return
    try:
        path = _V2_DOMAIN
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        for update in updates:
            section = update.get("section", "").strip()
            new_content = update.get("content", "").strip()
            if not section or not new_content:
                continue
            pattern = f"<!-- SECTION: {section} -->.*?<!-- /SECTION: {section} -->"
            import re as _re
            if _re.search(pattern, content, _re.DOTALL):
                content = _re.sub(pattern, new_content, content, flags=_re.DOTALL)
            else:
                content = content.rstrip() + f"\n\n{new_content}\n"
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        import sys
        print(f"[story_builder] Varování: nepodařilo se aktualizovat domain_model: {e}", file=sys.stderr)


def _save_qa_to_domain_model(qa_pairs: list) -> None:
    if not qa_pairs:
        return
    try:
        path = _V2_DOMAIN
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        new_entries = "\n".join(f"- Q: {q}\n  A: {a}" for q, a in qa_pairs)
        section_tag = "project-qa"
        import re as _re
        pattern = f"<!-- SECTION: {section_tag} -->.*?<!-- /SECTION: {section_tag} -->"
        existing = _re.search(pattern, content, _re.DOTALL)
        if existing:
            old_section = existing.group(0)
            updated = old_section.replace(f"<!-- /SECTION: {section_tag} -->",
                                          f"{new_entries}\n<!-- /SECTION: {section_tag} -->")
            content = content.replace(old_section, updated)
        else:
            section = (f"\n\n<!-- SECTION: {section_tag} -->\n"
                       f"## Ustanovené odpovědi (Q&A z validací)\n\n"
                       f"{new_entries}\n"
                       f"<!-- /SECTION: {section_tag} -->")
            content = content.rstrip() + section + "\n"
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        import sys
        print(f"[story_builder] Varování: nepodařilo se uložit Q&A do domain_model: {e}", file=sys.stderr)


def _update_story_register(story_id: str, title: str, epic: str, github_number: str) -> None:
    register_path = _V2_REGISTER
    try:
        existing = register_path.read_text(encoding="utf-8") if register_path.exists() else ""
        if not existing.strip():
            existing = "# Story Register\n\n| ID | Název | Epic | Status | GitHub |\n|---|---|---|---|---|\n"
        entry = f"| {story_id} | {title} | {epic} | validated | #{github_number} |\n"
        if story_id not in existing:
            register_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
    except Exception as e:
        import sys
        print(f"[story_builder] Varování: nepodařilo se aktualizovat story_register: {e}", file=sys.stderr)


def run_team_validation(session_id: str, form_data: dict, store) -> None:
    """Fáze 1: Product Owner → Conflict Detector → Architekt → uložení story."""
    cost_snapshot = lambda: (store_state.get_session(session_id) or {}).get("total_cost_usd", 0.0)

    # 1. Product Owner
    cost_before_po = cost_snapshot()
    po_data = _run_product_owner(session_id, form_data, store)
    if po_data is None:
        return
    cost_breakdown = {"Product Owner": round(cost_snapshot() - cost_before_po, 6)}
    if po_data.get("qa_pairs"):
        _save_qa_to_domain_model(po_data["qa_pairs"])

    # 2. Conflict Detector
    cost_before_cd = cost_snapshot()
    conflict_result = _run_conflict_detector(session_id, po_data["story_text"], store)
    cost_breakdown["Conflict Detector"] = round(cost_snapshot() - cost_before_cd, 6)
    if conflict_result.get("action") == "conflict":
        conflicts_text = "⚠️ Conflict Detector nalezl konflikty:\n" + "\n".join(
            f"- {c.get('typ', '')}: {c.get('popis', '')}"
            for c in conflict_result.get("conflicts", [])
        )
        store_state.add_review_comment(session_id, conflicts_text)

    # 3. Architekt (Fáze 1) — technické anotace + AC + test cases
    cost_before_arch = cost_snapshot()
    arch_data = _run_architect_phase1(session_id, po_data, conflict_result, store)
    if arch_data is None:
        return
    cost_breakdown["Architekt"] = round(cost_snapshot() - cost_before_arch, 6)

    # 4. Uložení story s status: validated
    store.update_session(session_id, status="building", validation_phase="done",
                         review_summary="Story je připravena.")
    try:
        total_cost = cost_snapshot()
        story_body = _build_story_body(
            form_data=form_data,
            po_data=po_data,
            arch_data=arch_data,
            total_cost_usd=total_cost,
            cost_breakdown=cost_breakdown,
        )
        existing_issue = form_data.get("issue_number")
        existing_wiki = form_data.get("wiki_path")
        if existing_issue and existing_wiki:
            parsed = github_helper.update_story(
                issue_number=int(existing_issue),
                title=form_data["name"],
                body=story_body,
                wiki_path=existing_wiki,
                repo_root=str(_REPO_ROOT),
            )
        else:
            parsed = github_helper.create_story(
                title=form_data["name"],
                body=story_body,
                epic=form_data.get("epic", ""),
                repo_root=str(_REPO_ROOT),
                labels=["user story"],
            )
        store.update_session(session_id, result=parsed, status="done")
        _apply_domain_model_updates(arch_data.get("domain_model_updates", []))
        _update_story_register(
            story_id=parsed["wiki_path"].split("/")[-1].replace(".md", ""),
            title=form_data["name"],
            epic=form_data.get("epic", ""),
            github_number=parsed["issue_url"].split("/")[-1] if parsed.get("issue_url") else "",
        )
    except Exception as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se vytvořit GitHub issue: {e}")


def run_review_comment(session_id: str, comment_id: str, comment_text: str, form_data: dict, store) -> None:
    prompt = (
        f"Uživatel chce vytvořit story a má komentář. Odpověz stručně (1-2 věty).\n\n"
        f"Formulář:\nNázev: {form_data.get('name', '')}\n"
        f"Co se zobrazuje: {form_data.get('what', '')}\n"
        f"Jak se to chová: {form_data.get('how', '')}\n\n"
        f"Komentář: {comment_text}"
    )
    result = _call_claude(prompt, _model_for_agent("product-owner"))
    store_state.increment_cost(session_id, result.get("cost_usd", 0.0) if result else 0.0)
    reply = result["text"] if result else "Chyba při zpracování komentáře."
    store.set_review_reply(session_id, comment_id, reply)
    store.update_session(session_id, status="reviewing")
