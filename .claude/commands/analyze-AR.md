# Analýza — Architekt

Fáze Architekt z validačního pipeline. Přidá technické anotace, AC, test cases a implementační plán.

Po dokončení uloží výsledek do US souboru, aktualizuje domain model a story register, a aktualizuje GitHub issue.

## Live komunikace s uživatelem (IPC)

`TF_SESSION_ID` a `TF_API_PORT` jsou nastaveny v prostředí (env).

**Poslat zprávu:**
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"ZPRÁVA\",\"agent\":\"JMÉNO\"}" || true
```

Kdy posílat zprávy:
- Před spuštěním architektonické analýzy
- Při klíčových rozhodnutích o architektuře

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 0. Inicializace

Zaznamenej čas začátku (`arch_start`). Připrav `cost_arch = 0.0`, `tokens_arch = 0`.

### 1. Načti story a kontext

Načti `wiki/stories/US-{id}.md`.

Přečti `.claude/config.md` — hodnoty `generate_acceptance_criteria` a `architect_creates_implementation_plan`.

### 2. Kontrola triviálnosti

Pokud story nemá `reads_sections` ani `writes_sections`, přeskoč na krok 4 (Finalizace) bez spuštění agenta.

### 3. Spusť agenta Architekt

Spusť agenta `architekt` (instrukce v `.memory-system/team/architekt.md`) s:
- Textem story (včetně anotací PO)
- `.memory-system/V1-static-context/project.md`
- `.memory-system/V1-static-context/constraints.md`
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md` (dle `reads_sections` / `writes_sections`)
- `.memory-system/V2-shared-truth/story_register.md`

Architekt přidá do story (výstup ve formátu JSON):
- AC a test cases (pokud `generate_acceptance_criteria: true`)
- Technické anotace a dopad na domain model
- Implementační plán (pokud `architect_creates_implementation_plan: true`)

Ulož výstup Architekta do wiki souboru pomocí Edit nástroje.

Aktualizuj domain model a story register dle instrukcí v `.memory-system/CLAUDE.md`.

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_arch = total_tokens`
- `cost_arch = tokens_arch / 1_000_000 × 7.8` (Sonnet 4.6: ~$7.8/MTok blended)

### 4. Finalizace a metriky

`arch_duration` = čas od `arch_start` (zaokrouhli na sekundy). Formát: `{n}s` / `{m}m {s}s` / `{h}h {m}m`.

Zapiš/přepiš řádek `- Analýza Arch:` v sekci `## Metriky` wiki souboru (zachovej ostatní řádky):
```
- Analýza Arch: $X.XXXX · čas {arch_duration}
```
Pokud Architekt byl přeskočen (triviální story), vynech tento řádek. Pokud sekce `## Metriky` neexistuje, přidej ji na konec souboru.

Aktualizuj status na `validated`:
```bash
sed -i '' 's/^- Status: .*/- Status: validated/; s/^status: .*/status: validated/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md validated
python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
```

Synchronizuj wiki soubor s issue systémem přes provider:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT:-5001}/api/issues/{číslo}/sync-wiki" || \
  echo "Warning: sync-wiki selhal — wiki soubor byl aktualizován, issue nikoli." >&2
```

## Pravidla
- Nikdy necommituj změny do gitu
- Pokud `<usage>` blok chybí, použij `$0.0000`
- Pokud Architekt byl přeskočen, nepiš `$0.0000` — vynech řádek úplně
