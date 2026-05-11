# Analýza — Product Owner

Fáze Product Owner z validačního pipeline. Zlepší kvalitu story — doplní, zpřesní a přepíše sekce tak, aby story byla jasná a připravená pro technický pipeline. Doplní `reads_sections` / `writes_sections`.

Po dokončení uloží výsledek do US souboru a aktualizuje GitHub issue.

## Live komunikace s uživatelem (IPC)

`TF_SESSION_ID` a `TF_API_PORT` jsou nastaveny v prostředí (env). Používej je pro live zprávy a otázky — uživatel je vidí v chatu okamžitě.

**Poslat zprávu** (informativní, nezastaví pipeline):
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"ZPRÁVA\",\"agent\":\"JMÉNO\"}" || true
```

**Zeptat se uživatele** (zastaví pipeline dokud neodpoví):
```bash
QID=$(python3 -c "import uuid; print(uuid.uuid4())")
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"question\",\"text\":\"OTÁZKA\",\"agent\":\"JMÉNO\",\"question_id\":\"${QID}\"}" || true
ANSWER="" TF_WAIT=0
while [ -z "$ANSWER" ] && [ "$TF_WAIT" -lt 300 ]; do
  sleep 2; TF_WAIT=$((TF_WAIT + 1))
  ANSWER=$(curl -sf "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/answer/${QID}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer','') if d.get('answered') else '')" 2>/dev/null || echo "")
done
if [ -z "$ANSWER" ]; then
  curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
    -H "Content-Type: application/json" \
    -d "{\"type\":\"message\",\"text\":\"Odpověď nedorazila (10 min), rozhoduji sám na základě dostupného kontextu.\",\"agent\":\"Product Owner\"}" || true
fi
```

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 0. Inicializace

Zaznamenej čas začátku (`po_start`). Připrav `cost_po = 0.0`, `tokens_po = 0`.

```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Product Owner kontroluje a zlepšuje story…\",\"agent\":\"Product Owner\"}" || true
```

### 1. Načti story a kontext

Načti `wiki/stories/US-{id}.md`.

Přečti `.claude/config.md` — hodnota `generate_acceptance_criteria`.

Načti `.memory-system/V1-static-context/project.md` a `.memory-system/V2-shared-truth/story_register.md`.

Pokud wiki soubor obsahuje řádek `- Figma_image: <cesta>`, načti soubor `wiki/stories/<cesta>` pomocí Read nástroje. Obrázek je referenční vstup — PO ho použije k lepšímu pochopení a rozepsání stávajícího popisu chování. Obrázek pomáhá konkretizovat a doplnit `## Jak se to chová` — PO vidí skutečné UI prvky, jejich stavy a rozmístění, a díky tomu může existující popis rozepsat přesněji a doplnit co autor vynechal. Sekci `## Co se zobrazuje` z obrázku nepřepisuje.

### 2. Spusť agenta Product Owner

Spusť agenta `product-owner` (instrukce v `.memory-system/team/product-owner.md`) s:
- Obsahem story
- Figma screenshot (pokud existuje — viz krok 1)
- Obsahem `project.md`
- Obsahem `story_register.md`

**Před analýzou zkontroluj sekci `## Clarify`** ve story souboru. Pokud existuje:
- Přečti otázky a jejich odpovědi (formát `1. otázka → odpověď`)
- Předej je agentovi jako kontextová rozhodnutí — zapracuje je do analýzy
- Informuj uživatele:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Nalezeny odpovědi na clarify otázky — zapracovávám do analýzy.\",\"agent\":\"Product Owner\"}" || true
```

**Agent provede zlepšení sekce po sekci** (viz `product-owner.md`):
- `## Why / Business Goal` — zpřesní záměr, pojmenuje byznys problém, odstraní vágní formulace
- `## Co se zobrazuje` — **přeskoč pokud story obsahuje řádek `- Figma:` nebo `- Figma_image:`** — vizuální popis zajišťuje Figma, PO do této sekce nezasahuje
- `## Jak se to chová` — **povinně** přepiš celou sekci: každá podsekce musí mít konkrétní obsah; prázdná podsekce (obsahuje jen `-`) musí být doplněna nebo označena v `## Clarify`; TBD musí být adresováno
- `## Rizikové situace` — byznys rizika (přidá pokud chybí)
- `## Acceptance Criteria` — testovatelná AC ve formátu `Když [podmínka], pak [výsledek]`, min. 3

Doplní `reads_sections` a `writes_sections` v Memory Contract.

**PO nesmí klást otázky uživateli v chatu.** Pouze pokud záměr obsahuje zásadní nejasnost (více interpretací s různým dopadem na scope), nastav `needs-clarify` a zapiš otázky do sekce `## Clarify`:

```bash
sed -i '' 's/^- Status: .*/- Status: needs-clarify/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md needs-clarify
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Story má zásadní nejasnosti. Odpověz na otázky v sekci Clarify a spusť analýzu znovu.\",\"agent\":\"Product Owner\"}" || true
```

Pokud `needs-clarify`: zapiš metriky (krok 3) a zastav.

### 3. Zapiš zlepšenou story do wiki

Zapiš výsledek agenta zpět do `wiki/stories/US-{id}.md`. Zachovej:
- Metadata sekci (Epic, Role, GitHub, Status, status_history)
- Sekce vyplněné Architektem (`## Architecture Notes`, `## Implementation Plan` a podobné) — pokud existují, nesahej na ně
- Sekci `## Clarify` — pokud existuje, zachovej ji beze změny
- Sekci `## Metriky` — pokud existuje, zachovej ji beze změny

Přepiš: `## Why / Business Goal`, `## Jak se to chová`, `## Rizikové situace`, `## Acceptance Criteria`.
`## Co se zobrazuje` přepiš pouze pokud story **neobsahuje** řádek `- Figma:` ani `- Figma_image:` — jinak tuto sekci nechej beze změny.

### 4. Metriky a uložení

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_po = total_tokens`
- `cost_po = tokens_po / 1_000_000 × 2.08`

`po_duration` = čas od `po_start` (zaokrouhli na sekundy). Formát: `{n}s` / `{m}m {s}s` / `{h}h {m}m`.

Zapiš/přepiš řádek `- Analýza PO:` v sekci `## Metriky` wiki souboru (zachovej ostatní řádky):
```
- Analýza PO: $X.XXXX · čas {po_duration}
```
Pokud sekce `## Metriky` neexistuje, přidej ji na konec souboru.

Pokud nebyl `needs-clarify`, aktualizuj status:
```bash
sed -i '' 's/^- Status: .*/- Status: conflict-check/; s/^status: .*/status: conflict-check/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md conflict-check
```

Synchronizuj wiki soubor s issue systémem přes provider:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT:-5001}/api/issues/{číslo}/sync-wiki" || \
  echo "Warning: sync-wiki selhal — wiki soubor byl aktualizován, issue nikoli." >&2
```

## Pravidla
- Nikdy necommituj změny do gitu
- Pokud `<usage>` blok chybí, použij `$0.0000`
- Nezasahuj do sekcí architektury ani implementace
