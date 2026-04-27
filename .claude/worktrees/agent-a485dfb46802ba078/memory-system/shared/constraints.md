# Globální omezení — platí pro všechny agenty

Tato pravidla jsou nadřazená definicím jednotlivých agentů. Každý agent je musí dodržovat, i když nejsou explicitně zmíněna v jeho definici.

## Bezpečnost

- Nikdy nepiš hardcoded credentials, tokeny, API klíče ani hesla — vždy env vars nebo secrets manager
- Veškerá business logika patří výhradně na backend
- Všechny uživatelské vstupy jsou validovány na serveru — frontend validace je pouze UX vrstva
- Uživatel smí přistupovat pouze ke svým vlastním datům

## Git a produkce

- **Nikdy nepushuj do main** bez explicitního schválení — pracuj v git worktree nebo feature větvi
- **Nikdy nespouštěj produkční systém** — pouze čti a edituj kód
- Před každou změnou přečti dotčený soubor celý

## Kódová kvalita

- Žádné komentáře popisující CO — pouze WHY, pokud je chování neobvyklé nebo neintuitivní
- Konzistentní pojmenování s existujícím kódem projektu
- Žádný mrtvý kód ani zakomentované bloky
- Žádné abstrakce nad rámec zadání

## Komunikace a výstupy

- Komunikuj česky, pokud není domluveno jinak
- Buď stručný a konkrétní — žádné zbytečné sekce ani chváloslov
- Výstupy předávej v dohodnutém formátu pro navazující agenty (viz `agents.md`)

## Externí volání

- Vždy nastav timeout pro všechna volání externích API
- Implementuj retry logiku pro kritická volání
- Selhání externího systému nesmí ponechat transakci nebo stav systému v neurčitém stavu
- Ulož stav před každým externím voláním
