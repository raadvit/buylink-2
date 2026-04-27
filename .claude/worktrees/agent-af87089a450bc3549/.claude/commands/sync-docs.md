# Synchronizace dokumentace

Spustí dokumentaristu na soubory změněné od posledního commitu nebo za posledních 24 hodin.

## Postup

### 1. Zjisti změněné soubory
```bash
git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only
```

### 2. Spusť dokumentaristu
Spusť agenta `dokumentarista` se:
- Seznamem změněných souborů z kroku 1
- Zadáním: projdi změněné soubory, aktualizuj dokumenty dotčených komponent v `wiki/components/` a `wiki/technical/`, udržuj `wiki/INDEX.md` aktuální — husté fakty (API kontrakty, datové modely, závislosti), ne prose

### 3. Reportuj výsledek
Vypiš které soubory dokumentace byly aktualizovány.
