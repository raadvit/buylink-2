# Vytvoření user story

> Názvy repozitářů čti ze souboru `.claude/config.md`.

Proveď uživatele strukturovaným zadáním nové feature, zvaliduj zadání s týmem a vytvoř user story jako GitHub issue + wiki soubor.

## Vstup

`$ARGUMENTS` může obsahovat stručný popis záměru nebo kompletní formulář. Pokud data chybí nebo jsou neúplná, ptej se po jedné otázce najednou:

1. **Epic** — vyber z: EP-01 BuyLink / EP-02 Administrace / EP-03 Platba / EP-04 Košík / EP-05 Doručení / EP-06 Escrow výplata / EP-07 Notifikace / EP-08 Customer service
2. **Role** — `buyer` / `seller` / `admin` / `api`
3. **Název** — jedna věta
4. **Business popis** — "Jako [role] chci [akce] aby [přínos]"
5. **Co se zobrazuje** — pole, sekce, komponenty viditelné na obrazovce
6. **Jak se to chová** — interakce, podmíněná logika, stavy, validace
7. **Přílohy** — screenshoty, HTML prototypy, diagramy (volitelné — uživatel může přeskočit)
8. **Out of scope / after MVP** — co záměrně neřešíme (volitelné)
9. **Závislosti a otevřené otázky** — co zatím nevíš (volitelné)

Pokud `$ARGUMENTS` obsahuje všechna povinná pole (1–6), přeskoč otázky a vytvoř story přímo.

## Postup

### 1. Sbírání vstupů
Ptej se po jedné otázce najednou. Pokud uživatel napíše "vygeneruj" nebo "viz výše", odvoď odpověď z kontextu.

### 2. Validace týmem (product-owner agent)
Po získání všech povinných vstupů spusť interní review:
- Je business popis srozumitelný?
- Jsou AC testovatelné?
- Chybí edge cases?
- Má story dopad na notifikace (EP-07), platby (EP-03) nebo externí API?

Pokud jsou nejasnosti, polož uživateli max 3 doplňující otázky (jedna po druhé) a počkej na odpovědi.

### 3. Urči ID nové story
```bash
ls wiki/stories/*.md 2>/dev/null | grep -oE 'US-[0-9]+' | sort -t- -k2 -n | tail -1
```
Vezmi nejvyšší číslo + 1. Pokud žádné soubory nejsou, začni od `US-001`.

### 4. Zkopíruj přílohy
Pokud uživatel přiložil soubory (screenshoty, HTML, diagramy):
```bash
mkdir -p wiki/stories/assets/{ID}
cp {zdrojový soubor} wiki/stories/assets/{ID}/
```
Odkazuj na ně relativní cestou `assets/{ID}/{soubor}` — nikdy absolutní cestou.

### 5. Vytvoř wiki/stories/{ID}.md
Použij šablonu z `wiki/story-teamplate.md`:

```markdown
# {ID}: {Název}

## Metadata
- Epic: {epic}
- Role: {role}
- Status: draft
- GitHub: #{doplň po vytvoření issue}
- Vytvořeno: {dnešní datum}
- Změněno: {dnešní datum}

## Business popis
Jako {role} chci {akce} aby {přínos}.

{Co a proč — 1–2 věty pro byznys.}

## Description
{Co se zobrazuje, jak se to chová, technické detaily.}

## Acceptance criteria
- [ ] {AC 1}
- [ ] {AC 2}
- [ ] {AC 3}

## Test cases
- [ ] Happy path: {scénář}
- [ ] Edge case: {scénář}
- [ ] Chybový stav: {scénář}

## Assets
- {typ}: assets/{ID}/{soubor}   ← pouze pokud příloha existuje

## Poznámky agenta
{postřehy z validace — dopady na jiné epicy, otevřené otázky}
```

### 6. Vytvoř GitHub issue
```bash
gh issue create \
  --repo {Hlavní repozitář z config} \
  --title "[STORY][{epic}] {Název}" \
  --body "{obsah shodný s wiki souborem}"
```
Pokud `gh` selže kvůli chybějícím labelům, vytvoř issue bez labelů.

### 7. Doplň číslo issue do wiki souboru
Aktualizuj řádek `GitHub:` v `wiki/stories/{ID}.md`.

### 8. Reportuj výsledek
```
Story vytvořena:
- ID: {ID}
- Soubor: wiki/stories/{ID}.md
- GitHub issue: {URL}
```

## Pravidla
- Story je vždy `Status: draft` při vytvoření
- Přílohy vždy kopíruj do `wiki/stories/assets/{ID}/`, nikdy neodkazuj na absolutní lokální cesty
- Pokud `gh` není dostupný: `gh auth login`
- Jeden příkaz = jedna story
