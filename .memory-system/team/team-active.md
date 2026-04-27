# Team — aktivní agenti pro tento projekt

Per-projekt konfigurace, kteří agenti jsou v aktuální iteraci aktivní.

> Tento soubor edituje Business Owner při setup projektu nebo při přechodu mezi fázemi.

## Aktivní v této fázi

| Agent | Aktivní | Note |
|---|---|---|
| product-owner | ✅ | Vždy aktivní |
| conflict-detector | ✅ | Vždy aktivní |
| architekt | ✅ | Vždy aktivní |
| backend-developer | ✅ | Aktivní pokud projekt má backend |
| frontend-developer | ✅ | Aktivní pokud projekt má frontend |
| code-reviewer | ✅ | Vždy aktivní |

## Volitelní (fáze 2 — INACTIVE v této verzi memory systému)

| Agent | Aktivní | Note |
|---|---|---|
| ux-designer | ❌ | Nedefinován v této verzi |
| qa-inzenyr | ❌ | Nedefinován v této verzi |
| security-auditor | ❌ | Nedefinován v této verzi |
| dokumentarista | ❌ | Nedefinován v této verzi |
| ops-monitor | ❌ | Nedefinován v této verzi |

## Pravidla

- **Kritická pětice** (PO, Conflict Detector, Architekt, Code Reviewer) je vždy aktivní. Bez nich pipeline nefunguje.
- **Backend Developer / Frontend Developer**: aktivní podle scope projektu. Pokud projekt nemá frontend (např. čistý API service), Frontend Developer se vypne. Pokud projekt nemá backend (např. statická SPA proti existujícímu API), Backend Developer se vypne.
- **Volitelní agenti**: aktivují se postupně, když data ukáží reálnou potřebu (např. > 20 % bugů uniká přes Code Reviewera = potřeba QA agenta).

## Spouštění

| Story scope | Aktivovaní developeři |
|---|---|
| BE only (např. nový endpoint, migrace) | Backend Developer |
| FE only (např. nová stránka proti existujícím endpointům) | Frontend Developer |
| Full-stack (nová feature s BE i FE) | Backend Developer → Frontend Developer (sekvenčně, BE první aby FE měl proti čemu pracovat) |

Architekt v `Implementation Plan` označí, které části jsou BE a FE — určuje to, kdo bude story implementovat.

## Kdy aktualizovat tento soubor

- Při založení nového projektu — Business Owner zvolí, kteří agenti jsou aktivní podle scope.
- Při fázovém přechodu — když validovaná data ukážou potřebu nového agenta, Business Owner ho aktivuje.
- Při rozhodnutí o "agent retreat" — pokud agent není přínosný (false positives, zpomalení), deaktivuje se.

Každá změna tohoto souboru by měla být doprovázena ADR s odůvodněním.
