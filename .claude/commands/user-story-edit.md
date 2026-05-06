# Editace user story

> Názvy repozitářů čti ze souboru `.claude/config.md`.

Uprav existující user story — aktualizuj GitHub issue i lokální soubor `wiki/stories/`.

## Vstup

`$ARGUMENTS` může obsahovat ID story (např. `US-003`) nebo číslo GitHub issue (např. `#12`).
Pokud chybí, zeptej se uživatele: "Které story chceš upravit? (zadej ID, např. US-003, nebo číslo GitHub issue)"

## Postup

### 1. Najdi story

**Pokud znáš ID (US-XXX):**
```bash
cat wiki/stories/[ID].md
```

**Pokud znáš číslo GitHub issue:**
```bash
gh issue view {číslo} --repo {Hlavní repozitář z config}
```
Pak najdi odpovídající soubor v `wiki/stories/` podle čísla v poli `GitHub:`.

### 2. Zobraz aktuální obsah uživateli

Ukaž mu stávající hodnoty a zeptej se co chce změnit. Nabídni možnosti:
- Název
- Business popis
- Acceptance criteria
- Test cases
- Status (draft → review → done)
- Epic
- Description
- Poznámky agenta

Ptej se po jedné změně najednou, nebo nech uživatele popsat vše najednou.

### 2b. Figma analýza (pokud uživatel přidává Figma URL)

Pokud uživatel zadá URL obsahující `figma.com` jako součást změn:

1. Zavolej MCP nástroj Figma pro načtení dat ze souboru.
2. Analyzuj strukturu — identifikuj obrazovky, komponenty, texty, podmíněné stavy.
3. Navrhni předvyplnění / rozšíření pro pole:
   - **Description** — co se zobrazuje, viditelné prvky
   - **Acceptance criteria** — podmínky odvozené z designu
4. Zobraz návrhy uživateli: *„Navrhuji toto doplnění na základě Figmy — chceš upravit nebo přijmout?"*
5. Počkej na odpověď, uprav dle instrukcí nebo přijmi.
6. Ulož URL jako přílohu v sekci Assets: `Figma: {URL}`

Pokud Figma MCP není dostupný, informuj: *„Nastav FIGMA_API_KEY a restartuj Claude Code."*

### 3. Aktualizuj wiki soubor

Uprav `wiki/stories/[ID].md` — změň pouze pole, která uživatel specifikoval. Aktualizuj `Změněno:` na dnešní datum.

### 4. Aktualizuj GitHub issue

```bash
gh issue edit {číslo} \
  --repo {Hlavní repozitář z config} \
  --title "[STORY][EP-0X] {Nový název}" \
  --body "{aktualizovaný obsah}"
```

Pokud se mění pouze status (draft/review/done), přidej label:
```bash
gh issue edit {číslo} --repo {Hlavní repozitář z config} --add-label "status:{nový-status}"
```

Pokud je status `done`, uzavři issue:
```bash
gh issue close {číslo} --repo {Hlavní repozitář z config}
```

### 5. Reportuj výsledek

```
Story aktualizována:
- Soubor: wiki/stories/[ID].md
- GitHub issue: {URL}
- Změněno: {co bylo upraveno}
```

## Pravidla
- Měň pouze pole, která uživatel specifikoval — nezasahuj do ostatních
- Vždy aktualizuj `Změněno:` datum v wiki souboru
- Pokud `gh` není dostupný, informuj uživatele: `gh auth login`
