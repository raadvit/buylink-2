# Worktrees — paralelní implementace

## Proč

Pro paralelní práci: každá story ve `status=in_development` má vlastní git worktree. Důvody:

1. **Paralelní práce.** Více stories může být `in_development` současně, každá v izolovaném pracovním adresáři.
2. **Žádné stash / context switching.** Developer agent (nebo člověk) skočí mezi stories bez ztráty rozdělané práce.
3. **Izolace selhání.** Pokud story selže (testy, build), nezasáhne to ostatní worktrees.
4. **Atomicita.** Jeden worktree = jedna story = jeden branch = jeden PR.

## Setup

```bash
# Hlavní repo (clone)
cd ~/projects/{project-name}
ls
# .git/  app/  wiki/  memory-system/

# Vytvoření worktree pro story
git worktree add ../worktrees/us-007 -b story/us-007-create-order

# Po vytvoření:
ls ~/projects/
# {project-name}/
# worktrees/us-007/   ← nový adresář s checkoutnutým branchem
```

## Konvence

| Položka | Pravidlo |
|---|---|
| Cesta | `../worktrees/us-NNN/` (relativní k hlavnímu repu) |
| Branch | `story/us-NNN-{slug}` |
| Slug | kebab-case z title story, max 30 znaků |
| Životnost | od `status=in_development` po merge + cleanup |

## Workflow integrace

```
Trigger /implement-be nebo /implement-fe US-NNN
      │
      ▼
Vytvoří worktree:
  git worktree add ../worktrees/us-NNN -b story/us-NNN-{slug}
      │
      ▼
Status story → in_development
      │
      ▼
Developer pracuje v ../worktrees/us-NNN/
  - BE Developer první (pokud full-stack)
  - FE Developer pokračuje na stejné branchi
      │
      ▼
Push branch, otevře PR
      │
      ▼
Code Review APPROVE → ready_for_testing
      │
      ▼
Human Reviewer: manuální QA → PASS → merge (squash)
      │
      ▼
Cleanup:
  git worktree remove ../worktrees/us-NNN
  git branch -d story/us-NNN-{slug}
      │
      ▼
Status story → done
```

## Pravidla

### Jeden branch jen v jednom worktree

Git neumožní checkout stejného branche ve dvou worktrees. To je pojistka — žádné dva worktrees nemodifikují stejný branch.

### Hlavní worktree = main

V hlavním adresáři je vždy checkoutnut `main`. Tam **neimplementujeme stories**, jen z něj větvíme.

### Sdílené `.git`, sdílené konfigurace

Všechny worktrees sdílí:
- git history
- remoty
- git config
- pre-commit hooks (instalují se v `.git/hooks/`)

Co **nesdílí:**
- working directory
- staged / unstaged změny
- `.env` soubory (každý worktree má vlastní lokální konfiguraci)

### Database per worktree

Každý worktree by měl mít vlastní lokální DB instanci nebo schema:
- `{project}_us_007` (pro worktree us-007)
- `{project}_us_008` (pro worktree us-008)

Důvod: paralelní migrace nesmí kolidovat. Konvence jména DB v `.env.local`.

### Limity

- Doporučeno max **5 paralelních worktrees** (víc = chaos pro pilot tým).
- Pokud agent má spustit story a všech 5 slotů je obsazeno, čeká.

## Cleanup

Po mergi PR:

```bash
# Z hlavního repa
git worktree remove ../worktrees/us-NNN
git branch -d story/us-NNN-{slug}
```

Pokud worktree měl uncommittnuté změny (nemělo by se stát po mergi), git odmítne. V tom případě:
- pokud změny chceme: commit + push, nebo `git stash` + apply jinde
- pokud změny nechceme: `git worktree remove --force`

## Časté chyby

| Chyba | Řešení |
|---|---|
| `fatal: 'X' is already checked out at...` | Branch je v jiném worktree. Najdi `git worktree list`. |
| Worktree existuje, ale adresář je smazán | `git worktree prune` uklidí orphan reference. |
| Migrace na produkční DB z worktree | NIKDY. Lokální DB only. |
| Push do mainu z worktree branche | Konvence: jen Human Reviewer mergne přes GitHub UI. |

## Status: aktivace

Doporučení: **aktivovat worktrees až po prvních 3 testovacích storiích sekvenčně**. Důvod: nejdřív validovat, že pipeline funguje, pak přidat paralelizaci.

## Skripty (k vytvoření v `scripts/`)

`scripts/start_implementation.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

STORY_ID="$1"  # např. US-007
SLUG="$2"      # např. create-order

WORKTREE_PATH="../worktrees/us-${STORY_ID#US-}"
BRANCH="story/us-${STORY_ID#US-}-${SLUG}"

# Vytvoření worktree
git worktree add "$WORKTREE_PATH" -b "$BRANCH" main

# Setup lokálního prostředí
cd "$WORKTREE_PATH"
cp ../../{project}/.env.example .env.local
sed -i "s|DB_NAME=.*|DB_NAME={project}_us_${STORY_ID#US-}|" .env.local

# Vytvoření DB (pokud BE projekt)
createdb "{project}_us_${STORY_ID#US-}"
alembic upgrade head

echo "Worktree ready: $WORKTREE_PATH"
echo "Branch: $BRANCH"
```

`scripts/cleanup_worktree.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

STORY_ID="$1"

WORKTREE_PATH="../worktrees/us-${STORY_ID#US-}"
BRANCH=$(cd "$WORKTREE_PATH" && git branch --show-current)

# Drop lokální DB
dropdb "{project}_us_${STORY_ID#US-}" --if-exists

# Remove worktree
git worktree remove "$WORKTREE_PATH"
git branch -d "$BRANCH"

echo "Cleaned up: $WORKTREE_PATH"
```
