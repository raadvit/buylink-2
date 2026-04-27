# Story Template

Šablona pro user story. Každá story v `wiki/stories/us-NNN.md` musí mít všechny povinné sekce.

**Validace:** pre-commit hook kontroluje přítomnost povinných sekcí a polí.

---

## Šablona (zkopíruj při vytváření nové story)

```markdown
---
id: US-NNN
title: [Krátký název max 80 znaků]
epic: [doménová oblast — např. auth, checkout, admin]
status: draft
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
author: Product Owner
assigned_dev: none
pr_url: none

# Memory Contract — vyplní Product Owner, validuje Conflict Detector
reads:
  - domain:section_name
  - api:section_name
writes:
  - domain:section_name
  - api:section_name
depends_on:
  - US-XXX
affected_stories: []  # vyplní Conflict Detector
conflict_check_iterations: 0  # increment Conflict Detector
---

## Business Context
[Proč to děláme. Jaký problém to řeší. Pro koho je to určeno.]

## User Story
**As a** [role uživatele]
**I want** [co chce udělat]
**So that** [proč, jaká hodnota]

## Acceptance Criteria
- [ ] AC-1: [Konkrétní, testovatelné kritérium]
- [ ] AC-2: ...
- [ ] AC-3: ...

## Out of Scope
- [Co tato story NEDĚLÁ — explicitně, ať Architekt neskočí mimo]

## Open Questions
- [Otázky, na které potřebuje Product Owner odpověď před conflict-check]

---

# === VYPLNÍ ARCHITEKT (fáze 1) ===

## Architecture Notes
[Doplní Architekt: dotčené komponenty, datový model, technické poznámky]

## Domain Changes
[Inline výtah z V2/domain.md — co se mění a co je relevantní pro implementaci]

## API Changes
[Inline výtah z V2/api.md — endpointy, payloady, response codes]

## Integration Changes
[Inline výtah z V2/integrations.md — pokud relevantní]

## Implementation Plan

### Backend kroky
1. [Krok 1 — co a kde]
2. [Krok 2]

### Frontend kroky
1. [Krok 1 — co a kde]
2. [Krok 2]

### Dotčené soubory
**Backend:**
- `path/to/file.py` — [popis změny]

**Frontend:**
- `path/to/template.html` — [popis změny]
- `path/to/script.js` — [popis změny]

### Migrace databáze
- [Pokud je třeba: nová tabulka / sloupce / index]

### Test plán
- **Unit testy (BE):** [co testovat]
- **Unit testy (FE):** [co testovat]
- **Integrační testy:** [co testovat end-to-end]
- **Manuální QA scénář** (povinné pro `ready_for_testing`):
  1. [Klikací krok 1]
  2. [Krok 2]
  3. [Očekávaný výsledek]

---

# === VYPLNÍ DEVELOPER (po implementaci) ===

## Implementation Notes
[Co se odlišilo od plánu, proč]

## PR Link
[URL]

---

# === VYPLNÍ CODE REVIEWER ===

## Review Result
- [ ] APPROVE → status `ready_for_testing`
- [ ] CHANGES NEEDED → status zpět na `in_development`

## Review Notes
[Pokud CHANGES NEEDED — co opravit]

---

# === VYPLNÍ HUMAN REVIEWER (před mergem) ===

## QA Test Result
- [ ] PASS → merge → status `done`
- [ ] FAIL → status zpět na `in_development` s popisem

## QA Notes
[Co bylo testováno, co failed pokud něco]

---

# === POSTMORTEM (po done, doporučeno) ===

## Postmortem
- **Co šlo dobře:** [...]
- **Co špatně:** [...]
- **Surprise:** [neočekávaná věc]
- **Změna v promptu / contractu:** [pokud nějaká]
```

---

## Povinná pole (validační schema)

| Sekce | Povinná v statusu |
|---|---|
| Frontmatter (id, title, epic, status, reads, writes) | draft a dál |
| Business Context | draft a dál |
| User Story (As a / I want / So that) | draft a dál |
| Acceptance Criteria (alespoň 1) | draft a dál |
| Architecture Notes | validated a dál |
| Implementation Plan (alespoň BE nebo FE kroky) | validated a dál |
| Domain Changes / API Changes / Integration Changes | validated a dál (alespoň jedna z nich, dle relevance) |
| Manuální QA scénář | validated a dál |
| Implementation Notes, PR Link | ready_for_review a dál |
| Review Result | ready_for_testing a dál |
| QA Test Result | done |

## Validační skript

```bash
python scripts/validate_story.py wiki/stories/us-NNN.md
```

Kontroluje:
- frontmatter má všechna povinná pole
- `reads` a `writes` referují existující sekce ve V2 (nebo sekce, které story sama vytváří)
- `status` je z povolené množiny
- pokud `status >= validated`, jsou vyplněné Architecture Notes, Implementation Plan a Manuální QA scénář
- pokud `status >= ready_for_review`, je vyplněn PR Link
- pokud `status >= ready_for_testing`, je vyplněn Review Result = APPROVE
- pokud `status == done`, je vyplněn QA Test Result = PASS

## Pravidla pro vyplňování

- **Pole `epic`** je volný text (doménová oblast nebo modul). Není vázán na předdefinovaný seznam, ale měl by být konzistentní napříč souvisejícími stories.
- **Pole `reads` a `writes`:** Product Owner odhadne nejlépe, jak může. Conflict Detector v případě potřeby koriguje. Architekt doplní, pokud objeví další dotčené sekce.
- **`Out of Scope`:** povinné, i když je to "nic mimo AC". Explicitně. Zabraňuje rozjíždění scope.
- **`Manuální QA scénář`:** Architekt vyplní v `Implementation Plan`. Bez něj nejde story do `validated`. Tento scénář pak Human Reviewer projde před mergem.
