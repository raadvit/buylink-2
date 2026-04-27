# Memory System

Re-usable memory systém pro AI-first development. Kopíruje se do každého projektu firmy a vyplní se jediný projekt-specific soubor: `V1 - static context/project.md`.

## Princip

**Business Owner zadá user story → AI agenti ji validují, navrhnou, implementují → vývojář dělá pouze code review a finální merge.**

## Setup nového projektu

1. Zkopíruj `memory-system/` do kořene projektu.
2. Vyplň `V1 - static context/project.md` (název, business model, tech stack, terminologie).
3. Zbytek je projekt-agnostic — neupravuj.
4. V2 soubory startují prázdné. Architekt je naplňuje při průchodu prvními stories.

## Struktura

```
memory-system/
├── V1 - static context/        # Read-only kontext
│   ├── project.md              # ⚠️ JEDINÝ projekt-specific soubor (vyplní Business Owner)
│   ├── constraints.md          # Globální pravidla pro agenty (re-usable)
│   ├── decisions.md            # ADR (append-only, plní se za běhu)
│   └── token_budget.md         # Token limity per agent run
│
├── V2 - shared truth/          # Single source of truth (plní agenti)
│   ├── domain.md               # Entity, atributy, stavy, operations
│   ├── api.md                  # API kontrakt (endpointy, payloady)
│   ├── integrations.md         # Externí systémy
│   └── story_register.md       # Registr všech stories
│
├── V3 - event log/             # INACTIVE (git history zatím stačí)
│   └── changelog.jsonl
│
├── V4 - derived cache/         # Generovaný cache (Conflict Detector)
│   └── cross_links.json
│
├── team/                       # Definice agentů
│   ├── product-owner.md
│   ├── conflict-detector.md
│   ├── architekt.md
│   ├── backend-developer.md
│   ├── frontend-developer.md
│   ├── code-reviewer.md
│   └── team-active.md          # Konfigurace, kteří agenti jsou v projektu aktivní
│
├── templates/                  # Strict format šablony
│   ├── story-template.md
│   ├── domain-entity-template.md
│   ├── api-endpoint-template.md
│   └── integration-template.md
│
└── docs/
    ├── agents.md               # Workflow obou fází + handshake
    ├── memory-system.md        # Architektura paměťových vrstev
    ├── agent-memory-contract.md # Read/write kontrakty
    ├── token-strategy.md       # Modely per agent
    ├── metrics.md              # Měření úspěchu
    └── worktrees.md            # Paralelní implementace
```

## Klíčové principy

1. **V2 je jediná pravda.** Pokud V3/V4 odporují, vyhrává V2.
2. **Agent čte minimum.** Jen sekce uvedené ve `reads` story.
3. **Developer nečte V2 přímo.** Architekt mu připraví self-contained kontext ve story.
4. **Story je self-contained snapshot** po Architektově fázi.
5. **Strict format > volná próza.** Strojově validovatelné.
6. **Append-only `decisions.md`.** Změna rozhodnutí = nový ADR s `Supersedes`.
7. **V2 startuje prázdná.** Žádné předdefinované entity, API, integrace.

## Status flow story

```
draft → conflict-check → ready-for-arch → validated 
   → in_development → ready_for_review → ready_for_testing 
   → done
```

Plus koncové stavy: `blocked`, `cancelled`.

## Aktivní agenti

Definováno v `team/team-active.md` per projekt. Default:

- Product Owner
- Conflict Detector
- Architekt
- Backend Developer
- Frontend Developer
- Code Reviewer

Volitelní (v této verzi nedefinováni, fáze 2): UX Designer, QA Inženýr, Security Auditor, Dokumentarista, Ops Monitor.

## Kde začít

| Co potřebuješ | Soubor |
|---|---|
| Setup projektu | `V1 - static context/project.md` |
| Workflow agentů | `docs/agents.md` |
| Architektura paměti | `docs/memory-system.md` |
| Co kdo smí číst/psát | `docs/agent-memory-contract.md` |
| Modely a tiery | `docs/token-strategy.md` |
| Metriky | `docs/metrics.md` |
| Konfigurace agentů | `team/*.md` |
