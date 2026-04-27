# Agent Memory System

## 🎯 Cíl
Minimalizovat spotřebu tokenů, udržet vysoký kontext projektu a zabránit duplicitnímu uvažování agentů.

## Principy
- Každý agent čte **pouze to co potřebuje** — ne celou historii
- V2 je jediná pravda. Pokud si V2 a V3 odporují, vyhrává V2.
- V3 a V4 jsou pomocné vrstvy — nikdy nejsou zdrojem rozhodnutí
- Agent nikdy nepíše do vrstvy, která mu nepřísluší (viz Agent Memory Contracts)

---

# 🧱 Paměťové vrstvy

## V1 — Static Context (read-only, nikdy se nemění)

Soubory (`memory-system/V1 - static context/`):
- `context.md` — role, pojmy, projekt, business model
- `constraints.md` — globální omezení pro všechny agenty
- `story_template.md` — šablona pro tvorbu user stories
- `decisions.md` — business rozhodnutí & Architecture Decision Records (ADR)

**Čte:** každý agent před zahájením práce  
**Píše:** nikdo během runtime — pouze ruční změna člověkem  
**Vlastník:** Business Owner — jediný kdo autoritativně mění obsah V1

> ⚠️ Pokud agent zjistí konflikt s V1, zastaví práci a eskaluje na Human review.

---

## V2 — Shared Truth (read + write, single source of truth)

Soubory:
- `domain_model.md` — entity, atributy, stavy, rules, API kontrakt, integrace
- `story_register.md` — seznam všech stories + jejich status

**Struktura domain_model.md používá sekční tagging:**
```
<!-- SECTION: orders -->
...obsah...
<!-- /SECTION: orders -->
```

Každý agent čte **pouze sekce relevantní pro svůj úkol** — určeno polem `reads_sections` ve story.

**Čte:** Product Owner, Architect, Conflict detector (selektivně dle affected_sections)  
**Píše:** Architect (domain_model + story_register), Product Owner (story_register)  

> ✅ Toto je jediný soubor kterému agenti "věří". Vždy aktuální, strojově čitelný.

---

## V3 — Event Log (append-only) 🔴 VYPNUTO

> **Status: INACTIVE** — git history na V2 souborech prozatím plní stejnou funkci.

Soubory (až bude aktivní):
- `changelog.jsonl` — každá změna V2 se loguje jako JSON záznam

Formát záznamu:
```json
{
  "ts": "2025-01-15T10:30:00Z",
  "story_id": "STORY-12",
  "agent": "Architect",
  "action": "update",
  "section": "orders",
  "summary": "Přidán stav CANCELLED do Order.status"
}
```

**Čte:** Conflict detector (při hledání původu konfliktu)  
**Píše:** Dokumentarista (po každé změně V2)

---

## V4 — Derived Cache (generovaný, nikdy není source of truth) — AKTIVNÍ

Soubory (`memory-system/V4 - Derived Cache/`):
- `cross_links.json` — předpočítané závislosti mezi stories a sekcemi V2

Příklad obsahu:
```json
{
  "STORY-15": {
    "depends_on": ["STORY-8", "STORY-12"],
    "affects_sections": ["orders", "payments"]
  }
}
```

**Přínos:** Conflict detector nemusí procházet celý story_register pokaždé znovu — podívá se do cache a ví co číst.

**Invalidace:** V4 není aktivně invalidována. Conflict Detector musí vždy křížově ověřit nalezené záznamy proti live `story_register.md`. Stale záznamy ignoruj — stale cache = pomalejší průchod, ne špatné výsledky.

**Čte:** Conflict detector  
**Píše:** Conflict detector (po každém průchodu)

---

# 🔁 Read strategie agentů

| Agent | Čte | Nepotřebuje |
|---|---|---|
| Product Owner | V1 + V2 (story_register) | V3, V4 |
| Conflict detector | V2 [affected_sections] + story_register + V4 | V1, celý V2, V3 |
| Architect | V1 + V2 [affected_sections] + nová story | V3, V4 |
| Backend / Frontend Developer | story + implementační plán od Architekta | V1, V2 přímo |
| Code Reviewer | diff + story (acceptance criteria) | V1, V2, V3, V4 |
| Dokumentarista | změněné části V2 + story | — |

> 🔑 Klíčová úspora: Developer **nečte V2 přímo**. Architect mu připraví potřebný kontext v implementačním plánu.

---

# ✍️ Write strategie agentů

Viz `agent_memory_contract.md` pro kompletní kontrakt.

| Agent | Píše do |
|---|---|
| Product Owner | V2 (story_register) |
| Architect | V2 (domain_model + story_register) |
| Conflict detector | V4 (cross_links) |
| Dokumentarista | V2 (domain_model), V3 (changelog) |
