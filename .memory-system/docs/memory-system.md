# Memory System

## Cíl

Minimalizovat spotřebu tokenů, udržet vysoký kontext projektu, zabránit duplicitnímu uvažování agentů, a hlavně **zajistit, že agent dostává přesně to, co potřebuje**.

## Principy

1. **Agent čte jen to, co potřebuje** — ne celou historii.
2. **V2 je jediná pravda.** V3 a V4 jsou pomocné, nikdy nejsou zdrojem rozhodnutí.
3. **Agent píše pouze do vrstvy ve svém kontraktu.**
4. **Strict format > volná próza** — strojově validovatelné, levnější tokeny, méně dvojznačnosti.
5. **Story self-contained po fázi 1** — Developer nečte V2 přímo.
6. **V2 startuje prázdná** — žádné předdefinované entity, API, integrace. Agenti naplňují podle stories.

## Re-use přes projekty

Memory systém je **re-usable napříč projekty firmy**. Každý projekt má vlastní instanci:

```
project-A/
└── memory-system/  (zkopírováno z template, vyplněn project.md)

project-B/
└── memory-system/  (zkopírováno z template, vyplněn project.md)
```

**Jediný projekt-specific soubor** je `V1/project.md`. Vše ostatní (agenti, kontrakty, šablony, V1 pravidla) je sdílené.

V kódu agentů se na cesty odkazuje relativně (`memory-system/V1 - static context/...`), takže se memory systém nemusí jinak konfigurovat.

---

## V1 — Static Context

`memory-system/V1 - static context/`

| Soubor | Obsah | Re-usable? |
|---|---|---|
| `project.md` | název, business model, tech stack, terminologie | ❌ Projekt-specific |
| `constraints.md` | globální omezení pro všechny agenty | ✅ Re-usable |
| `decisions.md` | ADR (append-only, plní se postupně) | ❌ Projekt-specific |
| `token_budget.md` | input limity per agent run | ✅ Re-usable (orientační) |

**Čte:** každý agent před zahájením práce (relevantní části)
**Píše:** Architekt do `decisions.md` (append-only). Ostatní jen ručně Business Owner.

⚠️ Při rozporu s V1 agent zastaví práci a eskaluje na Human review.

⚠️ `decisions.md` je **append-only**.

---

## V2 — Shared Truth (read + write)

`memory-system/V2 - shared truth/`

| Soubor | Obsah |
|---|---|
| `domain.md` | entity, atributy, stavy, rules, operations |
| `api.md` | endpointy, payloady, response codes |
| `integrations.md` | externí systémy, webhooky, providery |
| `story_register.md` | seznam všech stories + statusy |

### V2 startuje prázdná

První story projektu narazí na prázdnou V2. Architekt naplní:
- v `domain.md` první entity podle scope story
- v `api.md` první endpointy
- v `integrations.md` první providery (pokud jsou)
- volitelně v `domain.md` / `api.md` globální konvence projektu (často první ADR)

### Sekční tagging

Každý soubor používá tagging:
```
<!-- SECTION: section_name -->
...obsah...
<!-- /SECTION: section_name -->
```

Agent čte **pouze sekce relevantní pro úkol** — určeno polem `reads` a `writes` ve story.

### Limity

- max **1500 tokenů na sekci**. Pokud naroste, povinné rozdělení.

### Kdo čte / píše

| Soubor | Čte | Píše |
|---|---|---|
| `domain.md` | Architekt, Conflict Detector | Architekt |
| `api.md` | Architekt, Conflict Detector | Architekt |
| `integrations.md` | Architekt, Conflict Detector | Architekt |
| `story_register.md` | Product Owner, Conflict Detector, Architekt, Developeři, Code Reviewer | Product Owner, Conflict Detector, Architekt, Developeři, Code Reviewer |

V2 je jediná vrstva, které agenti **věří**. Strojově čitelná, vždy aktuální.

---

## V3 — Event Log 🔴 INACTIVE

`memory-system/V3 - event log/changelog.jsonl`

> **Status: INACTIVE** — git history nad V2 zatím plní stejnou funkci.

