# Token strategie — jediný zdroj pravdy pro modely

Změna modelu pro celý tým = změna jednoho řádku v sekci "Aktuální přiřazení".

---

## Tier definice

| Tier | Účel | Produkční model | Vývojový model |
|---|---|---|---|
| L1 | monitoring, dokumentace, QA | claude-haiku-4-5-20251001 | claude-haiku-4-5-20251001 |
| L2 | implementace, review, design | claude-sonnet-4-6 | claude-haiku-4-5-20251001 |
| L3 | architektura, komplexní rozhodnutí | claude-opus-4-7 | claude-haiku-4-5-20251001 |

---

## Aktuální přiřazení agentů

> Aktuální režim: **VÝVOJ** — všechny tiery na Haiku

| Agent | Tier | Aktuální model |
|---|---|---|
| conflict-detector | L2 | claude-haiku-4-5-20251001 |
| product-owner | L2 | claude-haiku-4-5-20251001 |
| architekt | L3 | claude-haiku-4-5-20251001 |
| designer-ux | L2 | claude-haiku-4-5-20251001 |
| developer-be | L2 | claude-haiku-4-5-20251001 |
| developer-fe | L2 | claude-haiku-4-5-20251001 |
| qa-inzenyr | L1 | claude-haiku-4-5-20251001 |
| code-reviewer | L2 | claude-haiku-4-5-20251001 |
| security-auditor | L2 | claude-haiku-4-5-20251001 |
| dokumentarista | L1 | claude-haiku-4-5-20251001 |
| ops-monitor | L1 | claude-haiku-4-5-20251001 |

---

## Execution rules

### Zakázáno
- běh více agentů paralelně bez nutnosti
- redundantní analýzy stejného kódu

### Povinné
- zpracovávat jen změny (delta processing)
- volitelné agenty (QA, Security, Dokumentarista) spouštět pouze on demand — viz `agents.md`

---

## Postup upgradu při přechodu na produkci

1. Změň řádek "Aktuální režim" z `VÝVOJ` na `PRODUKCE`
2. V tabulce "Aktuální přiřazení agentů" nahraď `claude-haiku-4-5-20251001` produkčním modelem dle tier sloupce
3. Aktualizuj `model:` v souborech dotčených agentů
