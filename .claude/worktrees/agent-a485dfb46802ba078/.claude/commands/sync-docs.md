# Synchronizace domain modelu

Aktualizuje `memory-system/V2 - Shared Truth/domain_model.md` o změny z posledního commitu.

## Postup

### 1. Zjisti změněné soubory

```bash
git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only
```

Vypiš seznam.

### 2. Přečti změny a domain model

```bash
git diff HEAD~1 HEAD -- <soubory> 2>/dev/null || git diff -- <soubory>
```

Přečti také celý `memory-system/V2 - Shared Truth/domain_model.md`.

### 3. Aktualizuj domain model

Porovnej diff se stávajícím domain modelem. Uprav pouze to, co se skutečně změnilo:

- **Nová funkce / endpoint / chování** → přidej nebo doplň relevantní SECTION
- **Odebraná funkcionalita** → odstraň nebo označ jako REMOVED v příslušné SECTION
- **Přejmenování / refactor** → aktualizuj existující záznamy
- **Beze změny** → nesahej na sekce, kterých se diff netýká

Pravidla pro domain model:
- Struktura: `<!-- SECTION: název -->` ... `<!-- /SECTION: název -->`
- Styl: husté fakty — funkce, parametry, podmínky, typy; žádná prose
- Jazyk: čeština
- Pokud sekce neexistuje a změna je dostatečně obecná (bude ji číst Architekt nebo Conflict Detector), vytvoř novou

### 4. Reportuj

Vypiš které sekce v domain_model.md byly změněny a proč (1 řádek na sekci).