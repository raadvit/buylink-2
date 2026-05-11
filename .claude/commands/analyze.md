  # Analýza user story

> Spouštěno automaticky přes `claude -p "/analyze {issue_number}"` z task-forge backendu (`story_builder.launch_analyze_agent`).
> task-forge polling sleduje změny statusu v `wiki/stories/US-{id}.md` — aktualizuj ho po každé fázi.

Provede validační pipeline pro existující story: Product Owner → Conflict Detector → Architekt.

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
    -d "{\"type\":\"message\",\"text\":\"Odpověď nedorazila (10 min), rozhoduji sám na základě dostupného kontextu.\",\"agent\":\"JMÉNO\"}" || true
fi
```

Kdy posílat zprávy:
- PO: před každou fází co děláš (`"Product Owner kontroluje srozumitelnost…"`)
- PO: pokud záměr není jasný — zeptej se otázkou místo domýšlení
- CD: při nalezení konfliktu před zápisem do wiki
- Arch: při klíčových rozhodnutích o architektuře

## Vstup

`$ARGUMENTS` = číslo issue (např. `42`). Převeď na `US-{id:03d}` (42 → `US-042`).

## Postup

### 0. Inicializace metrik

Zaznamenej čas začátku analýzy (`analyze_start`). Připrav proměnné:
- `cost_po = 0.0`, `tokens_po = 0`
- `cost_cd = 0.0`, `tokens_cd = 0`
- `cost_arch = 0.0`, `tokens_arch = 0`

### 1. Načti story a kontext

Načti `wiki/stories/US-{id}.md`.

Přečti `.claude/config.md` — hodnoty `generate_acceptance_criteria` a `architect_creates_implementation_plan`.

Pokud wiki soubor obsahuje řádek `- Figma_image: <cesta>`, načti soubor `wiki/stories/<cesta>` pomocí Read nástroje — obrázek předej Product Ownerovi jako vizuální kontext ve fázi 2.

### 2. Product Owner

Spusť agenta `product-owner` (instrukce v `.memory-system/team/product-owner.md`) s:
- Obsahem story
- Figma screenshot (pokud existuje — viz krok 1)
- `.memory-system/V1-static-context/project.md`
- `.memory-system/V2-shared-truth/story_register.md`
- Šablonou: `.memory-system/templates/story-template.md`

**Před analýzou zkontroluj sekci `## Clarify`** ve story souboru. Pokud existuje:
- Přečti otázky a jejich odpovědi (formát `1. otázka → odpověď`)
- Zapracuj odpovědi do analýzy — použij je jako kontextová rozhodnutí PO
- Informuj uživatele které odpovědi jsi použil:
```bash
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Nalezeny odpovědi na clarify otázky — zapracovávám do analýzy.\",\"agent\":\"Product Owner\"}" || true
```

**PO přepíše story do formátu šablony.** Toto je jeho hlavní úkol:
1. Přidá YAML frontmatter (`---`) s povinnými poli (`id`, `title`, `epic`, `status`, `reads`, `writes`, `depends_on`)
2. Přepíše/doplní **`## Business Context`** — proč to děláme, jaký problém řeší, pro koho
3. Přepíše/doplní **`## User Story`** — formát: *As a [role] / I want [akce] / So that [hodnota]*
4. Doplní **`## Acceptance Criteria`** — alespoň 3 konkrétní, testovatelné AC (checkbox formát). Pokud existuje Figma, AC musí pokrývat vizuální prvky ze screenshotu
5. Doplní **`## Out of Scope`** — explicitně co story NEDĚLÁ
6. Odhadne **`reads`** a **`writes`** v frontmatteru — sekce domain/api modelu, které story čte nebo mění. Pro čistě FE story bez API/DB změn: `reads: []`, `writes: []`
7. Zachová původní obsah (design popis, Figma odkaz, jak se chová) — přesune ho do správných sekcí, ale nepřepisuje vizuální specifikaci

Výstupem PO je **kompletně přepsaný wiki soubor** v šabloně. Ulož přes Edit nástroj.

**PO nesmí klást otázky uživateli v chatu.** Pokud story obsahuje zásadní nejasnosti bez odpovědí v sekci `## Clarify`, nastav `needs-clarify` a zapiš otázky:

