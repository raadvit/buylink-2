import json as _json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime

import store_state
from issue_provider import get_provider

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TOKEN_STRATEGY = _REPO_ROOT / "agents" / "token_strategy.md"


def _append_status_history(wiki_path: pathlib.Path, status: str) -> None:
    """Přidá záznam {status, ts} do status_history ve frontmatteru wiki souboru."""
    try:
        content = wiki_path.read_text(encoding="utf-8")
        ts = datetime.now().isoformat(timespec='seconds')
        entry = f"  - status: {status}\n    ts: \"{ts}\""
        if "status_history:" in content:
            content = re.sub(
                r"(status_history:(?:\n  - [^\n]+(?:\n    [^\n]+)*)*)",
                lambda m: m.group(0) + "\n" + entry,
                content, count=1,
            )
        else:
            content = re.sub(
                r"^(status: [^\n]+)",
                r"\1\nstatus_history:\n" + entry,
                content, flags=re.MULTILINE, count=1,
            )
        wiki_path.write_text(content, encoding="utf-8")
    except Exception:
        pass


def _load_github_repo() -> str:
    return os.environ.get("GITHUB_REPO", "raadvit/PreciousMetals_backend")


_GITHUB_REPO = _load_github_repo()


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
_AGENTS_DIR = _REPO_ROOT / ".memory-system" / "team"
_CONFIG = _REPO_ROOT / ".claude" / "config.md"

_impl_plan_in_analysis: bool | None = None


def _get_impl_plan_in_analysis() -> bool:
    global _impl_plan_in_analysis
    if _impl_plan_in_analysis is None:
        _impl_plan_in_analysis = _read_config_flag("architect_creates_implementation_plan", default=True)
    return _impl_plan_in_analysis


def _read_config_flag(key: str, default: bool = True) -> bool:
    try:
        text = _CONFIG.read_text(encoding="utf-8")
        for line in text.splitlines():
            if f"**{key}**" in line:
                return "true" in line.lower()
    except Exception:
        pass
    return default


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

def _call_claude(prompt: str, model: str, timeout: int = 120) -> dict | None:
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
        return f"{agent} nereagoval včas — zkus znovu nebo zvyš timeout v story_builder.py."
    if error == "claude_not_found":
        return "Claude CLI nenalezeno."
    return f"{agent} selhal: {error}"


def _run_product_owner(session_id: str, form_data: dict, store) -> str | None:
    store.update_session(session_id, status="reviewing", validation_phase="draft-start",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis(),
                         review_summary="Product Owner posuzuje zadání…")

    instructions = _read_file(_AGENTS_DIR / "product-owner.md")
    domain_model = _read_file(_V2_DOMAIN, max_chars=3000)
    story = _story_text(form_data)
    max_q = _agent_max_questions(_AGENTS_DIR / "product-owner.md")

    prompt = f"""{instructions}

---

Kontext projektu (domain model — etablované konvence, lifecycle, workflow):
{domain_model or "(prázdný)"}

---

Nový feature request:

{story}

---

Tvůj úkol (Fáze 1 — business zadání):
1. Pokud chybí klíčové byznys informace, polož max {max_q} nejdůležitějších otázek najednou.
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

    store.update_session(session_id, validation_phase="draft-finished",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis())
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
    store.update_session(session_id, validation_phase="conflict-check-start",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis(),
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
    store.update_session(session_id, validation_phase="arch-review-start",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis(),
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

    gen_ac = _read_config_flag("generate_acceptance_criteria", default=True)
    ac_instruction = (
        "2. Vygeneruj Acceptance Criteria (funkční + nefunkční podmínky) — zahrň kontext z upřesnění.\n"
        "3. Vygeneruj Test Cases (happy path, negative, edge case, chybový stav).\n"
        "4."
        if gen_ac else
        "2."
    )
    ac_schema = (
        '"acceptance_criteria": {{"functional": ["- [ ] AC1"], "non_functional": ["- [ ] AC1"]}},\n'
        '    "test_cases": ["- [ ] Happy path: ...", "- [ ] Negative: ...", "- [ ] Edge case: ...", "- [ ] Chybový stav: ..."],'
        if gen_ac else
        '"acceptance_criteria": {{}},\n    "test_cases": [],'
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
{ac_instruction} Extrahuj doménové znalosti ze story a zapiš je do domain_model.md.
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
    {ac_schema}
    "domain_model_updates": [{{"section": "název", "content": "<!-- SECTION: název -->\\n...\\n<!-- /SECTION: název -->"}}]
}}"""

    result = _call_claude(prompt, _model_for_agent("architekt"), timeout=180)
    store_state.increment_cost(session_id, result.get("cost_usd", 0.0))
    if result.get("error"):
        store.update_session(session_id, status="error", error=_agent_error_msg("Architekt", result["error"]))
        return None
    parsed = _parse_agent_json(result["text"])

    store.update_session(session_id, validation_phase="arch-review-finished",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis())
    return {
        "technical_notes": parsed.get("technical_notes", ""),
        "acceptance_criteria": parsed.get("acceptance_criteria", {}),
        "test_cases": parsed.get("test_cases", []),
        "domain_model_updates": parsed.get("domain_model_updates", []),
    }


