# Token strategy — jediný zdroj pravdy pro modely

Změna modelu pro celý tým = změna jednoho řádku v sekci "Aktuální přiřazení".

---

## Aktuální režim

**VÝVOJ** — nižší modely pro většinu agentů, kritické rozhodování na vyšším modelu.

Po validaci pilotu rekalibrace, případně přechod na **PRODUKCE** režim s vyššími modely.

---

## Tier definice

| Tier | Účel | VÝVOJ model | PRODUKCE model |
|---|---|---|---|
| L1 | monitoring, dokumentace, jednoduché QA | claude-haiku-4-5-20251001 | claude-haiku-4-5-20251001 |
| L2 | implementace, review, design, PO, conflict detection | claude-haiku-4-5-20251001 | claude-sonnet-4-6 |
| L3 | architektura, komplexní rozhodnutí | claude-sonnet-4-6 | claude-opus-4-7 |

---

## Aktuální přiřazení agentů

| Agent | Tier | Aktuální model |
|---|---|---|
| product-owner | L2 | claude-sonnet-4-6 |
| conflict-detector | L2 | claude-haiku-4-5-20251001 |
| architekt | L3 | claude-sonnet-4-6 |
| backend-developer | L2 | claude-haiku-4-5-20251001 |
| frontend-developer | L2 | claude-haiku-4-5-20251001 |
| code-reviewer | L2 | claude-haiku-4-5-20251001 |
[metrics.md](metrics.md)
## Volitelní agenti (INACTIVE v této verzi)

| Agent | Tier | Plánovaný model |
|---|---|---|
| ux-designer | L2 | claude-haiku-4-5-20251001 |
| qa-inzenyr | L1 | claude-haiku-4-5-20251001 |
| security-auditor | L2 | claude-haiku-4-5-20251001 |
| dokumentarista | L1 | claude-haiku-4-5-20251001 |
| ops-monitor | L1 | claude-haiku-4-5-20251001 |

---

## Execution rules

### Povinné

- Zpracovávat **jen změny** (delta processing) — ne celou historii.
- Volitelné agenty (fáze 2) spouštět **pouze on demand**.
- Logovat každý agent run do `metrics/agent_runs.jsonl` (input_tokens, output_tokens, cost, model, duration).

### Zakázané

- Paralelní běh **stejné role** bez nutnosti.
- Paralelní zápis do **stejného V2 souboru** (race condition).
- Redundantní analýza stejného kódu / stejné sekce V2.

### Povolené paralelní

- Architekt (L3) připravuje story + Code Reviewer (L2) reviewuje jinou story — **OK**, jiné role, jiné soubory.
- Backend Developer + Frontend Developer paralelně po Architektově plánu — **podmíněně OK**: jen pokud BE nemusí předat kontext FE (FE-only nebo BE už měl základ připravený). U full-stack stories doporučeno BE první.

---

## Postup upgradu na PRODUKCE

1. Změň "Aktuální režim" z `VÝVOJ` na `PRODUKCE`.
2. V tabulce "Aktuální přiřazení" nahraď modely dle PRODUKCE sloupce v Tier definici.
3. Aktualizuj `model:` v frontmatteru souborů `team/*.md`.
4. Před přechodem: **regression test** — proženi 5 testovacích stories oběma režimy a porovnej výsledky.

---

## Token costs (orientační)

Aktuální ceny ke dni založení projektu (zkontrolovat aktuální při upgradu):

| Model | Input ($/MTok) | Output ($/MTok) |
|---|---|---|
| claude-haiku-4-5 | 1 | 5 |
| claude-sonnet-4-6 | 3 | 15 |
| claude-opus-4-7 | 15 | 75 |

**Příklad cost per story v VÝVOJ režimu (full-stack):**

| Agent | Model | Input | Output | Cost |
|---|---|---|---|---|
| Product Owner | Haiku | 3k | 1k | $0.008 |
| Conflict Detector | Haiku | 5k | 1k | $0.010 |
| Architekt | Sonnet | 15k | 3k | $0.090 |
| Backend Developer | Haiku | 10k | 3k | $0.025 |
| Frontend Developer | Haiku | 10k | 3k | $0.025 |
| Code Reviewer | Haiku | 6k | 1k | $0.011 |
| **Total** |  |  |  | **~$0.17** |

Při 100 stories: ~$17. Při PRODUKCE režimu: ~$60-120.

⚠️ **Skutečné náklady ověř po prvních 3 stories** v `metrics/agent_runs.jsonl` — odhad může být mimo kvůli reálné spotřebě tokenů.

⚠️ **Ceny se mění** — před PRODUKCE přechodem zkontrolovat aktuální ceník.
