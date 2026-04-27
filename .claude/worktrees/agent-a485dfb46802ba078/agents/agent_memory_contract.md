# Agent Memory Contracts

Každý agent má přesně definováno co smí číst a co smí psát.
Psaní do nepovolené vrstvy je zakázáno.

---

## Routing paměťového systému dle epicu

Agenti určí správný paměťový systém podle pole `Epic` v user story:

| Epic | Paměťový systém | Kořenová cesta |
|---|---|---|
| `EP-01 Task-forge` | task-forge | `memory-system/task-forge/` |
| jakýkoli jiný epic | project | `memory-system/project/` |

**Sdílené soubory** (čtou oba systémy, nikdo nepíše):
- `memory-system/shared/constraints.md` — globální omezení
- `memory-system/shared/story_template.md` — šablona story

V kontraktech níže `{MS}` = kořenová cesta dle epicu výše.

---

## Product Owner

**Čte:**
- `{MS}/V1 - static context/` — celé
- `memory-system/shared/constraints.md`
- `{MS}/V2 - Shared Truth/story_register.md`

**Píše:**
- `{MS}/V2 - Shared Truth/story_register.md` (nová story, změna statusu)

**Nepíše do:** domain_model, V3, V4

---

## Conflict Detector

**Čte:**
- `{MS}/V2 - Shared Truth/domain_model.md` pouze sekce dle `reads_sections` nové story
- `{MS}/V2 - Shared Truth/story_register.md`
- nová story (draft)

**Píše:**
- výstup: `OK` nebo `NOT OK + důvody` předaný zpět Product Ownerovi

**Nepíše do:** V1, V2, V3

---

## Architekt

**Čte:**
- `{MS}/V1 - static context/` — celé
- `memory-system/shared/constraints.md`
- `{MS}/V2 - Shared Truth/domain_model.md` pouze sekce dle `reads_sections` story
- `{MS}/V2 - Shared Truth/story_register.md`
- aktuální story (status: `ready-for-arch`)

**Píše:**
- `{MS}/V1 - static context/decisions.md` (pouze append — nové ADR záznamy; nikdy neupravuje existující)
- `{MS}/V2 - Shared Truth/domain_model.md` (pouze sekce dle `writes_sections` story)
- `{MS}/V2 - Shared Truth/story_register.md` (update statusu na `arch-approved`)

**Nepíše do:** V1 context.md, shared/constraints.md, V3

---

## Backend Developer

**Čte:**
- story (finální, arch-approved)
- implementační plán od Architekta (kontext připravený, ne V2 přímo)

**Nepíše do:** žádné paměťové vrstvy — píše pouze kód

---

## Frontend Developer / UX Designer

**Čte:**
- story (finální, arch-approved)
- implementační plán od Architekta
- `docs/components/index.md` a dotčené spec soubory
- `wiki/style-guide/styles.css` (jen pro EP-01 Task-forge)

**Nepíše do:** žádné paměťové vrstvy — píše kód / design; aktualizuje `docs/components/`

---

## Code Reviewer

**Čte:**
- diff (změněné soubory)
- story — pouze acceptance criteria

**Nepíše do:** žádné paměťové vrstvy — výstup je APPROVE nebo CHANGES NEEDED

---

## QA Inženýr

**Čte:**
- story — acceptance criteria + test cases
- výstup implementace (větev / worktree)

**Nepíše do:** žádné paměťové vrstvy — výstup je PASS nebo FAIL

---

## Security Auditor

**Čte:**
- story
- dotčené části kódu

**Nepíše do:** žádné paměťové vrstvy — výstup je PASS nebo FINDINGS

---

## Dokumentarista

**Čte:**
- story (finální)
- změněné části `{MS}/V2 - Shared Truth/domain_model.md`

**Píše:**
- `{MS}/V2 - Shared Truth/domain_model.md` (stabilizovaná znalost po implementaci)
- `{MS}/V3 - event log/changelog.jsonl` (log změn, až bude aktivní)

**Nepíše do:** V1, shared

---

## Ops Monitor

**Čte:**
- `{MS}/V2 - Shared Truth/` — relevantní sekce

**Píše:**
- `{MS}/V3 - event log/changelog.jsonl` (anomálie, incidenty — až bude aktivní)

**Nepíše do:** V1, V2, shared
