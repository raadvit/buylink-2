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
Zapamatuj si cenu tohoto volání jako `cost_arch_analysis`.
Spusť agenta `architekt` s:
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

### 3. Rozdělení práce
Podle plánu architekta urči, které agenty spustit:
- Pouze FE změny → `developer-fe` + `designer-ux` paralelně
- Pouze BE změny → `developer-be`
- FE + BE → `developer-fe`, `designer-ux` a `developer-be` paralelně
- Obecné / nerozlišené → `developer`

### 4. Implementace
Zapamatuj si ceny jednotlivých agent volání: `cost_developer_fe`, `cost_developer_be`, `cost_designer_ux` (podle toho co spustíš).
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

### 5. Aktualizace stories
Pro každou implementovanou story:

Aktualizuj status:
```bash
sed -i '' 's/^- Status: .*/- Status: ready_for_testing/' wiki/stories/{ID}.md
gh issue edit {číslo} --repo {Main_repo z config} --add-label "ready for testing"
```

Přidej sekci implementačních nákladů do `wiki/stories/{ID}.md` pomocí Edit nástroje — vlož za existující `- Validace cena:` blok:
```
- Implementace cena: ${součet všech nákladů implementace}
  - Architekt (analýza): ${cost_arch_analysis}
  - Backend Developer: ${cost_developer_be}      ← jen pokud byl spuštěn
  - Frontend Developer: ${cost_developer_fe}     ← jen pokud byl spuštěn
  - UX Designer: ${cost_designer_ux}             ← jen pokud byl spuštěn
```
Pokud cena agenta není dostupná, použij `N/A`.

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
