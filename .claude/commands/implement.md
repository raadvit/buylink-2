# Implementace user story

> Názvy repozitářů a UX pravidla čti ze souboru `.claude/config.md`.

Provede celý implementační cyklus od načtení story přes refinement s týmem až po naprogramování. Vše provádí autonomně bez potvrzování.

## Vstup

`$ARGUMENTS` může obsahovat jedno nebo více čísel stories oddělených čárkou (např. `2,6,23` nebo jen `5`).
Čísla odpovídají suffixu ID souboru (2 → `US-002`). Pokud chybí, zavolej `/user-story-read` bez argumentu pro výběr.

## Postup

### 0. Inicializace metrik

Zaznamenej čas začátku implementace (`implement_start`).

### 1. Načti stories a technický kontext
Parsuj `$ARGUMENTS` jako čárkou oddělený seznam čísel. Každé číslo převeď na ID ve formátu `US-{číslo s nulami na 3 cifry}` (2 → `US-002`, 23 → `US-023`).

Pro každou story zavolej `/user-story-read {ID}` a načti její obsah.

Pokud je u některé story `Status` jiný než `validated`, informuj uživatele:
- `draft` → "Story {ID} nebyla technicky anotována architektem — přeskoč nebo oprav před implementací."
- `in_development` → "Story {ID} se již implementuje, pokračuji."
- `ready_for_testing` / `done` → "Story {ID} je hotová, pokračuji na žádost."

### 2. Načti implementační plán
Story musí obsahovat sekci `## Implementation Plan` — Architekt ji vyplnil v analýze (Fáze 1 dle `.memory-system/docs/agents.md`). Pokud sekce chybí, story nebyla správně zvalidována — zastav a informuj uživatele.

Nastav `cost_arch_analysis = 0.0000 USD`.

### 3. Rozdělení práce
Podle plánu architekta urči, které agenty spustit:
- Pouze FE změny → `developer-fe` + `designer-ux` paralelně
- Pouze BE změny → `developer-be`
- FE + BE → `developer-fe`, `designer-ux` a `developer-be` paralelně
- Obecné / nerozlišené → `developer`

### 4. Implementace
Spusť příslušné developer agenty s:
- Obsahem story
- Implementačním plánem architekta včetně výtahu kontextu z V2 (**agenti nečtou V2 přímo**)
- Instrukcí pracovat v aktuální git větvi
- Instrukcí nikdy nepushovat do main bez schválení
- **Instrukcí číst dokumentaci před zdrojovým kódem — zdroják jen kde je to nutné**

`designer-ux` dostane navíc:
- UX pravidla z `.claude/config.md` (Material Design 3 pro non-Task-forge epics)
- Instrukcí řídit se https://m3.material.io/components

Počkej až všechny paralelní agenty skončí.

Po dokončení každého volání přečti `total_tokens` z bloku `<usage>` ve výsledku agenta:
- `cost_developer_fe = tokens_fe / 1_000_000 × 6`
- `cost_developer_be = tokens_be / 1_000_000 × 6`
- `cost_designer_ux = tokens_ux / 1_000_000 × 6`

(USD, blended Sonnet 4.6: $3/MTok input, $15/MTok output, ~60/40 split → ~$6/MTok)

### 5. Aktualizace stories
Pro každou implementovanou story:

Aktualizuj status v lokálním wiki souboru (oba formáty):
```bash
sed -i '' 's/^- Status: .*/- Status: ready_for_testing/' wiki/stories/{ID}.md
sed -i '' 's/^status: .*/status: ready_for_testing/' wiki/stories/{ID}.md
python3 task-forge/status_history.py append wiki/stories/{ID}.md ready_for_testing
python3 task-forge/status_history.py metrics wiki/stories/{ID}.md
```

Aktualizuj GitHub issue body (přepíše tělo včetně nového statusu) a přidej label:
```bash
gh issue edit {číslo} --repo {Main_repo z config} --body "$(cat wiki/stories/{ID}.md)"
gh issue edit {číslo} --repo {Main_repo z config} --add-label "ready for testing"
```

Vypočti agregované hodnoty:
- `cost_implement_total = součet cost všech spuštěných developer agentů`
- `implement_duration` = čas od `implement_start` do teď (formát: `{m}m {s}s` nebo `{h}h {m}m`)

Připrav řádek implementace (zahrň jen spuštěné agenty):
```
- Implementace: $X.XXXX · Dev FE $X.XXXX · Dev BE $X.XXXX · Designer $X.XXXX · čas {duration}
```

Zapiš/přepiš sekci `## Metriky` v `wiki/stories/{ID}.md` pomocí Edit nástroje.
Zachovej existující řádek `- Analýza:` pokud je. Přepiš řádek `- Implementace:` a přepočítej `- Celkem:`.

Výsledná sekce (příklad s oběma fázemi):
```markdown
## Metriky
- Analýza: $0.063 · PO $0.007 · CD $0.003 · Arch $0.053 · čas 4m 12s
- Implementace: $0.120 · Dev FE $0.072 · Dev BE $0.048 · čas 1h 8m
- Celkem: $0.183
```

Pokud `<usage>` blok chybí, použij `$0.0000`.

### 6. Reportuj výsledek
```
Implementace dokončena:
- Stories: {seznam ID}
- Větev: {větev}
- Změněné soubory: {seznam}
- Story status: ready_for_testing
- Až budeš hotov: /pr
```

## Pravidla
- Vše provádět autonomně, bez potvrzování uživatelem
- Nikdy nepushovat do main bez schválení
- Pokud jakýkoli agent selže, zastav a informuj uživatele
- Přílohy ze `wiki/stories/assets/{ID}/` předej agentům jako kontext
- Developer agenti nečtou V2 přímo — dostanou výtah od architekta
