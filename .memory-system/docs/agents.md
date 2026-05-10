# Agents — workflow

Aktivní agenti definovaní v `team/team-active.md`. Default: 6 agentů (PO, Conflict Detector, Architekt, Backend Developer, Frontend Developer, Code Reviewer).

Všichni agenti dodržují `V1/constraints.md` a `agent-memory-contract.md`.

## Tým

| Agent | Soubor | Tier | Role |
|---|---|---|---|
| Business Owner | — | člověk | záměr / problém → Product Owner; jediný kdo mění V1 (kromě append do decisions) |
| Product Owner | `team/product-owner.md` | L2 | byznys → user story, správce story_register |
| Conflict Detector | `team/conflict-detector.md` | L2 | detekce konfliktů a závislostí před architekturou |
| Architekt | `team/architekt.md` | L3 | návrh řešení, datový model, ADR, impl. plán |
| Backend Developer | `team/backend-developer.md` | L2 | implementace BE části story |
| Frontend Developer | `team/frontend-developer.md` | L2 | implementace FE části story |
| Code Reviewer | `team/code-reviewer.md` | L2 | review před manuálním QA |
| Human Reviewer | — | člověk (vývojář) | manuální QA + finální merge |

## Fáze 1 — Příprava story

```
Business Owner
      │  záměr nebo problém
      ▼
Product Owner
      │  draft story dle templates/story-template.md
      │  vyplní: reads, writes, depends_on, AC
      │  status: draft → conflict-check
      ▼
Conflict Detector
      │  3 pasy: doména, API, integrace
      │  čte: V2 sekce dle reads+writes + story_register + V4
      │
      ├── NOT OK ──→ Product Owner (max 3 iterace)
      │              │ upraví story
      │              │ counter conflict_check_iterations++
      │              │ při 3. iteraci → status=blocked, eskalace Business Owner
      │              ↑ zpět na Conflict Detector
      ▼ OK
      │  doplní: affected_stories
      │  update V4/cross_links.json
      │  status → ready-for-arch
      │  AUTO-trigger Architekta
      ▼
Architekt (Fáze 1)
      │  čte: V1 + V2 [reads+writes] + story
      │  doplní story:
      │    - Architecture Notes
      │    - Domain Changes / API Changes / Integration Changes (INLINE výtahy)
      │    - Implementation Plan (rozdělen na BE / FE kroky)
      │    - Manuální QA scénář (povinné)
      │  píše do V2 [writes]: domain.md / api.md / integrations.md (strict format)
      │  volitelně: nový ADR v V1/decisions.md (append-only)
      │  status → validated
      ▼
   ✓ Story je ready k implementaci, self-contained
```

## Fáze 2 — Implementace

Spouští se manuálně (`/implement-be US-NNN`, `/implement-fe US-NNN`) nebo automaticky scheduler.

### BE-only story (např. nový endpoint, migrace bez UI změny)

```
Trigger /implement-be US-NNN
      │
      ▼
Backend Developer
      │  branch story/us-NNN-{slug}
      │  status → in_development
      │  čte: pouze story (self-contained)
      │  implementuje BE kroky
      │  testy, lintery
      │  push, otevře PR
      │  status → ready_for_review
      ▼
Code Reviewer
      │  výstup: APPROVE | CHANGES NEEDED
      │
      ├── CHANGES NEEDED ──→ Backend Developer (iterace)
      │                       status → in_development
      ▼ APPROVE
      │  status → ready_for_testing
      ▼
Human Reviewer
      │  manuální QA podle Manuální QA scénář
      │
      ├── FAIL ──→ Backend Developer
      │            status → in_development
      ▼ PASS
      │  merge do main (squash)
      │  status → done
      ▼
# pull nového kódu (před dokumentaristou)
git -C buy-link/buylinkApi pull  # nebo buylinkFe dle scope
      ▼
Dokumentarista  (trigger: /sync-docs US-NNN)
      │  čte: skutečný kód + V2 sekce dle writes
      │  aktualizuje V2 dle reality (ne plánu)
      │  poznámka do Jiry při odchylkách
      │  commit [US-NNN] docs: sync V2 po implementaci
      ▼
   ✓ V2 odpovídá skutečnosti, příští story má přesný kontext
```

### Full-stack story (BE + FE změny)