def build_draft_body(form_data: dict) -> str:
    """Minimální body pro uložení story před validací (status: conflict-check)."""
    today = date.today().isoformat()
    lines = [
        f"# {form_data.get('name', '')}",
        "",
        "## Metadata",
        f"- Epic: {form_data.get('epic', '')}",
        f"- Role: {form_data.get('role', '')}",
        "- Status: conflict-check",
        "- GitHub: ",
        f"- Změněno: {today}",
    ]
    for key, heading in [("what", "Co se zobrazuje"), ("how", "Jak se to chová"),
                          ("scope", "Rizikové situace"), ("deps", "Otevřené otázky"), ("ac", "Acceptance Criteria")]:
        if form_data.get(key):
            lines += ["", f"## {heading}", form_data[key]]
    return "\n".join(lines) + "\n"


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _build_story_body(form_data: dict, po_data: dict, arch_data: dict, total_cost_usd: float = 0.0, cost_breakdown: dict | None = None, duration_s: float = 0.0) -> str:
    today = date.today().isoformat()
    name = form_data.get('name', '')

    # Sestavení řádku Analýza pro ## Metriky
    cb = cost_breakdown or {}
    cost_po   = cb.get("Product Owner", 0.0)
    cost_cd   = cb.get("Conflict Detector", 0.0)
    cost_arch = cb.get("Architekt", 0.0)
    duration_str = _format_duration(duration_s) if duration_s else ""
    analyze_line = f"- Analýza: ${total_cost_usd:.4f}"
    if cost_po or cost_cd or cost_arch:
        analyze_line += f" · PO ${cost_po:.4f} · CD ${cost_cd:.4f} · Arch ${cost_arch:.4f}"
    if duration_str:
        analyze_line += f" · čas {duration_str}"

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

    if _read_config_flag("generate_acceptance_criteria", default=True):
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

    lines += ["", "## Metriky", analyze_line, f"- Celkem: ${total_cost_usd:.4f}"]

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
    validation_start = time.time()
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
        store.update_session(session_id, validation_phase="conflict-check-failed",
                             impl_plan_in_analysis=_get_impl_plan_in_analysis())
    else:
        store.update_session(session_id, validation_phase="conflict-check-finished",
                             impl_plan_in_analysis=_get_impl_plan_in_analysis())

    # 3. Architekt (Fáze 1) — přeskoč pokud story nemá žádné V2 závislosti
    is_trivial = (
        not po_data.get("reads_sections") and
        not po_data.get("writes_sections") and
        not conflict_result.get("affected_stories")
    )
    cost_before_arch = cost_snapshot()
    if is_trivial:
        store.update_session(session_id, validation_phase="arch-review-finished",
                             impl_plan_in_analysis=_get_impl_plan_in_analysis())
        arch_data = {"ac": [], "test_cases": [], "tech_notes": "", "domain_model_updates": []}
        cost_breakdown["Architekt"] = 0.0
    else:
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
            duration_s=time.time() - validation_start,
        )
        existing_issue = form_data.get("issue_number")
        existing_wiki = form_data.get("wiki_path")
        provider = get_provider()
        if existing_issue and existing_wiki:
            parsed = provider.update_story(
                issue_number=int(existing_issue),
                title=form_data["name"],
                body=story_body,
                wiki_path=existing_wiki,
                repo_root=str(_REPO_ROOT),
            )
        else:
            parsed = provider.create_story(
                title=form_data["name"],
                body=story_body,
                epic=form_data.get("epic", ""),
                repo_root=str(_REPO_ROOT),
                labels=["user story"],
            )
        store.update_session(session_id, result=parsed, status="done")
        _append_status_history(_REPO_ROOT / parsed["wiki_path"], "validated")
        _apply_domain_model_updates(arch_data.get("domain_model_updates", []))
        _update_story_register(
            story_id=parsed["wiki_path"].split("/")[-1].replace(".md", ""),
            title=form_data["name"],
            epic=form_data.get("epic", ""),
            github_number=parsed["issue_url"].split("/")[-1] if parsed.get("issue_url") else "",
        )
    except Exception as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se vytvořit GitHub issue: {e}")


