# Instrukce pro Claude Code

## Autonomní provádění

Vše potvrzuješ sám bez ptaní uživatele. Prováděj akce přímo a bez čekání na souhlas:
- čtení souborů (Bash, Read, grep, sed -n, find…)
- editace a zápis souborů
- git commit, push, gh operace, PR
- spouštění agentů a subagentů
- mazání labelů, migrace dat

Výjimka: nevratné destruktivní operace na sdíleném stavu (force push do main, DROP TABLE, rm -rf produkčních dat) — tam zastav a informuj.

**Nikdy se neptej na potvrzení.** Uživatel to řekl opakovaně. Každý tool use prováděj přímo bez čekání.

## Konfigurace projektu

- Repozitář: `raadvit/PreciousMetals_backend`
- Hlavní větev: `main`
- Pracovní větev: `feature/next`
- Squash merge přes PR, nikdy přímý push do main

## Styl odpovědí

- Česky
- Stručně
- Bez zbytečného komentáře co jsi udělal
