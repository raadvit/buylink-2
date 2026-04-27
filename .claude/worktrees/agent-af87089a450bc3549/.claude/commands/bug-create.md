# Vytvoření bug issue na GitHubu

> Názvy repozitářů čti ze souboru `.claude/config.md`.

Vytvoř GitHub issue pro bug v repozitáři **Main_repo** (z config).

## Vstup

`$ARGUMENTS` může obsahovat stručný popis bugy. Pokud chybí nebo je neúplný, zeptej se na:
1. Název / stručný popis (jedna věta)
2. Popis chyby
3. Kroky k reprodukci
4. Očekávané chování

Ptej se po jedné otázce najednou, dokud nemáš vše potřebné.

## Postup

1. **Sestav title** ve formátu: `[BUG] Stručný popis`

2. **Sestav body issue**:

```
## Popis
{co se děje}

## Kroky k reprodukci
1. 
2. 

## Očekávané chování
{co by se mělo stát}



4. **Vytvoř issue** přes `gh`:

```bash
gh issue create \
  --repo {Backend repozitář z config} \
  --title "[BUG] {TITLE}" \
  --body "{BODY}" \
  --label "{LABELS}"
```

5. **Reportuj výsledek**: `Issue vytvořeno: {URL}`

## Pravidla
- Jeden příkaz = jeden bug issue
- Pokud `gh` není dostupný nebo uživatel není přihlášen, informuj ho: `gh auth login`