def update_issue_status_in_development(issue_number: int, wiki_path: str, repo_root: str) -> None:
    """Aktualizuje GitHub issue body — nastaví status na in-development.

    Raises RuntimeError pokud gh CLI selže nebo vyprší timeout.
    """
    root = pathlib.Path(repo_root)
    full_path = root / wiki_path

    try:
        current_body = full_path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Nepodařilo se přečíst wiki soubor: {e}")

    if re.search(r"^- Status:", current_body, re.MULTILINE):
        # Nahraď všechny výskyty — brání vzniku duplicit při opakovaných voláních
        updated_body = re.sub(r"^- Status:[^\n]*\n?", "", current_body, flags=re.MULTILINE)
        updated_body = re.sub(
            r"(^- GitHub:[^\n]*\n)", r"\1- Status: in-development\n", updated_body,
            count=1, flags=re.MULTILINE,
        )
        if updated_body == re.sub(r"^- Status:[^\n]*\n?", "", current_body, flags=re.MULTILINE):
            # GitHub řádek nenalezen, přidej na konec metadat
            updated_body = updated_body.rstrip() + "\n- Status: in-development\n"
    else:
        # Status řádek vůbec neexistuje — přidej za GitHub řádek
        updated_body = re.sub(
            r"(^- GitHub:[^\n]*\n)", r"\1- Status: in-development\n", current_body,
            count=1, flags=re.MULTILINE,
        )
        if updated_body == current_body:
            updated_body = current_body.rstrip() + "\n- Status: in-development\n"

    full_path.write_text(updated_body, encoding="utf-8")
    _append_status_history(full_path, "in_development")

    try:
        result = subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--repo", _GITHUB_REPO,
             "--body", updated_body],
            capture_output=True, text=True, cwd=repo_root, timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("Příkaz 'gh' nebyl nalezen.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Aktualizace GitHub issue trvala příliš dlouho (timeout 30s).")

    if result.returncode != 0:
        raise RuntimeError(
            f"'gh issue edit' selhal: {result.stderr.strip() or 'neznámá chyba'}"
        )


def _get_issue_info(issue_number: int, repo_root: str) -> dict:
    """Vrátí základní info o issue ze GitHub (labels, body). Raises RuntimeError při chybě."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", _GITHUB_REPO,
             "--json", "labels,body,title"],
            capture_output=True, text=True, cwd=repo_root, timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("Příkaz 'gh' nebyl nalezen.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Načítání GitHub issue trvalo příliš dlouho (timeout 30s).")

    if result.returncode != 0:
        raise RuntimeError(f"Nepodařilo se načíst issue: {result.stderr.strip()}")

    import json as _json_mod
    try:
        return _json_mod.loads(result.stdout)
    except Exception:
        raise RuntimeError("Nepodařilo se zparsovat odpověď GitHub API.")


def _write_implement_metrics(full_wiki: pathlib.Path, cost_usd: float, duration_s: float) -> None:
    """Zapíše/přepíše řádek Implementace v sekci ## Metriky wiki souboru."""
    try:
        content = full_wiki.read_text(encoding="utf-8")
    except Exception:
        return
    duration_str = (
        f"{int(duration_s // 3600)}h {int((duration_s % 3600) // 60)}m"
        if duration_s >= 3600
        else f"{int(duration_s // 60)}m {int(duration_s % 60)}s"
    )
    impl_line = f"- Implementace: ${cost_usd:.4f} · čas {duration_str}"
    if "## Metriky" not in content:
        content += f"\n## Metriky\n{impl_line}\n- Celkem: ${cost_usd:.4f}\n"
    elif re.search(r"^- Implementace:", content, re.MULTILINE):
        content = re.sub(r"(?m)^- Implementace:.*$", impl_line, content, count=1)
    else:
        content = re.sub(r"(## Metriky\n)", rf"\1{impl_line}\n", content, count=1)
    analýza_m = re.search(r"^- Analýza:.*\$([0-9]+\.[0-9]+)", content, re.MULTILINE)
    cost_analyze = float(analýza_m.group(1)) if analýza_m else 0.0
    celkem = cost_analyze + cost_usd
    if re.search(r"^- Celkem:", content, re.MULTILINE):
        content = re.sub(r"(?m)^- Celkem:.*$", f"- Celkem: ${celkem:.4f}", content, count=1)
    else:
        content = re.sub(r"(## Metriky\n)", rf"\1- Celkem: ${celkem:.4f}\n", content, count=1)
    try:
        full_wiki.write_text(content, encoding="utf-8")
        subprocess.run(
            ["gh", "issue", "edit", str(full_wiki.stem.replace("US-", "")),
             "--repo", _GITHUB_REPO, "--body", content],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
        )
    except Exception:
        pass


