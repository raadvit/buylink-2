# Analýza — Conflict Detector

Fáze Conflict Detector z validačního pipeline. Zkontroluje konflikty story s ostatními stories a domain modelem.

Po dokončení uloží výsledek do US souboru a aktualizuje GitHub issue.

## Live komunikace s uživatelem (IPC)

`TF_SESSION_ID` a `TF_API_PORT` jsou nastaveny v prostředí (env).

**Poslat zprávu:**
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"ZPRÁVA\",\"agent\":\"JMÉNO\"}" || true
```

Kdy posílat zprávy:
- Před spuštěním detekce konfliktů
- Při nalezení konfliktu před zápisem do wiki

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 0. Inicializace

Zaznamenej čas začátku (`cd_start`). Připrav `cost_cd = 0.0`, `tokens_cd = 0`.

### 1. Načti story

Načti `wiki/stories/US-{id}.md`.

### 2. Spusť agenta Conflict Detector

Spusť agenta `conflict-detector` (instrukce v `.memory-system/team/conflict-detector.md`) s:
- Textem story (včetně `reads_sections` / `writes_sections` vyplněných PO)
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md` (dle `reads_sections`)
- `.memory-system/V2-shared-truth/story_register.md`

Výstup agenta je JSON:
- OK: `{"action": "ok", "affected_stories": []}`
- Konflikt: `{"action": "conflict", "conflicts": [{"typ": "...", "story": "...", "popis": "..."}]}`

### 3. Zpracování výsledku

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_cd = total_tokens`
- `cost_cd = tokens_cd / 1_000_000 × 2.08`

**Pokud `conflict`:**
- Přidej sekci `## Konflikty` do wiki souboru s popisem konfliktů
- Přečti `conflict_check_iterations` z frontmatteru wiki souboru (default 0)
- Inkrementuj counter: `conflict_check_iterations += 1`
- Pokud `conflict_check_iterations >= 3`: nastav `blocked`, jinak `draft`
  ```bash
  # Pro draft (< 3 iterace):
  sed -i '' 's/^conflict_check_iterations: .*/conflict_check_iterations: N/; s/^- Status: .*/- Status: draft/; s/^status: .*/status: draft/' wiki/stories/US-{id}.md
  python3 task-forge/status_history.py append wiki/stories/US-{id}.md draft

  # Pro blocked (>= 3 iterace):
  sed -i '' 's/^- Status: .*/- Status: blocked/; s/^status: .*/status: blocked/' wiki/stories/US-{id}.md
  python3 task-forge/status_history.py append wiki/stories/US-{id}.md blocked
  python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
  ```
- Pošli zprávu uživateli přes IPC s popisem konfliktu a navrhovaným řešením

**Pokud `ok`:**
```bash
sed -i '' 's/^- Status: .*/- Status: ready-for-arch/; s/^status: .*/status: ready-for-arch/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md ready-for-arch
```

### 4. Metriky a uložení

`cd_duration` = čas od `cd_start` (zaokrouhli na sekundy). Formát: `{n}s` / `{m}m {s}s` / `{h}h {m}m`.

Zapiš/přepiš řádek `- Analýza CD:` v sekci `## Metriky` wiki souboru (zachovej ostatní řádky):
```
- Analýza CD: $X.XXXX · čas {cd_duration}
```
Pokud sekce `## Metriky` neexistuje, přidej ji na konec souboru.

Synchronizuj wiki soubor s issue systémem přes provider:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT:-5001}/api/issues/{číslo}/sync-wiki" || \
  echo "Warning: sync-wiki selhal — wiki soubor byl aktualizován, issue nikoli." >&2
```

## Pravidla
- Nikdy necommituj změny do gitu
- Pokud `<usage>` blok chybí, použij `$0.0000`
