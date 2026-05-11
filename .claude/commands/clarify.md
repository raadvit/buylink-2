# Clarify — vyjasnění požadavků story

> Spouštěno automaticky přes `claude -p "/clarify {issue_number}"` z task-forge backendu.
> Čte **pouze story soubor** — bez memory systému, bez domain modelu. Záměrně rychlý a lehký.

Vygeneruje max 5 prioritizovaných otázek k story a zapíše je do sekce `## Clarify`.

## Live komunikace s uživatelem (IPC)

`TF_SESSION_ID` a `TF_API_PORT` jsou nastaveny v env.

```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"ZPRÁVA\",\"agent\":\"Clarify\"}" || true
```

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 1. Načti story

Načti `wiki/stories/US-{id}.md`. Nečti žádné jiné soubory.

Pošli zprávu:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Analyzuji story…\",\"agent\":\"Clarify\"}" || true
```

### 2. Sken ambiguit

Projdi story a pro každou kategorii níže urči stav: **Jasné** / **Částečné** / **Chybí**.

Kategorie:
- **Funkční rozsah** — Co přesně funkce dělá, co je out of scope
- **Datový model** — Entity, atributy, vztahy, unikátnost
- **UX flow** — Klíčové kroky uživatele, chybové a prázdné stavy
- **Edge cases** — Negativní scénáře, souběžné akce, limity
- **Terminologie** — Nejednoznačné nebo nedefinované pojmy
- **Completion signals** — Testovatelná acceptance criteria

Automaticky zařaď jako **Chybí** pokud:
- Sekce nebo podsekce obsahuje pouze `-`
- Jakýkoli text obsahuje `TBD`, `TODO`, `?`, `nevím`, `doplnit`

Automaticky **přeskoč** sekci (nezařazuj ani jako Chybí) pokud:
- Sekce obsahuje `---` nebo je zcela prázdná — tyto sekce jsou záměrně nevyplněné

### 3. Vygeneruj otázky (max 5)

Ze kategorií se stavem **Částečné** nebo **Chybí** vyber max 5 otázek s nejvyšším dopadem na implementaci. Pravidla:

- Otázka musí mít přímý dopad na architekturu, datový model, UX chování nebo AC
- Vyřaď otázky na stylové preference a implementation details
- Upřednostni otázky, jejichž špatný předpoklad způsobí přepracování
- Pokud žádné podstatné nejasnosti neexistují, pokračuj krokem 4b

### 4a. Zapiš do story (pokud jsou otázky)

Vytvoř nebo přepiš sekci `## Clarify` v `wiki/stories/US-{id}.md`:

```markdown
## Clarify
### Session YYYY-MM-DD
1. <otázka>
2. <otázka>
3. <otázka>
```

Zachovej existující sekce dokumentu, vlož `## Clarify` těsně před `## Acceptance criteria` (nebo na konec pokud sekce neexistuje).

Aktualizuj status na `clarify`:
```bash
sed -i '' 's/^ *- Status: .*/- Status: clarify/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md clarify
```

Pošli zprávu:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Otázky jsou připraveny. Odpověz na ně v chatu a klikni Spustit analýzu.\",\"agent\":\"Clarify\"}" || true
```

### 4b. Žádné nejasnosti

Pokud story nemá žádné podstatné nejasnosti, aktualizuj status na `draft`:
```bash
sed -i '' 's/^ *- Status: .*/- Status: draft/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md draft
```

Synchronizuj s issue systémem:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT:-5001}/api/issues/{číslo}/sync-wiki" || true
```

Pošli zprávu:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Žádné kritické nejasnosti — story je připravena k analýze.\",\"agent\":\"Clarify\"}" || true
```

## Pravidla

- Nečti žádné soubory kromě `wiki/stories/US-{id}.md`
- Nečti `.memory-system/`, `.claude/config.md`, domain model ani jiné stories
- Nikdy necommituj změny do gitu
