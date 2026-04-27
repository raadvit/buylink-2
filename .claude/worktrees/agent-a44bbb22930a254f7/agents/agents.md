# Tým agentů — přehled a workflow

Všichni agenti sdílejí globální pravidla definovaná v `memory-system/V1 - static context/constraints.md`.
Paměťové vrstvy a read/write kontrakty viz `memory_system.md` a `agent_memory_contract.md`.

---

## Členové týmu

Aktuální modely viz `token_strategy.md`.

| Agent | Soubor | Tier   | Role |
|---|---|--------|---|
| Business Owner | —                        | člověk | záměr / problém → Product Owner; jediný kdo mění V1 |
| Product Owner | `team/product-owner.md` | L2     | business → user story, správce story_register |
| Conflict Detector | `team/conflict-detector.md` | L2     | detekce konfliktů a závislostí před architekturou |
| Architekt | `team/architekt.md` | L3     | návrh řešení, datový model, ADR |
| UX/UI Designer | `team/designer-ux.md` | L2     | uživatelské rozhraní a tok |
| Backend Developer | `team/developer-be.md` | L2     | implementace BE, migrace |
| Frontend Developer | `team/developer-fe.md` | L2     | implementace FE |
| QA Inženýr | `team/qa-inzenyr.md` | L1     | validace oproti acceptance criteria |
| Code Reviewer | `team/code-reviewer.md` | L2     | review před mergem |
| Security Auditor | `team/security-auditor.md` | L2     | audit bezpečnosti |
| Dokumentarista | `team/dokumentarista.md` | L1     | aktualizace V2, technická dokumentace |
| Ops Monitor | `team/ops-monitor.md` | L1     | provozní monitoring |

---

## Fáze 1 — Příprava story

```
Business Owner
      │  záměr nebo problém
      ▼
Product Owner
      │  draft story dle story-template.md
      │  vyplní: reads_sections, writes_sections
      ▼
Conflict Detector                    ← trigger: status draft → conflict-check
      │  čte: V2 [affected_sections] + story_register
      │  hledá: konflikty, závislosti, nekonzistentní entity
      │
      ├── NOT OK ──→ Human review ──→ Product Owner (upraví story)
      │                                     ↑ zpět na Conflict Detector
      ▼ OK
      │  doplní: affected_stories do story Memory Contract
      │  status → ready-for-arch
      │  automaticky spustí Architekta
      ▼
Architekt
      │  čte: V1 + V2 [affected_sections] + story
      │  doplní story o technické popisky (datový model, dotčené komponenty, závislosti)
      │  píše: domain_model.md [writes_sections], story_register
      │  status → validated
      ▼
   ✓ Story je připravena k implementaci
```

---

## Fáze 2 — Implementace

Spouští se samostatně (příkazem `/implement`) nad jednou nebo více validated stories.

```
Architekt
      │  čte: validated stories + V1 + V2 [affected_sections]
      │  výstup: implementační plán (viz níže)
      │
      ├──────────────────────────────┐
      ▼                              ▼
Backend Developer           Frontend Developer + UX Designer
      │  čte: story + impl. plán    │  čte: story + impl. plán
      │  NEČTE V2 přímo             │  NEČTE V2 přímo
      └──────────────┬──────────────┘
                     ▼
             status → in_development
                     │
                     ▼  /pr
              Code Reviewer
                     │  výstup: APPROVE / CHANGES NEEDED
                     ▼
                  merge do main

[volitelně] QA Inženýr              → výstup: PASS / FAIL
[volitelně] Security Auditor        → výstup: PASS / FINDINGS
[volitelně] Dokumentarista          → aktualizuje V2, loguje do V3 (až aktivní)
```

---

## Handshake protokoly — formát předávání výstupů

### Product Owner → Conflict Detector
Story ve formátu dle `story-template.md` se statusem `conflict-check`.
Povinně vyplněno: `reads_sections`, `writes_sections`.

### Conflict Detector → Product Owner (NOT OK)
Seznam konfliktů ve formátu:
```
CONFLICT: [typ konfliktu]
Story: [ID kolidující story]
Sekce: [dotčená sekce domain_model]
Popis: [konkrétní rozpor]
```

### Conflict Detector → Architekt (OK)
Story s doplněným `affected_stories` a statusem `ready-for-arch`.

### Architekt → story (fáze 1 — technické anotace)
Architekt doplní do story:
- dotčené komponenty a jejich závislosti
- datový model nebo schéma (pokud se mění)
- technické poznámky relevantní pro implementaci
- status → `validated`

### Architekt → Developer (BE / FE) — fáze 2
Implementační plán obsahující:
- seznam dotčených souborů
- popis změn (co přidat / změnit / odstranit)
- datový model nebo schéma (pokud se mění)
- API kontrakt (endpoint, parametry, odpovědi)
- pořadí kroků (pokud záleží na pořadí)
- **výtah relevantního kontextu z V2** — Developer nečte V2 přímo

### Developer → Code Reviewer → merge
- explicitní `APPROVE` od Code Reviewera

### merge → Dokumentarista
- seznam změněných souborů
- odkaz na story (co se implementovalo)

---

## Volitelní agenti (on demand, šetří tokeny)

### QA Inženýr
Spouštěj ručně, když:
- implementace je komplexní nebo riziková
- acceptance criteria jsou rozsáhlá a těžko ověřitelná čtením kódu

### Security Auditor
Spouštěj ručně, když:
- změna autentizace nebo autorizace
- nový endpoint přijímající uživatelský vstup
- změna nakládání se secrets nebo credentials
- před releasem do produkce

### Dokumentarista
Spouštěj ručně, když:
- změna API kontraktu
- změna konfigurace prostředí
- příprava releasu