def launch_implement_agent(session_id: str, issue_number: int, store) -> None:
    """Spustí /implement agenta v background vláknu a po dokončení aktualizuje session."""
    import shutil, time
    store.update_session(session_id, status="in_development", implementation_initiated=True)
    claude_bin = shutil.which("claude") or "/opt/homebrew/bin/claude"
    cmd = [claude_bin, "-p", f"/implement {issue_number}", "--output-format", "json"]
    t_start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError:
        store.update_session(session_id, status="error", error=f"claude CLI nenalezeno ({claude_bin}).")
        return
    except Exception as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se spustit agenta: {e}")
        return
    duration_s = time.monotonic() - t_start

    if result.returncode != 0:
        store.update_session(session_id, status="error",
                             error=f"Agent /implement skončil s chybou (exit {result.returncode}).")
        return

    # Parsuj cost z JSON výstupu claude
    cost_usd = 0.0
    try:
        outer = _json.loads(result.stdout)
        cost_usd = float(outer.get("total_cost_usd") or 0.0)
    except Exception:
        pass

    store.update_session(session_id, status="in_development", validation_phase="development-finish",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis())
    session = store.get_session(session_id)
    wiki_path = (session or {}).get("wiki_path")
    if wiki_path:
        full_wiki = _REPO_ROOT / wiki_path
        _append_status_history(full_wiki, "ready_for_testing")
        try:
            from status_history import update_cycle_time
            update_cycle_time(str(full_wiki))
        except Exception:
            pass
        # Zapsat náklady pouze pokud je skill nezapsal (bugy, příp. stories bez impl. plánu)
        try:
            wiki_content = full_wiki.read_text(encoding="utf-8")
            if "- Implementace:" not in wiki_content:
                _write_implement_metrics(full_wiki, cost_usd, duration_s)
        except Exception:
            pass
    store.update_session(session_id, status="done", validation_phase="ready_for_testing-start",
                         impl_plan_in_analysis=_get_impl_plan_in_analysis())


def launch_clarify_agent(session_id: str, issue_number: int, store) -> None:
    """Spustí /clarify agenta — čte pouze story soubor, bez memory systému."""
    import shutil
    store.update_session(session_id, status="analyzing", validation_phase="clarify-start")
    claude_bin = shutil.which("claude") or "/opt/homebrew/bin/claude"
    cmd = [claude_bin, "-p", f"/clarify {issue_number}", "--output-format", "json"]
    env = os.environ.copy()
    env["TF_SESSION_ID"] = session_id
    env["TF_API_PORT"] = os.environ.get("PORT", "5001")
    try:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                cwd=str(_REPO_ROOT), env=env)
    except FileNotFoundError:
        store.update_session(session_id, status="error", error=f"claude CLI nenalezeno ({claude_bin}).")
        return
    except Exception as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se spustit agenta: {e}")
        return

    if result.returncode != 0:
        store.update_session(session_id, status="error",
                             error=f"Agent /clarify skončil s chybou (exit {result.returncode}).")
        return

    store.update_session(session_id, status="done", validation_phase="clarify-finished")


