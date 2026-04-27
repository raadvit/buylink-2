# Načtení user story

Načte a zobrazí user story ze `wiki/stories/` podle ID.

## Vstup

`$ARGUMENTS` musí obsahovat ID story ve formátu `US-XXX`. Pokud chybí, vypiš seznam dostupných stories:

```bash
ls wiki/stories/*.md | grep -oE 'US-[0-9]+'
```

a zeptej se: "Které ID chceš načíst?"

## Postup

### 1. Načti soubor
```bash
cat wiki/stories/{ID}.md
```

Pokud soubor neexistuje, vypiš: "Story {ID} nenalezena. Dostupné stories:" a seznam.

### 2. Zobraz story
Vypiš obsah story přehledně — nezměněný markdown.

### 3. Vrať strukturovaná data
Po zobrazení vrať story jako strukturovaný objekt pro případné volání z jiného skillu:

```
STORY_ID: {ID}
STORY_EPIC: {epic}
STORY_ROLE: {role}
STORY_TITLE: {název}
STORY_STATUS: {status}
STORY_FILE: wiki/stories/{ID}.md
```

## Pravidla
- Pouze čte, nikdy nemění soubor
- Pokud ID není ve formátu US-XXX, oprav ho automaticky (např. "2" → "US-002")
