# Analýza user story

> Spouštěno automaticky přes `claude -p "/analyze {issue_number}"` z task-forge backendu (`story_builder.launch_analyze_agent`).
> task-forge polling sleduje změny statusu v `wiki/stories/US-{id}.md` — aktualizuj ho po každé fázi.

Provede validační pipeline pro existující story: Product Owner → Conflict Detector → Architekt.

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 0. Inicializace metrik

Zaznamenej čas začátku analýzy (`analyze_start`). Připrav proměnné:
- `cost_po = 0.0`, `tokens_po = 0`
- `cost_cd = 0.0`, `tokens_cd = 0`
- `cost_arch = 0.0`, `tokens_arch = 0`

### 1. Načti story a kontext

Načti `wiki/stories/US-{id}.md`.

Přečti `.claude/config.md` — hodnoty `generate_acceptance_criteria` a `architect_creates_implementation_plan`.

### 2. Product Owner

Spusť agenta `product-owner` (instrukce v `.memory-system/team/product-owner.md`) s:
- Obsahem story
- `.memory-system/V1-static-context/project.md`
- `.memory-system/V2-shared-truth/story_register.md`

PO ověří srozumitelnost story a doplní `reads_sections` / `writes_sections` (sekce domain modelu, které story čte/mění).

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_po = total_tokens`
- `cost_po = tokens_po / 1_000_000 × 2.08` (Haiku 4.5: ~$2.08/MTok blended)

Po PO aktualizuj status:
```bash
sed -i '' 's/^- Status: .*/- Status: conflict-check/; s/^status: .*/status: conflict-check/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md conflict-check
```

### 3. Conflict Detector

Spusť agenta `conflict-detector` (instrukce v `.memory-system/team/conflict-detector.md`) s:
- Výstupem PO (text story)
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md` (dle `reads_sections`)
- `.memory-system/V2-shared-truth/story_register.md`

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_cd = total_tokens`
- `cost_cd = tokens_cd / 1_000_000 × 2.08`

Výstup agenta je JSON:
- OK: `{"action": "ok", "affected_stories": []}`
- Konflikt: `{"action": "conflict", "conflicts": [{"typ": "...", "story": "...", "popis": "..."}]}`

Pokud `conflict`:
- Přidej sekci `## Konflikty` do wiki souboru s popisem konfliktů
- Aktualizuj status na `blocked`:
  ```bash
  sed -i '' 's/^- Status: .*/- Status: blocked/; s/^status: .*/status: blocked/' wiki/stories/US-{id}.md
  python3 task-forge/status_history.py wiki/stories/US-{id}.md blocked
  python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
  ```
- Přejdi na krok 5 (zapiš metriky a zastav)

Pokud `ok`:
```bash
sed -i '' 's/^- Status: .*/- Status: ready-for-arch/; s/^status: .*/status: ready-for-arch/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py wiki/stories/US-{id}.md ready-for-arch
```

### 4. Architekt (Fáze 1 — technické anotace)

Pokud story nemá `reads_sections` ani `writes_sections` (triviální story), přeskoč Architekta a pokračuj krokem 5.

Spusť agenta `architekt` (instrukce v `.memory-system/team/architekt.md`) s:
- Výstupem PO (text story)
- `.memory-system/V1-static-context/project.md`
- `.memory-system/V1-static-context/constraints.md`
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md`
- `.memory-system/V2-shared-truth/story_register.md`

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_arch = total_tokens`
- `cost_arch = tokens_arch / 1_000_000 × 7.8` (Sonnet 4.6: ~$7.8/MTok blended)

Architekt přidá do story (výstup ve formátu JSON):
- AC a test cases (pokud `generate_acceptance_criteria: true`)
- Technické anotace a dopad na domain model
- Implementační plán (pokud `architect_creates_implementation_plan: true`)

Ulož výstup Architekta do wiki souboru pomocí Edit nástroje.

Aktualizuj domain model a story register dle instrukcí v `.memory-system/CLAUDE.md`.

### 5. Finalizace a metriky

Vypočti agregované hodnoty:
- `cost_analyze_total = cost_po + cost_cd + cost_arch`
- `analyze_duration` = čas od `analyze_start` do teď (zaokrouhli na sekundy)

Formatuj čas: pokud < 60s → `{n}s`, pokud < 3600s → `{m}m {s}s`, jinak `{h}h {m}m`.

Připrav řádek metriky analýzy:
```
- Analýza: $X.XXXX · PO $X.XXXX · CD $X.XXXX · Arch $X.XXXX · čas {duration}
```
Pokud Architekt byl přeskočen, vynech `· Arch $X.XXXX`. Pokud `<usage>` nebyl dostupný, použij `$0.0000`.

Zapiš/přepiš sekci `## Metriky` v wiki souboru (Edit nástroj). Pokud sekce existuje, zachovej řádky `- Implementace:` a `- Celkem:` pokud jsou. Přepiš pouze řádek `- Analýza:` a přepočítej `- Celkem:`.

Výsledná sekce:
```markdown
## Metriky
- Analýza: $X.XXXX · PO $X.XXXX · CD $X.XXXX · Arch $X.XXXX · čas {duration}
- Celkem: $X.XXXX
```

Aktualizuj status na `validated` (nebo ponech `blocked` pokud Conflict Detector selhal):
```bash
sed -i '' 's/^- Status: .*/- Status: validated/; s/^status: .*/status: validated/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py wiki/stories/US-{id}.md validated
python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
```

Aktualizuj GitHub issue:
```bash
gh issue edit {číslo} --repo {Main_repo z .claude/config.md} --body "$(cat wiki/stories/US-{id}.md)"
```

## Pravidla
- Nikdy necommituj změny do gitu — wiki soubory jsou working state sledovaný backendem
- Pokud agent selže non-fatálně (např. conflict-detector), pokračuj na další fázi
- Agenti nečtou V2 přímo v implementační fázi — výtah připravuje Architekt
- Pokud `<usage>` blok chybí, použij `$0.0000` — nezastavuj pipeline kvůli chybějícím metrikám
