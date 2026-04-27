# Agent Memory Contracts

Každý agent má přesně definováno co smí číst a co smí psát.
Psaní do nepovolené vrstvy je zakázáno.

---

## Product Owner

**Čte:**
- V1 — celé (`memory-system/V1 - static context/`)
- V2 — `story_register.md`

**Píše:**
- V2 → `story_register.md` (nová story, změna statusu)

**Nepíše do:** domain_model, V3, V4

---

## Conflict Detector

**Čte:**
- V2 — `domain_model.md` pouze sekce dle `reads_sections` nové story
- V2 — `story_register.md`
- V4 — `cross_links.json` (hint — vždy křížově ověř proti story_register)
- nová story (draft)

**Píše:**
- V4 → `cross_links.json` (update závislostí po průchodu)
- výstup: `OK` nebo `NOT OK + důvody` předaný zpět Product Ownerovi

**Nepíše do:** V1, V2, V3

---

## Architekt

**Čte:**
- V1 — celé
- V2 — `domain_model.md` pouze sekce dle `reads_sections` story
- V2 — `story_register.md`
- aktuální story (status: `ready-for-arch`)

**Píše:**
- V2 → `domain_model.md` (pouze sekce dle `writes_sections` story)
- V2 → `story_register.md` (update statusu na `arch-approved`)

**Nepíše do:** V3, V4

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

**Nepíše do:** žádné paměťové vrstvy — píše pouze kód / design

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
- změněné části V2 (co Architect upravil)

**Píše:**
- V2 → `domain_model.md` (stabilizovaná znalost po implementaci)
- V3 → `changelog.jsonl` (log změn, až bude aktivní)

**Nepíše do:** V4

---

## Ops Monitor

**Čte:**
- V2 — relevantní sekce dle sledované oblasti

**Píše:**
- V3 → `changelog.jsonl` (anomálie, incidenty — až bude aktivní)

**Nepíše do:** V1, V2, V4
