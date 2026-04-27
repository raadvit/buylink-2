# Implementace user story

Provede celý implementační cyklus od načtení story přes refinement s týmem až po naprogramování. Vše provádí autonomně bez potvrzování.

## Vstup

`$ARGUMENTS` musí obsahovat ID story (např. `US-002`). Pokud chybí, zavolej `/user-story-read` bez argumentu pro výběr.

## Postup

### 1. Načti story a technický kontext
Zavolej `/user-story-read {ID}` a načti obsah story.

Pokud je `Status` jiný než `draft` nebo `validated`, informuj uživatele a pokračuj:
- `in_development` → "Story se již implementuje, pokračuji."
- `ready_for_testing` / `done` → "Story je hotová, pokračuji na žádost."

Načti index dokumentace:
```bash
cat wiki/INDEX.md 2>/dev/null || echo "(index neexistuje)"
```

### 2. Refinement s týmem (architekt)
Spusť agenta `architekt` s:
- Obsahem story
- Obsahem `wiki/INDEX.md` z kroku 1
- Zadáním:
  - Podle indexu urči dotčené komponenty a načti **jen jejich** dokumenty z `wiki/components/` a `wiki/technical/`
  - Zdrojový kód čti pouze tam, kde doc chybí nebo nestačí
  - Navrhni implementační plán, identifikuj rizika a závislosti
  - Rozděl práci na konkrétní úkoly pro developery
  - Odhadni složitost (low / medium / high)

### 3. Rozdělení práce
Podle plánu architekta urči, které agenty spustit:
- Pouze FE změny → `developer-fe`
- Pouze BE změny → `developer-be`
- FE + BE → `developer-fe` a `developer-be` paralelně
- Obecné / nerozlišené → `developer`

### 4. Implementace
Spusť příslušné developer agenty s:
- Obsahem story
- Implementačním plánem architekta
- Technickou dokumentací dotčených komponent (z `wiki/technical/`, `wiki/components/`)
- Instrukcí pracovat v aktuální git větvi
- Instrukcí nikdy nepushovat do main bez schválení
- **Instrukcí číst dokumentaci před zdrojovým kódem — zdroják jen kde je to nutné**

Každý agent implementuje svoji část. Pokud běží paralelně (FE + BE), počkej až oba skončí.

### 5. Aktualizace dokumentace
Spusť `dokumentarista` **pouze pokud** implementace zahrnuje alespoň jedno z:
- Nový nebo změněný API endpoint (request/response shape)
- Nová komponenta nebo modul
- Změna datového modelu nebo závislostí mezi vrstvami

Pokud jde jen o CSS, layout, přejmenování nebo čistě vizuální změny — krok přeskoč.

Při spuštění předej:
- Seznam změněných souborů
- Implementační plán architekta
- Zadání: aktualizuj dokumenty dotčených komponent v `wiki/technical/` a `wiki/components/` a udržuj `wiki/INDEX.md` — husté fakty, ne prose

### 6. Aktualizace story
```bash
sed -i '' 's/^- Status: .*/- Status: in_development/' wiki/stories/{ID}.md
gh issue edit {číslo} --repo raadvit/BuyLink --add-label "ready for testing"
```

### 7. Reportuj výsledek
```
Implementace {ID} dokončena:
- Větev: {větev}
- Změněné soubory: {seznam}
- Story status: in_development
- Až budeš hotov se skupinou stories: /pr
```

## Pravidla
- Vše provádět autonomně, bez potvrzování uživatelem
- Nikdy nepushovat do main bez schválení
- Pokud jakýkoli agent selže, zastav a informuj uživatele
- Přílohy ze `wiki/stories/assets/{ID}/` předej agentům jako kontext
- `wiki/INDEX.md` je primární navigace — zdrojový kód je záloha
