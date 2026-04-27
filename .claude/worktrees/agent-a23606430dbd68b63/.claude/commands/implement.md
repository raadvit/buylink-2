# Implementace user story

> Názvy repozitářů a UX pravidla čti ze souboru `.claude/config.md`.

Provede celý implementační cyklus od načtení story přes refinement s týmem až po naprogramování. Vše provádí autonomně bez potvrzování.

## Vstup

`$ARGUMENTS` může obsahovat jedno nebo více čísel stories oddělených čárkou (např. `2,6,23` nebo jen `5`).
Čísla odpovídají suffixu ID souboru (2 → `US-002`). Pokud chybí, zavolej `/user-story-read` bez argumentu pro výběr.

## Postup

### 1. Načti stories a technický kontext
Parsuj `$ARGUMENTS` jako čárkou oddělený seznam čísel. Každé číslo převeď na ID ve formátu `US-{číslo s nulami na 3 cifry}` (2 → `US-002`, 23 → `US-023`).

Pro každou story zavolej `/user-story-read {ID}` a načti její obsah.

Pokud je u některé story `Status` jiný než `validated`, informuj uživatele:
- `draft` → "Story {ID} nebyla technicky anotována architektem — přeskoč nebo oprav před implementací."
- `in_development` → "Story {ID} se již implementuje, pokračuji."
- `ready_for_testing` / `done` → "Story {ID} je hotová, pokračuji na žádost."

### 2. Refinement — Architekt (analýza)
Přečti `.claude/config.md`, hodnotu `architect_creates_implementation_plan`.

Pokud je `true`: zkontroluj, zda story obsahuje sekci `## Implementační plán`. Pokud ano, použij ji přímo jako plán a **přeskoč spuštění Architekta** — nastav `cost_arch_analysis = 0.0000 USD` a pokračuj krokem 3.

Pokud sekce chybí nebo config je `false`: spusť agenta `architekt` s:
- Obsahem **všech** načtených stories
- `memory-system/V1 - static context/context.md`
- `memory-system/V1 - static context/constraints.md`
- Relevantními sekcemi `memory-system/V2 - Shared Truth/domain_model.md` (dle `reads_sections` ze stories)
- `memory-system/V2 - Shared Truth/story_register.md`
- Zadáním dle `agents/team/architekt.md`:
  - Podle domain_model urči dotčené komponenty a závislosti
  - Zdrojový kód čti pouze tam, kde V2 nestačí
  - Navrhni implementační plán, identifikuj rizika a závislosti
  - Rozděl práci na konkrétní úkoly pro BE / FE
  - Odhadni složitost (low / medium / high)
  - Výstup musí obsahovat: seznam dotčených souborů, popis změn, datový model / API kontrakt, pořadí kroků, **výtah relevantního kontextu z V2 pro developery**

Po dokončení volání přečti `total_tokens` z bloku `<usage>` ve výsledku agenta a ulož jako `tokens_arch`. Cena: `cost_arch_analysis = tokens_arch / 1_000_000 × 6` (USD, blended Sonnet 4.6).

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

Aktualizuj status:
```bash
sed -i '' 's/^- Status: .*/- Status: ready_for_testing/' wiki/stories/{ID}.md
gh issue edit {číslo} --repo {Main_repo z config} --add-label "ready for testing"
```

Přidej sekci implementačních nákladů do `wiki/stories/{ID}.md` pomocí Edit nástroje — vlož **před** existující `- Validace cena:` řádek:
```
- Implementace cena: ${součet všech nákladů implementace}
  - Architekt plán: ${cost_arch_analysis}
  - Developer FE: ${cost_developer_fe}     ← jen pokud byl spuštěn
  - Developer BE: ${cost_developer_be}     ← jen pokud byl spuštěn
  - Designer UX: ${cost_designer_ux}       ← jen pokud byl spuštěn
```
Pokud `<usage>` blok chybí nebo `total_tokens` není k dispozici, použij `0.0000 USD`. Vždy zapiš všechny podpoložky agentů, kteří byli spuštěni — i při nulové ceně.

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
