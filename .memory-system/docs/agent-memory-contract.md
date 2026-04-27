# Agent Memory Contracts

Každý agent má přesně definováno **co smí číst a co smí psát**.

Zápis do nepovolené vrstvy = kritická chyba. Agent zastaví práci a eskaluje.

---

## Product Owner

**Čte:**
- `memory-system/V1 - static context/` — celé (project, constraints, decisions, token_budget)
- `memory-system/V2 - shared truth/story_register.md`

**Píše:**
- `memory-system/V2 - shared truth/story_register.md` (nový řádek, změna statusu)
- `wiki/stories/us-NNN.md` (nová story dle template)

**Nepíše do:** V1, `domain.md`, `api.md`, `integrations.md`, V3, V4

---

## Conflict Detector

**Čte:**
- `memory-system/V2 - shared truth/domain.md` — pouze sekce dle `reads`+`writes` aktuální story
- `memory-system/V2 - shared truth/api.md` — pouze sekce dle `reads`+`writes`
- `memory-system/V2 - shared truth/integrations.md` — pouze sekce dle `reads`+`writes`
- `memory-system/V2 - shared truth/story_register.md`
- `memory-system/V4 - derived cache/cross_links.json`
- aktuální story (draft / conflict-check)

**Píše:**
- `memory-system/V4 - derived cache/cross_links.json` (po každém průchodu)
- `memory-system/V2 - shared truth/story_register.md` (status, updated_at, affected_stories)
- frontmatter aktuální story (status, affected_stories, conflict_check_iterations)

**Výstup mimo paměť:** seznam konfliktů (NOT OK) v handshake formátu, předaný zpět Product Ownerovi

**Nepíše do:** V1, `domain.md`, `api.md`, `integrations.md` (těla souborů), V3

---

## Architekt

**Čte:**
- `memory-system/V1 - static context/` — celé
- `memory-system/V2 - shared truth/domain.md` — sekce dle `reads`+`writes` story
- `memory-system/V2 - shared truth/api.md` — sekce dle `reads`+`writes`
- `memory-system/V2 - shared truth/integrations.md` — sekce dle `reads`+`writes`
- `memory-system/V2 - shared truth/story_register.md`
- aktuální story (status: `ready-for-arch`)

**Píše:**
- `memory-system/V1 - static context/decisions.md` — **pouze append** nových ADR
- `memory-system/V2 - shared truth/domain.md` — pouze sekce dle `writes`
- `memory-system/V2 - shared truth/api.md` — pouze sekce dle `writes`
- `memory-system/V2 - shared truth/integrations.md` — pouze sekce dle `writes`
- `memory-system/V2 - shared truth/story_register.md` (status, updated_at)
- `wiki/stories/us-NNN.md` — Architecture Notes, Domain/API/Integration Changes, Implementation Plan, Manuální QA scénář

**Nepíše do:** `V1/project.md`, `V1/constraints.md`, `V1/token_budget.md`, V3, V4

⚠️ **Append-only `decisions.md`:** Validační hook odmítne commit, který modifikuje řádky existujícího ADR.

---

## Backend Developer

**Čte:**
- `wiki/stories/us-NNN.md` — finální validated story (single source of truth)
- `memory-system/V1 - static context/project.md` — tech stack, konvence
- `memory-system/V1 - static context/constraints.md` — globální pravidla
- existující kód v repu

**Nečte (důležité!):**
- `V2/domain.md`, `V2/api.md`, `V2/integrations.md` — **přímo nečte**, vše inline ve story
- `V1/decisions.md` — Architekt vyextrahoval relevantní

**Píše:**
- BE kód, testy, migrace v repu
- `wiki/stories/us-NNN.md` — Implementation Notes (BE část), PR Link, status
- `memory-system/V2 - shared truth/story_register.md` (status, updated_at)

**Nepíše do:** V1, V2 mimo story_register, V3, V4

---

## Frontend Developer

**Čte:**
- `wiki/stories/us-NNN.md` — finální validated story
- `memory-system/V1 - static context/project.md` — tech stack, konvence
- `memory-system/V1 - static context/constraints.md` — globální pravidla
- `wiki/style-guide/` — design systém (pokud existuje)
- existující FE kód v repu

**Nečte (důležité!):**
- `V2/domain.md`, `V2/api.md`, `V2/integrations.md` — přímo nečte
- BE kód detailně (jen kontrakt přes API Changes ze story)
- `V1/decisions.md`

**Píše:**
- FE kód, testy v repu
- `wiki/stories/us-NNN.md` — Implementation Notes (FE část), PR Link, status
- `memory-system/V2 - shared truth/story_register.md` (status, updated_at)

**Nepíše do:** V1, V2 mimo story_register, V3, V4

---

## Code Reviewer

**Čte:**
- diff PR (změněné soubory)
- `wiki/stories/us-NNN.md` — pouze sekce Acceptance Criteria, Implementation Plan, Out of Scope
- `memory-system/V1 - static context/constraints.md`
- `memory-system/V1 - static context/project.md`

**Nečte:** zbytek V1, V2 (kdyby potřeboval, story nebyla self-contained — vrátit Architektovi)

**Píše:**
- GitHub PR review komentáře (APPROVE / CHANGES NEEDED)
- `memory-system/V2 - shared truth/story_register.md` (status, updated_at)
- frontmatter aktuální story (status, Review Result, Review Notes)

**Nepíše do:** V1, V2 mimo story_register a story frontmatter, V3, V4

---

## Volitelní agenti (fáze 2 — INACTIVE v této verzi)

V této verzi memory systému nejsou definováni. Aktivace přijde s firemním rozhodnutím a doplněním kontraktů:

- UX Designer
- QA Inženýr
- Security Auditor
- Dokumentarista
- Ops Monitor

Pravidla pro doplnění:
- Každý nový agent musí mít jasně definovaný Memory Contract (read/write).
- Pokud má psát do V2, musí být specifikováno, do kterých sekcí a kdy.
- Pokud konflikt se zápisy Architekta, musí být pravidlo (např. "Dokumentarista píše po Architektovi a jen pokud realita ≠ návrh").

---

## Validace kontraktů

CI / pre-commit kontroluje:
- agent při zápisu loguje, do jakého souboru zapisuje
- pokud zápis je mimo kontrakt → odmítnutí commitu + alert
- audit log: `metrics/contract_violations.jsonl`

## Co se děje při porušení

1. **Detekce** — validační skript nebo pre-commit hook zjistí porušení.
2. **Zastavení** — agent nepokračuje, žádný další zápis.
3. **Eskalace** — Human review s logem porušení.
4. **Postmortem** — proč k tomu došlo, jak upravit prompt agenta.