def launch_analyze_agent(session_id: str, issue_number: int, store) -> None:
    """Spustí /analyze agenta a po dokončení aktualizuje session."""
    import shutil
    store.update_session(session_id, status="analyzing", validation_phase="draft-start")
    claude_bin = shutil.which("claude") or "/opt/homebrew/bin/claude"
    cmd = [claude_bin, "-p", f"/analyze {issue_number}", "--output-format", "json"]
    env = os.environ.copy()
    env["TF_SESSION_ID"] = session_id
    env["TF_API_PORT"] = "5001"
    try:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                cwd=str(_REPO_ROOT), env=env)
    except FileNotFoundError:
        store.update_session(session_id, status="error", error=f"claude CLI nenalezeno ({claude_bin}).")
        return
    except Exception as e:
        store.update_session(session_id, status="error", error=f"Nepodařilo se spustit agenta: {e}")
        return

    if result.returncode != 0:
        store.update_session(session_id, status="error",
                             error=f"Agent /analyze skončil s chybou (exit {result.returncode}).")
        return

    # Zachyť náklady z JSON výstupu a přepiš Celkem: v wiki
    total_cost_usd = 0.0
    try:
        out = _json.loads(result.stdout)
        total_cost_usd = float(out.get("total_cost_usd", 0.0) or 0.0)
    except Exception:
        pass

    # Zkontroluj výsledný stav ze wiki souboru
    session = store.get_session(session_id)
    wiki_path = (session or {}).get("wiki_path")
    if wiki_path:
        try:
            full_wiki = _REPO_ROOT / wiki_path
            body = full_wiki.read_text(encoding="utf-8")
            status_m = re.search(r"- Status:\s*([^\n]+)", body)
            wiki_status = status_m.group(1).strip() if status_m else ""
            if wiki_status == "blocked":
                conflict_m = re.search(r"## Konflikty\s*\n([\s\S]*?)(?=\n##|$)", body)
                conflict_text = conflict_m.group(1).strip() if conflict_m else "Story blokována konfliktem."
                store.update_session(session_id, status="error",
                                     validation_phase="conflict-check-failed",
                                     error=f"⚠️ Story blokována:\n{conflict_text}")
                return
            # Přepiš Celkem: skutečnými náklady ze subprocess
            if total_cost_usd > 0:
                updated = re.sub(r"- Celkem: \$[\d.]+", f"- Celkem: ${total_cost_usd:.4f}", body)
                if updated != body:
                    full_wiki.write_text(updated, encoding="utf-8")
        except Exception:
            pass

    store.update_session(session_id, status="done", validation_phase="done")


def _parse_figma_url(url: str) -> tuple[str, str | None]:
    m = re.search(r'figma\.com/(?:file|design)/([A-Za-z0-9]+)', url)
    if not m:
        raise ValueError("Neplatná Figma URL")
    file_key = m.group(1)
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    node_id = params.get("node-id", [None])[0]
    if node_id:
        node_id = node_id.replace("-", ":").split("&")[0]
    return file_key, node_id