```bash
# Přidej otázky do sekce ## Clarify v wiki souboru (nová podsekce s datem)
# Potom nastav status:
sed -i '' 's/^- Status: .*/- Status: needs-clarify/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md needs-clarify
# Pošli zprávu:
curl -sf -X POST "http://localhost:${TF_API_PORT}/api/session/${TF_SESSION_ID}/push" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"message\",\"text\":\"Story má zásadní nejasnosti. Odpověz na otázky v sekci Clarify a spusť analýzu znovu.\",\"agent\":\"Product Owner\"}" || true
# Zastav pipeline — přejdi na krok 5
```

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_po = total_tokens`
- `cost_po = tokens_po / 1_000_000 × 2.08` (Haiku 4.5: ~$2.08/MTok blended)

Po PO aktualizuj status:
```bash
sed -i '' 's/^- Status: .*/- Status: conflict-check/; s/^status: .*/status: conflict-check/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py append wiki/stories/US-{id}.md conflict-check
```

### 3. Conflict Detector

Spusť agenta `conflict-detector` (instrukce v `.memory-system/team/conflict-detector.md`) s:
- Výstupem PO (text story)
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md` (dle `reads_sections`)
- `.memory-system/V2-shared-truth/story_register.md`

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_cd = total_tokens`
- `cost_cd = tokens_cd / 1_000_000 × 2.08`

Výstup agenta je JSON:
- OK: `{"action": "ok", "affected_stories": []}`
- Konflikt: `{"action": "conflict", "conflicts": [{"typ": "...", "story": "...", "popis": "..."}]}`

Pokud `conflict`:
- Přidej sekci `## Konflikty` do wiki souboru s popisem konfliktů
- Přečti `conflict_check_iterations` z frontmatteru wiki souboru (default 0)
- Inkrementuj counter: `conflict_check_iterations += 1`
- Pokud `conflict_check_iterations >= 3`: nastav `blocked`, jinak `draft`
  ```bash
  # Pro draft (< 3 iterace) — vrátit uživateli k opravě:
  sed -i '' 's/^conflict_check_iterations: .*/conflict_check_iterations: N/; s/^- Status: .*/- Status: draft/; s/^status: .*/status: draft/' wiki/stories/US-{id}.md
  python3 task-forge/status_history.py append wiki/stories/US-{id}.md draft

  # Pro blocked (>= 3 iterace):
  sed -i '' 's/^- Status: .*/- Status: blocked/; s/^status: .*/status: blocked/' wiki/stories/US-{id}.md
  python3 task-forge/status_history.py append wiki/stories/US-{id}.md blocked
  python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
  ```
- Pošli zprávu uživateli přes IPC s popisem konfliktu a navrhovaným řešením
- Přejdi na krok 5 (zapiš metriky a zastav)

Pokud `ok`:
```bash
sed -i '' 's/^- Status: .*/- Status: ready-for-arch/; s/^status: .*/status: ready-for-arch/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py wiki/stories/US-{id}.md ready-for-arch
```

### 4. Architekt (Fáze 1 — technické anotace)

Architekta přeskoč **pouze** pokud story explicitně obsahuje `arch_skip: true` v hlavičce. Ve všech ostatních případech vždy spusť — i FE-only story potřebuje implementační plán.

Spusť agenta `architekt` (instrukce v `.memory-system/team/architekt.md`) s:
- Výstupem PO (text story)
- `.memory-system/V1-static-context/project.md`
- `.memory-system/V1-static-context/constraints.md`
- Relevantními sekcemi `.memory-system/V2-shared-truth/domain.md`
- `.memory-system/V2-shared-truth/story_register.md`

Po dokončení přečti `total_tokens` z bloku `<usage>` a ulož:
- `tokens_arch = total_tokens`
- `cost_arch = tokens_arch / 1_000_000 × 7.8` (Sonnet 4.6: ~$7.8/MTok blended)

Architekt přidá do story (výstup ve formátu JSON):
- AC a test cases (pokud `generate_acceptance_criteria: true`)
- Technické anotace a dopad na domain model
- Implementační plán (pokud `architect_creates_implementation_plan: true`)

Ulož výstup Architekta do wiki souboru pomocí Edit nástroje.

Aktualizuj domain model a story register dle instrukcí v `.memory-system/CLAUDE.md`.

### 5. Finalizace a metriky

Vypočti agregované hodnoty:
- `cost_analyze_total = cost_po + cost_cd + cost_arch`
- `analyze_duration` = čas od `analyze_start` do teď (zaokrouhli na sekundy)

Formatuj čas: pokud < 60s → `{n}s`, pokud < 3600s → `{m}m {s}s`, jinak `{h}h {m}m`.

Připrav řádek metriky analýzy:
```
- Analýza: $X.XXXX · PO $X.XXXX · CD $X.XXXX · Arch $X.XXXX · čas {duration}
```
Pokud Architekt byl přeskočen, vynech `· Arch $X.XXXX`. Pokud `<usage>` nebyl dostupný, použij `$0.0000`.

Zapiš/přepiš sekci `## Metriky` v wiki souboru (Edit nástroj). Pokud sekce existuje, zachovej řádky `- Implementace:` a `- Celkem:` pokud jsou. Přepiš pouze řádek `- Analýza:` a přepočítej `- Celkem:`.

Výsledná sekce:
```markdown
## Metriky
- Analýza: $X.XXXX · PO $X.XXXX · CD $X.XXXX · Arch $X.XXXX · čas {duration}
- Celkem: $X.XXXX
```

Aktualizuj status na `validated` (nebo ponech `blocked` pokud Conflict Detector selhal):
```bash
sed -i '' 's/^- Status: .*/- Status: validated/; s/^status: .*/status: validated/' wiki/stories/US-{id}.md
python3 task-forge/status_history.py wiki/stories/US-{id}.md validated
python3 task-forge/status_history.py metrics wiki/stories/US-{id}.md
```

Aktualizuj GitHub issue:
```bash
gh issue edit {číslo} --repo {Main_repo z .claude/config.md} --body "$(cat wiki/stories/US-{id}.md)"
```

## Pravidla
- Nikdy necommituj změny do gitu — wiki soubory jsou working state sledovaný backendem
- Pokud agent selže non-fatálně (např. conflict-detector), pokračuj na další fázi
- Agenti nečtou V2 přímo v implementační fázi — výtah připravuje Architekt
- Pokud `<usage>` blok chybí, použij `$0.0000` — nezastavuj pipeline kvůli chybějícím metrikám
