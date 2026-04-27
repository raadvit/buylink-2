# PR a merge do main

Vytvoří pull request z aktuální větve, provede code review a mergne do main.

## Postup

### 1. Zjisti stav větve
```bash
git log main..HEAD --oneline
git diff main --stat
```
Vypiš: počet commitů, změněné soubory.

### 2. Code review
Spusť agenta `code-reviewer` s celým diffem oproti main:
```bash
git diff main
```

Pokud code reviewer najde problémy:
- **Kritické** → zastav, informuj uživatele, oprav před PR
- **Doporučení** → zahrň do PR description

### 3. Vytvoř PR
```bash
gh pr create \
  --repo raadvit/BuyLink \
  --base main \
  --title "{stručný název dle commitů}" \
  --body "..."
```

PR description má obsahovat:
- Co bylo implementováno (seznam GitHub issues #XX)
- Doporučení z code review (pokud nějaká)
- Co testovat

### 4. Merge
```bash
gh pr merge {číslo} --repo raadvit/BuyLink --squash --delete-branch
```

### 5. Vytvoř novou feature větev pro další práci
```bash
git checkout main && git pull
git checkout -b feature/next
```

### 6. Reportuj
```
PR #{číslo} mergnut do main.
Nová větev: feature/next
```

## Pravidla
- Nikdy nepushuj přímo do main (vždy přes PR)
- Squash merge — jeden čistý commit na main za skupinu stories
- Po mergu vždy vytvoř novou větev pro další práci