def _fetch_figma_node(file_key: str, node_id: str | None) -> dict:
    api_key = os.environ.get("FIGMA_API_KEY", "")
    if not api_key:
        raise ValueError("FIGMA_API_KEY není nastaven v prostředí")
    if node_id:
        api_url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={urllib.parse.quote(node_id)}"
    else:
        api_url = f"https://api.figma.com/v1/files/{file_key}?depth=2"
    req = urllib.request.Request(api_url, headers={"X-Figma-Token": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read().decode())


def _extract_node_text(node: dict, depth: int = 0) -> str:
    if depth > 6:
        return ""
    ntype = node.get("type", "")
    name = node.get("name", "")
    chars = node.get("characters", "")
    prefix = "  " * depth
    parts = []
    if ntype == "TEXT" and chars:
        parts.append(f"{prefix}[TEXT] {name}: {chars!r}")
    elif name:
        parts.append(f"{prefix}[{ntype}] {name}")
    for child in node.get("children", [])[:25]:
        t = _extract_node_text(child, depth + 1)
        if t:
            parts.append(t)
    return "\n".join(parts)


def _summarize_figma_data(data: dict) -> str:
    if "nodes" in data:
        parts = []
        for node_data in data["nodes"].values():
            if node_data:
                parts.append(_extract_node_text(node_data.get("document", {})))
        return "\n\n".join(parts)
    if "document" in data:
        return _extract_node_text(data["document"])
    return str(data)[:3000]


def _fetch_figma_image(file_key: str, node_id: str) -> tuple[str, str]:
    """Vrátí (cdn_url, base64_png). Vyžaduje node_id."""
    import base64  # noqa: PLC0415
    api_key = os.environ.get("FIGMA_API_KEY", "")
    if not api_key:
        raise ValueError("FIGMA_API_KEY není nastaven v prostředí")
    api_url = (
        f"https://api.figma.com/v1/images/{file_key}"
        f"?ids={urllib.parse.quote(node_id)}&format=png&scale=1"
    )
    req = urllib.request.Request(api_url, headers={"X-Figma-Token": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = _json.loads(resp.read().decode())
    cdn_url = data.get("images", {}).get(node_id)
    if not cdn_url:
        raise ValueError("Figma nevrátilo image URL pro daný node")
    with urllib.request.urlopen(cdn_url, timeout=30) as resp:
        image_b64 = base64.b64encode(resp.read()).decode()
    return cdn_url, image_b64


def _call_claude_vision(image_path: str, prompt: str, model: str) -> dict | None:
    full_prompt = f"{prompt}\n\nCesta k obrázku: {image_path}\nPoužij Read nástroj pro načtení obrázku."
    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt, "--model", model, "--output-format", "json",
             "--no-session-persistence", "--max-budget-usd", str(_MAX_BUDGET_USD_PER_RUN),
             "--allowedTools", "Read"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=None,
            text=True, timeout=120, cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError:
        return {"error": "claude_not_found"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        outer = _json.loads(result.stdout)
    except Exception:
        return {"error": "parse_error"}
    if outer.get("is_error"):
        return {"error": outer.get("subtype", "api_error")}
    raw = outer.get("result", "").strip()
    parsed = _parse_agent_json(raw)
    if parsed.get("shows") or parsed.get("behaves"):
        return {"shows": parsed.get("shows", ""), "behaves": parsed.get("behaves", "")}
    return {"shows": raw, "behaves": ""}


def run_figma_describe(figma_url: str) -> dict | None:
    import base64, tempfile
    try:
        file_key, node_id = _parse_figma_url(figma_url)
        figma_data = _fetch_figma_node(file_key, node_id)
        node_summary = _summarize_figma_data(figma_data)[:3000]
        if not node_id:
            return {"error": "Pro načtení obrázku zadej URL s ?node-id=..."}
        cdn_url, image_b64 = _fetch_figma_image(file_key, node_id)
    except urllib.error.HTTPError as e:
        return {"error": f"Figma API vrátilo {e.code}: {e.reason}"}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Figma API chyba: {e}"}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(base64.b64decode(image_b64))
            tmp_path = tmp.name

        prompt = (
            "Jsi Product Owner. Přečti obrázek (screenshot z Figma designu) a vrať JSON se dvěma klíči.\n\n"
            "Klíč \"shows\": popis co uživatel vidí, strukturovaný podle řádků/sekcí v designu (shora dolů). "
            "Každý řádek nebo sekce = jeden krátký odstavec. Odstavce odděl prázdným řádkem (\\n\\n). "
            "Pro každý odstavec uveď co daná část obrazovky zobrazuje, jaké prvky obsahuje a v jakém jsou stavu. "
            "Piš v češtině, bez markdown.\n\n"
            "Klíč \"behaves\": pouze seznam názvů komponent jako šablona pro BO, v pořadí shora dolů. "
            "Každá položka: název komponenty, nový řádek, pomlčka, prázdný řádek. "
            "Příklad:\nNavigace\n-\n\nFormulář přihlášení\n-\n\nTlačítko Odeslat\n-\n\n"
            f"Doplňkový kontext — vrstvová struktura z Figma:\n{node_summary}\n\n"
            "Vrať pouze validní JSON objekt, žádný další text."
        )
        result = _call_claude_vision(tmp_path, prompt, _model_for_agent("product-owner"))
    finally:
        if tmp_path:
            try:
                pathlib.Path(tmp_path).unlink()
            except Exception:
                pass

    if result and "error" not in result:
        result["image_url"] = cdn_url
        result["_image_bytes"] = base64.b64decode(image_b64)
    return result


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
