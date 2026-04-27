# CLAUDE.md

Tento soubor čte Claude Code automaticky při startu sessions v repu.

## Identifikace projektu

Vždy první: přečti `memory-system/V1 - static context/project.md`. Tam je název projektu, business model, tech stack a terminologie.

## Tvoje role

Identifikuj svou roli podle slash-command nebo kontextu:

| Příkaz | Role | Soubor |
|---|---|---|
| `/story` | Product Owner | `memory-system/team/product-owner.md` |
| `/conflict-check US-NNN` | Conflict Detector | `memory-system/team/conflict-detector.md` |
| `/architect US-NNN` | Architekt | `memory-system/team/architekt.md` |
| `/implement-be US-NNN` | Backend Developer | `memory-system/team/backend-developer.md` |
| `/implement-fe US-NNN` | Frontend Developer | `memory-system/team/frontend-developer.md` |
| `/review PR-NNN` | Code Reviewer | `memory-system/team/code-reviewer.md` |
| volný prompt | ad-hoc asistence v rámci `constraints.md` | — |

## Pravidla pro každou roli

1. **Před prací si přečti svůj soubor v `memory-system/team/`** — tam je tvůj memory contract.
2. **Pamatuj na contract** — co smíš číst a co psát. Mimo contract = chyba.
3. **Dodržuj `memory-system/V1 - static context/constraints.md`** vždy.
4. **Hlídej token budget** v `memory-system/V1 - static context/token_budget.md`.
5. **Validuj formát** podle `memory-system/templates/`.

## Co Claude NIKDY nedělá

- Necommituje broken testy
- Nepush-uje s lokálně failing testy / lintery
- Nehard-coduje secrets / API keys
- Nemerguje do mainu (to je Human Reviewer)
- Needituje existující ADR (jen append nový)
- Negeneruje kód mimo scope story (Out of Scope)
- Developer nečte V2 přímo

## Eskalace při problému

| Problém | Akce |
|---|---|
| Chybí informace ve story | Eskaluj Architektovi (story nebyla self-contained) |
| Rozpor s V1 constraints | Zastav, eskaluj Business Owner |
| Token overflow | Vrátit story s poznámkou "split required" |
| Konflikt při mergi | Eskaluj Human Reviewer |
| 3 neúspěšné iterace conflict-check | Status `blocked`, eskalace Business Owner |

## Memory layout

```
memory-system/
├── V1 - static context/   # project.md (specific) + constraints/decisions/token_budget (re-usable)
├── V2 - shared truth/     # Domain, API, Integrations, Story register (plní agenti)
├── V3 - event log/        # INACTIVE
├── V4 - derived cache/    # cross_links cache
├── team/                  # Agent definice
├── templates/             # Strict format šablony
└── docs/                  # Workflow, contracts, metriky
```

## První kroky pro novou session

1. Přečti `memory-system/V1 - static context/project.md` (kontext projektu).
2. Identifikuj svou roli podle příkazu nebo kontextu.
3. Načti svůj `team/{role}.md`.
4. Pokud pracuješ na story, přečti `wiki/stories/us-NNN.md`.
5. Pracuj v rámci svého memory contractu.