Až bude aktivní, log formát:
```json
{
  "ts": "2026-04-26T10:30:00Z",
  "story_id": "US-007",
  "agent": "Architekt",
  "action": "update",
  "file": "domain.md",
  "section": "orders",
  "summary": "Přidán stav CANCELLED do Order"
}
```

Aktivace V3 přijde s prvním Dokumentaristou ve fázi 2.

---

## V4 — Derived Cache (aktivní)

`memory-system/V4 - derived cache/cross_links.json`

Předpočítané závislosti mezi stories a V2 sekcemi. Pomáhá Conflict Detectorovi rychleji najít, co číst.

```json
{
  "stories": {
    "US-007": {
      "depends_on": ["US-002", "US-006"],
      "affects_sections": ["domain:orders", "domain:payments", "api:orders"]
    }
  },
  "sections": {
    "domain:orders": {
      "affected_by": ["US-007", "US-014"],
      "dependents": ["US-008", "US-009"]
    }
  }
}
```

### Invalidace

V4 **není aktivně invalidována**. Conflict Detector vždy cross-checkuje proti live `story_register.md`. Stale záznamy = pomalejší průchod, ne špatné výsledky.

### Kdo čte / píše

- **Čte:** Conflict Detector
- **Píše:** Conflict Detector (po každém průchodu update)

---

## Read strategie agentů

| Agent | Čte | Nečte |
|---|---|---|
| Product Owner | V1 + V2/story_register | V2 mimo register, V3, V4 |
| Conflict Detector | V2 [reads+writes] + story_register + V4 | V1, celý V2 |
| Architekt | V1 + V2 [reads+writes] + story | V3, V4 |
| Backend Developer | story (self-contained) + V1/project + V1/constraints | V2 přímo, V3, V4 |
| Frontend Developer | story (self-contained) + V1/project + V1/constraints + style-guide | V2 přímo, V3, V4 |
| Code Reviewer | diff + story (AC, Plan, Out of Scope) + V1/constraints + V1/project | V2 přímo, V3, V4 |

🔑 **Klíčová úspora:** Developeři nečtou V2 přímo. Architekt jim připraví výtah ve story.

## Write strategie agentů

| Agent | Píše do | Pozn. |
|---|---|---|
| Product Owner | V2/story_register | Nový řádek + status update |
| Conflict Detector | V2/story_register, V4 | Status, affected_stories, cache |
| Architekt | V1/decisions (append), V2/domain+api+integrations [writes], V2/story_register | Append-only ADR |
| Backend Developer | žádné paměťové vrstvy (jen kód a story body) | Story Implementation Notes (BE) + PR Link |
| Frontend Developer | žádné paměťové vrstvy (jen kód a story body) | Story Implementation Notes (FE) + PR Link |
| Code Reviewer | V2/story_register (status), story frontmatter | Jen status + Review Result |

## Validace zápisů

Každý zápis do V2 spouští validační skript:
- `domain.md` — každá entita má povinné sekce (Atributy, Operations, Invariants, Vztahy)
- `api.md` — každý endpoint má Method, Path, Auth, Request/Response, Errors
- `integrations.md` — každá integrace má Účel, Auth, Status, Error handling
- `story_register.md` — všechny řádky mají povinné sloupce
- story soubor — frontmatter má povinná pole pro daný status

Pre-commit hook odmítne commit, který validaci neprojde.

## Velikost a růst

V průběhu projektu V2 roste. Doporučení:
- pokud sekce > 1500 tokenů → rozdělit (např. `orders` → `orders-core`, `orders-payments`)
- pokud V2 přeroste typický token budget Architekta → rekalibrovat budget v `token_budget.md`
- pokud `decisions.md` přeroste 100+ ADR, rozdělit do `decisions/` adresáře po doménách (vyžaduje ADR meta)

## Backup a versioning

V1 + V2 jsou v gitu. Každá změna = commit s popisem. Git history nahrazuje V3 ve fázi pilotu.

Doporučení: tag v gitu při milestonech (`v0.1-pilot-end`, `v0.2-fáze-2-start`).
