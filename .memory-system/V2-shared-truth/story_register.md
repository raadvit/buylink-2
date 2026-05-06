# Story Register

Registr všech user stories projektu. Source of truth pro status každé story.

> **Tento soubor startuje prázdný (jen hlavička tabulky).** Product Owner přidává řádky postupně.

## Pravidla pro tento soubor

- **Format:** strojově parsovatelná tabulka v Markdownu. Žádná volná próza.
- **Update:**
  - Product Owner přidává řádky a updatuje statusy
  - Conflict Detector / Architekt / Backend Developer / Frontend Developer / Code Reviewer mění `status` a `updated_at` při průchodu pipeline
- **Validace:** pre-commit hook ověří, že každý řádek má všechny povinné sloupce a že hodnoty `status` jsou z povolené množiny.

## Sloupce

| Sloupec | Popis | Hodnoty / format |
|---|---|---|
| `id` | Identifikátor story | `US-NNN` (NNN tříciferné, padding nulami) |
| `title` | Krátký název | string, max 80 znaků |
| `epic` | Doménová oblast nebo modul | např. `EP-XX` (volný text, dle `project.md`) |
| `status` | Aktuální stav | viz status flow níže |
| `reads` | Sekce V2, které story čte | `domain:section, api:section` (čárkou oddělené) |
| `writes` | Sekce V2, které story zapisuje / mění | stejný formát |
| `depends_on` | Story IDs, na kterých závisí | `US-XXX, US-YYY` nebo `none` |
| `created_at` | Datum vytvoření | ISO 8601 (YYYY-MM-DD) |
| `updated_at` | Datum poslední změny statusu | ISO 8601 |
| `assigned_dev` | Komu je story přiřazena | `agent` nebo `human-{name}` nebo `none` |
| `pr_url` | URL PR (po implementaci) | URL nebo `none` |

## Status flow

```
draft → conflict-check → ready-for-arch → validated 
   → in_development → ready_for_review → ready_for_testing 
   → done
```

Plus koncové: `blocked`, `cancelled`.

| Status | Význam | Kdo nastavuje |
|---|---|---|
| `draft` | PO právě napsal | Product Owner |
| `conflict-check` | Čeká na Conflict Detectora | Product Owner |
| `ready-for-arch` | Bez konfliktů, čeká na Architekta | Conflict Detector |
| `validated` | Architekt doplnil impl. plán, story je ready | Architekt |
| `in_development` | Developer pracuje | Backend / Frontend Developer (start) |
| `ready_for_review` | Developer hotov, čeká na Code Reviewera | Backend / Frontend Developer |
| `ready_for_testing` | Code Reviewer APPROVE, čeká na manuální QA | Code Reviewer |
| `done` | Manuální QA prošel + merge do main | Human Reviewer |
| `blocked` | Eskalace na Business Ownera | Conflict Detector / Architekt |
| `cancelled` | Story zrušena | Business Owner / Product Owner |

---

## Registr

| id | title | epic | status | reads | writes | depends_on | created_at | updated_at | assigned_dev | pr_url |
|---|---|---|---|---|---|---|---|---|---|---|

---

## Stats

> Generováno automaticky validačním skriptem nebo dashboardem.

- Total stories: 0
- By status: —
- Critical path: —

## Workflow

1. **Business Owner** předá záměr Product Ownerovi.
2. **Product Owner** přidá řádek do tabulky se statusem `draft`, vyplní `reads` / `writes` / `depends_on`. Vytvoří story soubor v `wiki/stories/us-NNN.md` a GitHub issue.
3. **Conflict Detector** (auto trigger): mění status na `conflict-check`, po průchodu na `ready-for-arch` (OK) nebo zpět na `draft` s důvody (NOT OK).
4. **Architekt** (auto trigger po `ready-for-arch`): mění na `validated`.
5. **Trigger `/implement-be`** nebo `/implement-fe`**: nastaví `in_development`, přiřadí `assigned_dev`.
6. **Developer** po dokončení: nastaví `ready_for_review`, vyplní `pr_url`.
7. **Code Reviewer**: APPROVE → nastaví `ready_for_testing`. CHANGES NEEDED → status zpět na `in_development`.
8. **Human Reviewer**: manuální QA → merge do main → status `done`.