```
Trigger /implement-be US-NNN  (vždy první, FE potřebuje API)
      │
      ▼
Backend Developer
      │  branch story/us-NNN-{slug}
      │  status → in_development
      │  implementuje BE kroky, testy
      │  commit + push (BEZ PR)
      │  vyplní Implementation Notes (BE část)
      │  status zůstává in_development
      ▼
Trigger /implement-fe US-NNN  (po BE)
      │
      ▼
Frontend Developer
      │  pokračuje na branchi story/us-NNN-{slug}
      │  implementuje FE kroky, testy
      │  konzumuje API podle inline API Changes ve story
      │  push, otevře PR
      │  vyplní Implementation Notes (FE část) + PR Link
      │  status → ready_for_review
      ▼
Code Reviewer
      │  reviewuje BE+FE diff
      │  výstup: APPROVE | CHANGES NEEDED
      │
      ├── CHANGES NEEDED ──→ Backend nebo Frontend Developer (dle pripomínek)
      ▼ APPROVE
      │  status → ready_for_testing
      ▼
Human Reviewer
      │  manuální QA
      │
      ├── FAIL ──→ Developer (BE nebo FE)
      ▼ PASS
      │  merge → status done
      ▼
# pull nového kódu
git -C buy-link/buylinkApi pull && git -C buy-link/buylinkFe pull
      ▼
Dokumentarista  (trigger: /sync-docs US-NNN)
      │  aktualizuje V2 dle reality
      ▼
   ✓ V2 synchronizováno
```

### FE-only story (nová stránka proti existujícím endpointům)

Stejný flow jako BE-only, jen volá `/implement-fe`. Pokud Architekt v plánu označí, že existující API je dostatečné, BE Developer se nespouští.

## Handshake protokoly

### Product Owner → Conflict Detector

Story se statusem `conflict-check`. Povinně vyplněno:
- frontmatter: id, title, epic, status, reads, writes, depends_on
- Business Context, User Story, Acceptance Criteria, Out of Scope

### Conflict Detector → Product Owner (NOT OK)

Seznam konfliktů ve formátu:
```
CONFLICT_TYPE: DOMAIN | API | INTEGRATION | DEPENDENCY
SEVERITY: BLOCKER | WARNING
SECTION: domain:section-name
RELATED_STORIES: [US-XXX, ...]
DESCRIPTION: [1-3 věty]
SUGGESTED_RESOLUTION: [návrh úpravy]
```

### Conflict Detector → Architekt (OK)

Story s doplněným `affected_stories` a statusem `ready-for-arch`. Update V4 cache.

### Architekt → Developeři

**Story self-contained.** Developeři nepotřebují nic mimo story:
- Architecture Notes (technický kontext)
- Domain/API/Integration Changes (INLINE výtahy z V2, ne odkazy)
- Implementation Plan: BE kroky / FE kroky / dotčené soubory / migrace
- Manuální QA scénář (pro Human Reviewera)
- Acceptance Criteria (z fáze 1)

### Backend Developer → Frontend Developer

Pokud full-stack: BE Developer pushne branch s commity, vyplní `Implementation Notes` (BE část). FE Developer pokračuje na stejném branchi.

### Developer → Code Reviewer

PR otevřený, story má `Implementation Notes` a `PR Link`.

### Code Reviewer → Human Reviewer

GitHub PR review s `APPROVE`, status `ready_for_testing`. Human Reviewer projde `Manuální QA scénář`, merguje.

## Worktrees (paralelní implementace)

Pro paralelní implementaci více stories: každá story `in_development` má vlastní worktree. Detail v `docs/worktrees.md`.

## Volitelní agenti (fáze 2 — později)

Tito agenti **nejsou** v této verzi memory systému definovaní. Aktivace přijde s firemním rozhodnutím a samostatnou definicí v `team/`.

| Agent | Spouštěč | Hodnota |
|---|---|---|
| UX Designer | manuální při FE story | konzistentní design napříč stories |
| QA Inženýr | manuální při komplexní implementaci | strukturované testování AC, automatizace |
| Security Auditor | manuální při změně auth / endpointů | nezávislý security review |
| Dokumentarista | `/sync-docs US-NNN` po mergi story | aktualizace V2 po implementaci — sync kódu s memory systémem |
| Ops Monitor | scheduler po deployi | sledování anomálií v produkci |

Před aktivací každého: data, která ukazují, že **opravdu** chybí.

## Execution rules

### Povinné

- Selektivní čtení V2 podle `reads`+`writes` story
- Strict format ve všech V2 zápisech (validační hook)
- Append-only `decisions.md`
- Self-contained story po Architektově fázi
- Token budget per agent run
- BE Developer před FE Developerem u full-stack stories
- Manuální QA před mergem (Human Reviewer)

### Zakázané

- Paralelní běh agentů, kteří píší do stejného souboru
- Vícenásobný zápis do `domain.md` v rámci jedné story bez sekvenčního flow
- Skip validace formátu
- Edit existujícího ADR
- Developer čte V2 přímo
- Merge bez manuálního QA
