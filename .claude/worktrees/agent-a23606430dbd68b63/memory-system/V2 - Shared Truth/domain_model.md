# Domain Model — Task-Forge

<!-- SECTION: story-lifecycle -->
## Story Lifecycle

Story prochází těmito stavy:

| Stav | Popis |
|---|---|
| `draft` | Vyplněný formulář uložen jako GitHub issue (tlačítko Uložit draft). Status zapsán přímo do body issue. |
| `conflict-check` | Po odeslání formuláře agentu — Conflict Detector prochází závislosti a story register. |
| `ready-for-arch` | Conflict Detector nedetekoval konflikty; story čeká na technické anotace od Architekta. |
| `validated` | Architekt doplnil technické popisky, AC a test cases. Story je připravena k implementaci. |
| `in_development` | Spuštěna fáze 2 (`/implement`); Backend a/nebo Frontend Developer pracuje na implementaci. |
| `ready_for_testing` / `ready-for-pr` | Implementace dokončena, čeká na QA nebo Code Review. |
| `done` | PR zamergován do main. |

### Přechody a kdo je mění

```
Business Owner (člověk)
  → uloží formulář → status: draft (zapsáno do GitHub issue body)
  → odešle agentu  → session: waiting_for_validation

Product Owner (agent)
  → zpracuje zadání → session.validation_phase: product_owner
  → může klást otázky → session.status: asking_questions
  → po dokončení → session.status: reviewing

Conflict Detector (agent)
  → session.validation_phase: conflict_detector
  → OK  → story status: ready-for-arch (zapsáno do wiki souboru)
  → NOK → přidá review_comment s výpisem konfliktů

Architekt (agent)
  → session.validation_phase: architect
  → doplní technické anotace → story status: validated (zapsáno do wiki)
  → zapisuje do domain_model.md

story_builder.py
  → po dokončení všech agentů nastaví session.status: done
  → vytvoří/aktualizuje GitHub issue a wiki soubor
```

### Kde je status uložen

- **Session** (`store_state.py`): přechodný stav agentového pipeline. Smaže se restartem procesu.
- **GitHub issue body**: trvalý stav; pole `- Status: <hodnota>` v markdown body.
- **Wiki soubor** (`wiki/stories/US-NNN.md`): lokální kopie story; synchronizována s issue body.

<!-- /SECTION: story-lifecycle -->

<!-- SECTION: timeline-widget -->
## Timeline Widget

Timeline se vykresluje komponentou `renderTimeline()` v `shared.js`. Zobrazuje 7 kroků životního cyklu story. **Timeline je nyní jediný status indicator v aplikaci** — staré prvky `#status-bar` a `#done-section` byly odstraněny (story US-037).

### Kroky timeline

| Index | Klíč (`key`) | Label |
|---|---|---|
| 0 | `draft` | Draft |
| 1 | `conflict-check` | Konflikt |
| 2 | `ready-for-arch` | Arch review |
| 3 | `arch-approved` | Dev plán |
| 4 | `in-development` | Vývoj |
| 5 | `ready-for-pr` | PR |
| 6 | `done` | Done |

### Mapování story statusu na krok (`_STATUS_TO_STEP`)

| Story status | Poslední úspěšný krok (`lastSuccess`) |
|---|---|
| `draft` | `draft` |
| `conflict-check` | `draft` |
| `ready-for-arch` | `conflict-check` |
| `validated` | `arch-approved` |
| `in_development` / `in-development` | `in-development` |
| `ready-for-pr` | `ready-for-pr` |
| `done` | `done` |

### Barevné stavy — CSS třídy

| CSS třída | Barva | Podmínka |
|---|---|---|
| `.passed` | zelená (`#43a047`) | `idx <= lastIdx` — krok byl již úspěšně dokončen; nebo `idx === activeIdx` (aktuální fáze se vykresluje jako passed) |
| `.pending` | modrá (`#1976d2`, glow efekt) | `idx === activeIdx + 1` — krok hned za aktuální fází; nebo pokud `activeIdx === -1` pak `idx === lastIdx + 1` |
| `.blocked` | červená (`#e53935`) | `idx === errorIdx` — krok explicitně označen jako chybový (konflikt, selhání) |
| (žádná) | šedá (`#e0e0e0` / `#bbb`) | všechny ostatní kroky — ještě nenastaly |

### Volání z kódu

`renderTimeline(container, storyStatus, opts?)` kde `opts` může obsahovat:
- `activeStep` — klíč kroku aktuálně probíhající fáze
- `errorStep` — klíč kroku, který má být označen červeně

Mapování `validation_phase` na timeline (funkce `_updateTimelineForPhase` v `app.js`):

| `validation_phase` | `storyStatus` | `activeStep` | `errorStep` |
|---|---|---|---|
| `product_owner` | `draft` | `draft` | `null` |
| `conflict_detector` | `conflict-check` | `conflict-check` | `conflict-check` (jen pokud jsou konflikty) |
| `architect` | `ready-for-arch` | `ready-for-arch` | `null` |
| `done` | `validated` | `null` | `null` |

### Kdy se timeline aktualizuje (polling)

| `session.status` | Podmínka | Volání |
|---|---|---|
| `asking_questions` | `data.validation_phase` je přítomno | `_updateTimelineForPhase(data.validation_phase, _phaseHasConflict(data))` |
| `done` | vždy | `_updateTimelineForPhase('done', false)` |
| `building` | vždy | `_updateTimelineForPhase('done', false)` |
| `error` | — | timeline se neresetuje |

### CSS transitions

`.impl-step`, `.impl-step::before`, `.impl-step::after` mají `transition: .3s ease` na `color`, `background`, `box-shadow`.

### Zobrazování timeline v rámci aplikace

Timeline se zobrazuje v těchto use casech:
- **Story formulář** (index.html) - po uložení draftu (`saveForm`) se zobrazí timeline s statusem 'draft'
- **Vytvoření myšlenky** - po uložení myšlenky se zobrazí timeline s statusem 'draft'
- **Nahlášení bugu** (bug.html) - po vytvoření bug issue se zobrazí timeline s statusem 'draft'
- **Agentová validace** (submitForm) - timeline se dynamicky aktualizuje dle `validation_phase` agentů (product_owner, conflict_detector, architect)

### HTML umístění

Timeline widget je jedinou viditelnou součástí statusu story. HTML struktura:

```html
<div id="story-timeline-wrap" hidden>
  <div class="story-timeline-card" id="story-timeline-container"></div>
</div>
```

**Odstraněné prvky (story US-037):**
- `#status-bar` — starší status indicator (duplikace s timeline)
- `#done-section` — banner "Story byla vytvořena" (nahrazena timeline aktualizací)

<!-- /SECTION: timeline-widget -->

<!-- SECTION: session-lifecycle -->
## Session Lifecycle

Session je in-memory struktura (`store_state.py`, slovník chráněný `threading.Lock`). Vytváří se při každém odeslání formuláře (`/api/submit`). Nepřežije restart Flask serveru.

### Stavy session (`status`)

| Stav | Kdy nastane |
|---|---|
| `waiting_for_validation` | Ihned po vytvoření session (`create_session`). |
| `reviewing` | Agent aktivně zpracovává — přechází sem po dokončení otázek nebo mezi fázemi agentů. |
| `asking_questions` | Agent potřebuje odpovědi od uživatele; session čeká na `POST /api/answer`. |
| `processing` | Přechodný stav při zpracování review komentáře (`/api/review-comment`). |
| `building` | Agenti dokončili analýzu; session.py sestavuje story a volá GitHub. |
| `preview` | (Historický stav — připraven náhled ke schválení uživatelem; v aktuálním kódu aktivní přes `/api/confirm`.) |
| `done` | Story úspěšně vytvořena/aktualizována na GitHubu. |
| `error` | Libovolná fatální chyba (timeout, budget exceeded, GitHub API selhání). |

### SessionStorage klíče (frontend)

| Klíč | Hodnota | Kdy se zapisuje | Kdy se maže |
|---|---|---|---|
| `active_session_id` | `_sessionId` (string) | `submitForm()` po `startPolling()` | `_resetForm()`, `handleSessionData` při `status === 'error'` |

Při `DOMContentLoaded`: pokud `active_session_id` existuje, obnoví `_sessionId` a zavolá `startPolling()` — přežívá page reload, ne zavření tabu.

### Pole `validation_phase`

Upřesňuje, který agent aktuálně běží (relevantní jen pokud `status == "reviewing"`):

| Hodnota | Agentová fáze |
|---|---|
| `product_owner` | Product Owner posuzuje zadání. |
| `conflict_detector` | Conflict Detector kontroluje závislosti a story register. |
| `architect` | Architekt doplňuje technické anotace, AC, test cases. |
| `done` | Všichni agenti dokončili práci; session přechází do `building`. |
| `null` | Session ještě nezačala agentový pipeline nebo je mimo fázi validace. |

### Struktura session objektu

```json
{
  "status": "reviewing",
  "form_data": { "name": "...", "epic": "...", ... },
  "questions": [{ "id": "uuid", "text": "...", "answer": null, "agent": "Product Owner" }],
  "preview": null,
  "result": { "issue_url": "...", "wiki_path": "..." },
  "error": null,
  "review_comments": [{ "id": "uuid", "text": "...", "reply": null }],
  "review_summary": "Product Owner posuzuje zadání…",
  "total_cost_usd": 0.0,
  "total_tokens": 0,
  "validation_phase": "product_owner",
  "validation_agent": "Product Owner"
}
```

<!-- /SECTION: session-lifecycle -->

<!-- SECTION: validation-pipeline -->
## Validation Pipeline

Funkce `run_team_validation()` v `story_builder.py` orchestruje 3 agenty sekvenčně. Každý agent volá `claude` CLI jako subprocess s `--output-format json`.

### Agent 1: Product Owner

- **Soubor instrukci**: `agents/team/product-owner.md`
- **Co dělá**: Posuzuje business zadání — zda je story dostatečně popsána. Pokud chybí klíčové informace, může položit max. 4 otázky (omezeno polem `max_questions` v instrukčním souboru). Generuje: `why` (business goal), `what` (co se zobrazuje), `how` (jak se chová), `reads_sections`, `writes_sections`.
- **Výstup JSON (action: ask)**: `{ "action": "ask", "questions": [...], "summary": "..." }`
- **Výstup JSON (action: complete)**: `{ "action": "complete", "summary": "...", "why": "...", "what": "...", "how": "...", "reads_sections": [...], "writes_sections": [...] }`
- **Interakce s uživatelem**: Pokud vrátí `ask`, session přejde do stavu `asking_questions`. Uživatel odpovídá přes `POST /api/answer`. Po odpovědích se PO zavolá znovu s kontextem Q&A.
- **Předává dál**: `po_data` — slovník s `story_text`, `why`, `what`, `how`, `summary`, `reads_sections`, `writes_sections`, `qa_pairs`.

### Agent 2: Conflict Detector

- **Soubor instrukci**: `agents/team/conflict-detector.md`
- **Co dělá**: Čte `domain_model.md` a `story_register.md`. Hledá konflikty a závislosti — nekonzistentní entity, kolize se stávajícími stories, porušení omezení.
- **Vstup**: `story_context` (text story od PO), `domain_model`, `story_register`.
- **Výstup JSON (ok)**: `{ "action": "ok", "affected_stories": [] }`
- **Výstup JSON (conflict)**: `{ "action": "conflict", "conflicts": [{ "typ": "...", "story": "...", "popis": "..." }] }`
- **Vliv na session**: Pokud `action == "conflict"`, přidá se `review_comment` s výpisem konfliktů a nastaví se `errorStep` na krok `conflict-check` v timeline. Conflict Detector **není fatální** — pipeline pokračuje dál k Architektovi.
- **Předává dál**: `conflict_result` slovník (předán Architektovi jako kontext).

### Agent 3: Architekt (Fáze 1)

- **Soubor instrukci**: `agents/team/architekt.md`
- **Co dělá**: Čte V1 context, V1 constraints, domain_model.md. Doplňuje technické anotace, generuje Acceptance Criteria (funkční + nefunkční) a Test Cases. Extrahuje doménové znalosti a zapisuje je do `domain_model.md` (pole `domain_model_updates`).
- **Vstup**: `po_data`, `conflict_result`, V1 context, V1 constraints, domain_model.
- **Výstup JSON**: `{ "action": "complete", "technical_notes": "...", "acceptance_criteria": { "functional": [...], "non_functional": [...] }, "test_cases": [...], "domain_model_updates": [{ "section": "...", "content": "..." }] }`
- **Předává dál**: `arch_data` — slovník s `technical_notes`, `acceptance_criteria`, `test_cases`, `domain_model_updates`.
- **Vedlejší efekt**: Funkce `_apply_domain_model_updates()` zapíše/aktualizuje sekce v `domain_model.md` pomocí tagů `<!-- SECTION: ... -->`.

### Předávání výsledků

```
Product Owner → conflict_result jako kontext
              → po_data pro sestavení story body

Conflict Detector → conflict_result (conflicts / ok) předán Architektovi

Architekt → arch_data použit v _build_story_body()
          → domain_model_updates zapsány do domain_model.md
          → story_register aktualizován přes _update_story_register()
```

### Akumulace ceny

Každé volání `_call_claude()` vrací `cost_usd`. `store_state.increment_cost()` průběžně sčítá náklady. Po dokončení se náklady zapisují do story body jako `- Validace cena: $X.XXXX`.

<!-- /SECTION: validation-pipeline -->

<!-- SECTION: api-endpoints -->
## API Endpoints

Flask server běží na portu `5001` (`task-forge/task-forge.py`).

### GET `/`
Vrací `static/index.html` — hlavní stránka s formulářem pro vytvoření user story.

### GET `/bug/new`
Vrací `static/bug.html` — formulář pro nahlášení bugu.

### POST `/api/submit`
Spustí agentový pipeline pro novou story.
- **Body (JSON)**: `{ name, epic, role, what, how, scope?, deps?, ac?, flags?, issue_number?, wiki_path? }`
- **Povinná pole**: `name`, `epic`, `role`, `what`, `how`
- **Odpověď**: `{ session_id }` (HTTP 202)
- **Efekt**: Vytvoří session, spustí `run_team_validation()` v novém vlákně.

### GET `/api/session?session_id=<id>`
Polling endpoint — vrací aktuální stav session.
- **Odpověď**: Celý session objekt včetně `status`, `validation_phase`, `review_summary`, `review_comments`, `questions`, `result`, `error`, `total_cost_usd`.

### POST `/api/answer`
Odeslání odpovědi na otázku agenta.
- **Body (JSON)**: `{ session_id, question_id, answer }`
- **Podmínka**: Session musí být ve stavu `asking_questions`.
- **Efekt**: Zapíše odpověď do session. Pokud jsou zodpovězeny všechny otázky, session přejde do `building`.

### POST `/api/review-confirm`
Potvrzení vytvoření story po dokončení review.
- **Body (JSON)**: `{ session_id }`
- **Podmínka**: Session musí být ve stavu `reviewing`.
- **Efekt**: Přechod do `building`, spustí `run_session()` v novém vlákně.

### POST `/api/review-comment`
Odeslání komentáře/dotazu k review.
- **Body (JSON)**: `{ session_id, comment }`
- **Podmínka**: Session musí být ve stavu `reviewing`.
- **Efekt**: Přechod do `processing`, přidá comment, spustí `run_review_comment()`.

### POST `/api/confirm`
Potvrzení náhledu story (legacy preview flow).
- **Body (JSON)**: `{ session_id }`
- **Podmínka**: Session musí být ve stavu `preview`.
- **Efekt**: Session přejde do `building`.

### GET `/api/done?session_id=<id>`
Dotaz na výsledek — vrací `status`, `result` nebo `error`.

### POST `/api/save`
Uloží draft story nebo myšlenku jako GitHub issue (bez agentového pipeline).
- **Body (multipart/form-data)**: pole `data` (JSON), volitelně `files` (max 3 soubory)
- **JSON data**: `{ name, epic, role, why?, what?, how?, scope?, deps?, ac?, type }` — `type` je `"story"`, `"idea"` nebo `"bug"`
- **Povinné pole**: `name`
- **Odpověď**: `{ issue_url, issue_number, wiki_path }`
- **Efekt**: Vytvoří GitHub issue s labelem dle `type`, zapíše wiki soubor se statusem `draft`.

### POST `/api/update`
Aktualizuje existující draft issue.
- **Body (multipart/form-data)**: pole `data` (JSON s `issue_number`, `wiki_path`), volitelně `files`
- **Validace**: `wiki_path` musí začínat `wiki/stories/` a nesmí obsahovat `..`
- **Odpověď**: `{ issue_url, wiki_path }`

### GET `/api/issues`
Načte otevřené GitHub issues pro modal výběru.
- **Odpověď**: Pole objektů `{ id, title, type, epic, date, body, story_status, wiki_path }`
- **`type`**: `idea` / `story` / `bug` / `other` (dle GitHub labels)
- **Limit**: 100 issues

### POST `/api/attach`
Připojí soubory (přílohy) k existující story.
- **Body (multipart/form-data)**: pole `data` (JSON s `issue_number`, `wiki_path`), `files`
- **Validace**: `wiki_path` musí být v `wiki/stories/`, kontrola path traversal

### POST `/api/submit-bug`
Vytvoří bug issue na GitHubu.
- **Body (JSON)**: `{ name, epic, role, what_happened, expected, steps?, details? }`
- **Povinná pole**: `name`, `epic`, `role`, `what_happened`, `expected`
- **Odpověď**: `{ issue_url, issue_number }`

<!-- /SECTION: api-endpoints -->

<!-- SECTION: github-integration -->
## GitHub Integration

Modul `github_helper.py`. GitHub repozitář: `raadvit/PreciousMetals_backend` (načítáno z `.claude/config.md`, fallback hardcoded).

### Vytvoření issue

Funkce `create_story(title, body, epic, repo_root, files?, labels?)`:
1. Spustí `gh issue create --repo <repo> --title <title> --body <body> [--label <label>...]`
2. Parsuje URL z výstupu, extrahuje číslo issue.
3. Vytvoří wiki soubor na cestě `wiki/stories/US-NNN.md`, kde `NNN` = číslo issue (zero-padded na 3 cifry).
4. Aktualizuje `- GitHub:` pole v body na `#<číslo>`.
5. Pokud jsou přiloženy soubory: uloží je do `wiki/stories/assets/<story_id>/` a aktualizuje body i issue přes `gh issue edit`.

### Aktualizace issue

Funkce `update_story(issue_number, title, body, wiki_path, repo_root, files?)`:
1. Opraví `- GitHub:` pole v body.
2. Zachová existující přílohy (sekce `## Přílohy` z wiki souboru).
3. Spustí `gh issue edit <číslo> --repo <repo> --title <title> --body <body>`.

### Wiki soubory

- **Cesta**: `wiki/stories/US-NNN.md` (NNN = číslo GitHub issue, zero-padded)
- **Source of truth**: číslo GitHub issue = číslo wiki souboru
- **Formát**: Markdown s metadatovým blokem na začátku:
  ```markdown
  # <Název story>

  ## Metadata
  - Epic: <hodnota>
  - Role: <hodnota>
  - Status: <hodnota>
  - GitHub: #<číslo>
  - Vytvořeno: <ISO datum>
  - Změněno: <ISO datum>
  - Validace cena: $X.XXXX
    - Product Owner: $X.XXXX
    - Conflict Detector: $X.XXXX
    - Architekt: $X.XXXX
  ```

### Assets (přílohy)

- **Cesta**: `wiki/stories/assets/<story_id>/<filename>`
- **Story ID**: `US-NNN` (stejné jako wiki soubor)
- **Odkaz v wiki**: `- [<filename>](assets/<story_id>/<filename>)`
- **Sekce v wiki**: `## Přílohy` (na konci souboru)
- **Sanitizace jmen**: znaky mimo `\w.\-() ` nahrazeny podtržítkem; soubory začínající `.` ignorovány
- **Limit**: max 3 soubory najednou (vynuceno na frontendu)

<!-- /SECTION: github-integration -->

<!-- SECTION: story-form-fields -->
## Story Form Fields

Formulář v `static/index.html`, logika v `static/app.js`.

### Pole formuláře

| ID pole | Klíč v payloadu | Typ UI | Povinné | Popis |
|---|---|---|---|---|
| `f-name` | `name` | text input | ano | Název story |
| `f-epic` | `epic` | select (dropdown) | ano | Epic, ke kterému story patří |
| `#roles .chip` | `role` | chip group (multi-select) | ano | Role uživatele (lze vybrat více) |
| `f-why` | `why` | textarea | ne | Proč — business motivace (odesílá se jen při save/update, ne do agentů přímo) |
| `f-what` | `what` | textarea | ano | Co se zobrazuje — popis UI prvků |
| `f-how` | `how` | textarea | ano | Jak se to chová — interakce, pravidla |
| `f-scope` | `scope` | textarea | ne | Rizikové situace / scope |
| `f-deps` | `deps` | textarea | ne | Otevřené otázky / závislosti |
| `f-ac` | `ac` | textarea | ne | Vlastní Acceptance Criteria |
| `f-file` | `files` | file input (multipart) | ne | Přílohy (max 3 soubory) |

### Flags (checkboxy)

Pole `flags` — pole stringů, odesílá se při `submitForm()` (ne při save/update draftu).

| Checkbox ID | Hodnota v `flags` |
|---|---|
| `f-flag-ext-api` | `ext-api` |
| `f-flag-db` | `db` |
| `f-flag-notif` | `notif` |
| `f-flag-security` | `security` |

### Povinná pole (`required`)

`['name', 'epic', 'role', 'what', 'how']`

Validace probíhá ve funkci `validate()` — neúspěšná pole dostanou CSS třídu `error` na `.card` elementu a indikátor `!` v `.si` elementu.

### Vizuální stavy karet

| Stav | CSS třída na `.card` | `.si` indikátor | Barva |
|---|---|---|---|
| Vyplněno | `.filled` | `✓` (třída `done`) | zelená (`#4caf50`) |
| Chyba | `.error` | `!` (třída `err`) | červená (`#e53935`) |
| Prázdné | (žádná) | prázdné | výchozí |

### LocalStorage draft

Funkce `loadDraft()` automaticky obnoví formulář z `localStorage['us-draft']` při načtení stránky. Klíč se smaže po úspěšném odeslání (`localStorage.removeItem('us-draft')`).

<!-- /SECTION: story-form-fields -->

<!-- SECTION: project-qa -->
## Ustanovené odpovědi (Q&A z validací)

- Q: Jaký je business důvod pro přidání filtru 'ready for testing'? Jaké problémy to řeší a kdo bude tuto funkcionalitu primárně používat?
  A: chci si vyjet seznam k testování
- Q: Má se label 'ready for testing' přidat automaticky po skončení /implement, nebo je to manuelní akce?
  A: tohle už funguje, zde řešíme jen zobrazení
- Q: V popup 'načíst myšlenku' jsou už nějaké filtry? Jak budou filtrovat kombinovat (AND/OR logika) — např. filtrovat jen 'ready for testing' nebo i s dalšími labely?
  A: pouze jeden filtr může být vybraný
- Q: Jakou má toto priority? Je deadline pro implementaci?
  A: deadlines neřeš
- Q: Jaká je business motivace za odstraněním widgetu EUR? (Přestali jsme obchodovat EUR? Migrujeme na nový kurz API? Cleanup po ukončení funkce?)
  A: už to nechci
- Q: Jaký je rozsah odstraňování — jenom UI/widget, nebo také backend API, databází a logiku pro EUR kurzy?
  A: vše
- Q: Co se stane s historickými daty o EUR kurzech? (Archivovat, smazat, nebo ponechat pro reporting/audit?)
  A: smazat
- Q: Je toto součástí větší business iniciativy nebo má nějaký business deadline?
  A: stand alone
- Q: Jaká je business motivace k přesunutí stavového řádku nad timeline? Jde o lepší viditelnost stavu uživatele, konzistentnější layout, nebo něco jiného?
  A: ano
- Q: Stavový řádek — je to nějaký custom widget, který já máme někde v kódu, nebo jde o textový status, který existuje jinde? Máš příklad nebo reference (obrázek)?
  A: oboje už existuje jak timeline tak status řádek, nyní v něm vidím Agent čeká na vaše odpovědi.
- Q: Scope: Jsou use casy 'uložit na později', 'vytvořit myšlenku', 'nahlásit bug' součástí tohoto taskeru, nebo jsou to separátní flow, které se jen mají také aktualizovat?
  A: ano je potřeba to vyřeit i pro ně a timeline začít ukazovat i u těch dalších use casů
- Q: Kritérium hotovo: Kdy je feature považován za úspěšný? Jaké jsou měřitelné znaky (všechny use casy mají timeline, stavový řádek je vždy vidět, specifický design, atd.)?
  A: vždy je videt timeline a když se zobrazí stavový řádek je v ní
- Q: Kde mám najít ten design mockup? (soubor v repozitáři, link, příloha emailu?) — zmíňuješ 'v příloze', ale nevidím ji
  A: attachment se uloží až ty uložíš storku
- Q: Co konkrétně je na aktuálním designu timeline rozbitého? Jaké jsou viditelné problémy nebo chyby, které řeší nový design?
  A: layoutove to nezapadá
- Q: Co má ten banner pod widgetem s názvem požadavku obsahovat? (jaké informace, pole, jak vypadá?)
  A: data vem ze současného panelu s timeline a stavového řádku
- Q: Máš info: admini vidí všechny story v systému, nebo pouze filtrované podmnožiny? Je timeline/banner stejný pro všechny story nebo se mění podle typu/statusu?
  A: ano stejný, jen se mění data
- Q: Jaký je business důvod pro změnu barvy na zelenou (#43a047)? Co se tím zlepší z pohledu uživatele nebo workflow?
  A: chci to
- Q: Kolik tlačítek se má změnit — jen konkrétní tlačítko v určité sekci/stránce, nebo všechna tlačítka 'Odeslat k validaci' v aplikaci?
  A: jen to jedno
- Q: Je tato změna součástí větší vizuální iniciativy či redesignu, nebo jde o izolovanou UI změnu?
  A: ne
- Q: Jakou informaci má uživatel "čekat" a v jakých story stavech se má zobrazit text o čekání? (např. waiting_for_validation, asking_questions, draft…)
  A: dej mi svůj návrh pak zadám změny
- Q: Jakou URL se má zobrazit "po vygenerování story"? GitHub issue URL, wiki soubor, nebo něco jiného?
  A: github url, už tam nyní byla jen v jiném panelu
- Q: Když se texty ze status-bar přesouvají do story-status-text — má status-bar sekce zmizet ze stránky úplně, nebo zůstat v HTML bez obsahu?
  A: zmizet
- Q: Jaký je **business problém** s aktuálním workflow? Dnes se story ztrácejí po odeslání, nemůžou se editovat, nebo je problém nějaký jiný?
  A: když to spadne při validaci přijdu o zadání
- Q: Zadání říká 'Co se zobrazuje: viz níže' — ale konkrétní popis chybí. Má UI zůstat stejně a jde jen o změnu logiky, nebo se mají změnit nějaké prvky UI (dialog, notifikace, progress indikátor)?
  A: jen změna logiky
- Q: Role 'admin' — znamená to, že **pouze admin** může story odeslat k validaci, nebo je 'admin' role autora, který ji vytváří?
  A: ano
- Q: Po skončení validace — má být story automaticky přesunuta do dalšího kroku workflowu (ready-for-arch), či má jen přijít notifikace? Má se zmenšit UI nebo čekání?
  A: proces neměníme jen měníme to že před validací to uloží storku
- Q: Proč se odstraňují `done-section` a `status-bar`? Jsou redundantní s timeline widgetem, nebo jde o přípraavu na nový UI design?
  A: ano s timeline
- Q: Má se smazat kód jen vizuálně (CSS display:none), nebo kompletně z HTML/JS? Nebo ty widgety zůstávají v kódu, jen se nerendrují pro adminy?
  A: úplně
- Q: Měla by se změna aplikovat na všechny role nebo jen na admina?
  A: vše
<!-- /SECTION: project-qa -->

<!-- SECTION: github-labels-workflow -->
## GitHub Labels & Automatizace

### Label: ready-for-testing
- **Přidává se**: automaticky po skončení `/implement`
- **Podmínka**: issue má label 'user story'
- **Konvence**: `ready-for-testing` (malá písmena, pomlčky - GitHub standard)
- **Status v kódu**: `ready_for_testing` (Python konvence - podtržítka)
- **Použití**: filtrování issues v popup 'Načíst myšlenku' pro admin

**Poznámka k pojmenování**: Existuje nejednotnost v domain_model - `ready_of_testing` (podtržítka) se zároveň používá s `ready-for-pr` (pomlčka). Doporučujeme sjednotit:
- GitHub labels: vždy pomlčky (`ready-for-testing`)
- Python/backend: vždy podtržítka (`ready_of_testing`)
- Markdown body: vždy podtržítka (stejně jako Python)

<!-- /SECTION: github-labels-workflow -->

<!-- SECTION: ui-load-idea-filter -->
## Popup 'Načíst myšlenku' - Filtr na Labely

### Komponenty
- **Umístění**: hlavička popup
- **Typ**: single-select dropdown
- **Volba**: 'ready for testing'
- **Chování**: filtruje seznam issues podle GitHub labelu `ready-for-testing`
- **Default stav**: bez filtru (zobrazuje všechny relevantní issues)
- **Persistence**: filtr zůstává vybraný i po zavření/otevření popup

### Funkčnost
- Seznam se aktualizuje bez zpoždění (< 500ms)
- Accessibility: klávesnicí přístupný (Tab, Shift+Tab, Enter)
- Filtr se aplikuje client-side (po načtení dat) nebo server-side (dle architektury)

<!-- /SECTION: ui-load-idea-filter -->

<!-- SECTION: task-forge-ui-components -->
## Task-Forge UI Components (Administrativa)

Task-Forge je administrativní aplikace pro tvorbu a validaci user stories. Skládá se z těchto UI komponent:

### Timeline Widget
Vizuální reprezentace životního cyklu story (draft → conflict-check → ready-for-arch → arch-approved → in-development → ready-for-pr → done). Renderuje se funkcí `renderTimeline()` v `shared.js`.

### Story Form
Hlavní formulář s poli: name, epic, role, why, what, how, scope, deps, ac, files. Povinná pole: name, epic, role, what, how.

### Submit Button ("Odeslat týmu k validaci")
**Umístění**: Část `.btn-row-main` (po uložení draftu nebo při novém zadání)
**CSS třída**: `.btn-send`
**Barva**: `#43a047` (zelená, shodná s timeline `.passed` stavem)
**Funkce**: Odesílá formulář k agentové validaci (spouští Product Owner review)
**Barva zdůvodnění**: Zelená signalizuje, že akce inicializuje product owner phase a odpovídá design jazyku timeline widget — stejná barva pro aktivní/schváleno stavy

### Status Notes
Pole `- Status: <value>` v GitHub issue body, synchronizované s wiki souborem. Story prochází stavy: draft, conflict-check, ready-for-arch, validated, in_development, ready_for_testing, ready-for-pr, done.

### REMOVED: EUR Rate Widget
Byla součástí formuláře (div `.eur-box`), zobrazovala aktuální kurz EUR/CZK z ČNB API. Funkce `loadEurRate()` fetchovala `/api/eur-rate` endpoint. **Odstraněna: již se nepoužívá.**

<!-- /SECTION: task-forge-ui-components -->

<!-- SECTION: timeline-widget -->
## Timeline Widget

Timeline se vykresluje komponentou `renderTimeline()` v `shared.js`. Zobrazuje 7 kroků životního cyklu story. **Timeline je nyní jediný status indicator v aplikaci** — staré prvky `#status-bar` a `#done-section` byly odstraněny (story US-037).

### Kroky timeline

| Index | Klíč (`key`) | Label |
|---|---|---|
| 0 | `draft` | Draft |
| 1 | `conflict-check` | Konflikt |
| 2 | `ready-for-arch` | Arch review |
| 3 | `arch-approved` | Dev plán |
| 4 | `in-development` | Vývoj |
| 5 | `ready-for-pr` | PR |
| 6 | `done` | Done |

### Mapování story statusu na krok (`_STATUS_TO_STEP`)

| Story status | Poslední úspěšný krok (`lastSuccess`) |
|---|---|
| `draft` | `draft` |
| `conflict-check` | `draft` |
| `ready-for-arch` | `conflict-check` |
| `validated` | `arch-approved` |
| `in_development` / `in-development` | `in-development` |
| `ready-for-pr` | `ready-for-pr` |
| `done` | `done` |

### Barevné stavy — CSS třídy

| CSS třída | Barva | Podmínka |
|---|---|---|
| `.passed` | zelená (`#43a047`) | `idx <= lastIdx` — krok byl již úspěšně dokončen; nebo `idx === activeIdx` (aktuální fáze se vykresluje jako passed) |
| `.pending` | modrá (`#1976d2`, glow efekt) | `idx === activeIdx + 1` — krok hned za aktuální fází; nebo pokud `activeIdx === -1` pak `idx === lastIdx + 1` |
| `.blocked` | červená (`#e53935`) | `idx === errorIdx` — krok explicitně označen jako chybový (konflikt, selhání) |
| (žádná) | šedá (`#e0e0e0` / `#bbb`) | všechny ostatní kroky — ještě nenastaly |

### Volání z kódu

`renderTimeline(container, storyStatus, opts?)` kde `opts` může obsahovat:
- `activeStep` — klíč kroku aktuálně probíhající fáze
- `errorStep` — klíč kroku, který má být označen červeně

Mapování `validation_phase` na timeline (funkce `_updateTimelineForPhase` v `app.js`):

| `validation_phase` | `storyStatus` | `activeStep` | `errorStep` |
|---|---|---|---|
| `product_owner` | `draft` | `draft` | `null` |
| `conflict_detector` | `conflict-check` | `conflict-check` | `conflict-check` (jen pokud jsou konflikty) |
| `architect` | `ready-for-arch` | `ready-for-arch` | `null` |
| `done` | `validated` | `null` | `null` |

### Kdy se timeline aktualizuje (polling)

| `session.status` | Podmínka | Volání |
|---|---|---|
| `asking_questions` | `data.validation_phase` je přítomno | `_updateTimelineForPhase(data.validation_phase, _phaseHasConflict(data))` |
| `done` | vždy | `_updateTimelineForPhase('done', false)` |
| `building` | vždy | `_updateTimelineForPhase('done', false)` |
| `error` | — | timeline se neresetuje |

### CSS transitions

`.impl-step`, `.impl-step::before`, `.impl-step::after` mají `transition: .3s ease` na `color`, `background`, `box-shadow`.

### Zobrazování timeline v rámci aplikace

Timeline se zobrazuje v těchto use casech:
- **Story formulář** (index.html) - po uložení draftu (`saveForm`) se zobrazí timeline s statusem 'draft'
- **Vytvoření myšlenky** - po uložení myšlenky se zobrazí timeline s statusem 'draft'
- **Nahlášení bugu** (bug.html) - po vytvoření bug issue se zobrazí timeline s statusem 'draft'
- **Agentová validace** (submitForm) - timeline se dynamicky aktualizuje dle `validation_phase` agentů (product_owner, conflict_detector, architect)

### HTML umístění

Timeline widget je jedinou viditelnou součástí statusu story. HTML struktura:

```html
<div id="story-timeline-wrap" hidden>
  <div class="story-timeline-card" id="story-timeline-container"></div>
</div>
```

**Odstraněné prvky (story US-037):**
- `#status-bar` — starší status indicator (duplikace s timeline)
- `#done-section` — banner "Story byla vytvořena" (nahrazena timeline aktualizací)

<!-- /SECTION: timeline-widget -->

<!-- SECTION: story-status-representation -->
## Story Status Representation — Visual & Textual

Pro UI reprezentaci story statusu se používají tři komplementární prvky:

1. **Timeline Widget** — Vizuální zobrazení cesty (7 kroků) od draft do done. Aktuální krok je zvýrazněn barvou. (viz sekce Timeline Widget)

2. **Stavový řádek** (Status Bar, z US-030) — Zobrazuje v jednom řádku:
   - Aktuální `storyStatus` (human-readable text, např. "Ready for Architecture Review")
   - Aktuální `validation_phase` (např. "Architect Review in Progress")
   - Umístěn nad timelinerem (fixed/sticky header)

3. **Status Banner** — Umístěn pod timelinerem. Detailnější popis stavu:
   - Status + Phase (textová forma)
   - Timestamp poslední změny
   - Doplňuje timeline vizuální informace; čitelné pro uživatele, kteří čtou text

### Mapování statusu → Label

| `storyStatus` | Human-readable label | Popis |
|---|---|---|
| `draft` | "Draft" | Story je uložena jako GitHub issue, čeká na odeslání agentům |
| `conflict-check` | "Conflict Check" | Conflict Detector prochází story, hledá konflikty |
| `ready-for-arch` | "Ready for Architecture Review" | Konflikty ok; Architekt začíná anotace |
| `validated` | "Architecture Approved" | Architekt doplnil AC a plán; ready pro developers |
| `in-development` | "In Development" | Developer pracuje na implementaci |
| `ready-for-pr` | "Ready for PR Review" | Implementace hotová, PR je otevřen |
| `done` | "Done" | PR je zamergován, story kompletní |

### Mapování validation_phase → Label

| `validation_phase` | Human-readable label |
|---|---|
| `product_owner` | "Product Owner Review" |
| `conflict_detector` | "Conflict Detection" |
| `architect` | "Architect Review" |
| (null/none) | "Awaiting Validation" |

<!-- /SECTION: story-status-representation -->

<!-- SECTION: story-save-validation-workflow -->
## Save-Then-Validate Workflow (Fáze 1 hack)

### Problém
Původní workflow ztratil data pokud validace spadla během runtime — formulář zůstal jen v session bez persistence.

### Řešení: Dvoustupňový zápis

Story se nyní ukládá **PŘED** validací:

#### Fáze 1: Save (synchronní, v rámci jednoho HTTP request)
Kdy: User klikne "Odeslat týmu k validaci"

1. **Frontend validace**: Zkontroluj povinná pole
2. **Backend zápis**: 
   - Vytvoř/aktualizuj GitHub issue se statusem `conflict-check` (v issue body: `- Status: conflict-check`)
   - Vytvoř/aktualizuj wiki soubor (wiki/stories/US-NNN.md) — draft verze bez technických anotací
3. **Response**: Vrátí `{success: true, session_id, issue_number, issue_url, wiki_path}` nebo `{success: false, error}`
4. **Pokud selže**: Validace se nespustí, user vidí chybu, formulář zůstane na stránce

#### Fáze 2: Validate (asynchronní, spuštěna až po potvrzení Phase 1)
Kdy: Ihned po Phase 1, ale v separátní session

1. **Product Owner**: Pokládá otázky (pokud jsou, inače přeskočí)
2. **Conflict Detector**: Ověří závislosti v story register + domain model
3. **Architekt (Fáze 1)**: Doplní technické anotace, AC, test cases
4. **Zápis výsledku**: Aktualizuje GitHub issue a wiki se statusem:
   - Pokud OK: `- Status: validated`
   - Pokud konflikt: `- Status: conflict-check` + review comment s konflikty

### Výhody
- **Persistence**: Story se nikdy neztratí — vždy v GitHub
- **Debuggability**: User vidí GitHub issue URL hned, může ji otevřít a sledovat změny
- **Failsafe**: Pokud agent spadne, state je konzistentní (poslední úspěšný zápis)
- **Editability**: User může přepsat formulář a znovu odeslat (create-or-update pattern v GitHub)

### Implementace

**Backend** (`story_builder.py`):
- Rozdělit `run_team_validation()` na:
  - `save_story_to_github(form_data)` — atomická operace (vytvoř issue + wiki nebo rollback)
  - `run_team_validation(form_data, store)` — vlastní validace (Product Owner, Conflict Detector, Architekt)
- Session se vytvoří až **po** úspěšném save
- `/api/submit` endpoint: save (sync) → return response → spustit validation (async) v background

**Frontend** (`app.js`):
- `submitForm()`: 
  - Zavolá `/api/submit` (nikoli `/api/save` + `/api/submit` zvlášť — backend to udělá atomicky)
  - Čeká na response: `{success: true, session_id, issue_number}`
  - Pokud OK: spustí polling (stejně jako dnes)
  - Pokud fail: zobrazí error, formulář zůstane enabled
- Timeline se zobrazí po úspěšném Phase 1 (draft status)

**GitHub API**:
- Create-or-update pattern: pokud `issue_number` je v payloadu, PATCH issue; jinak CREATE

### Story lifecycle s novým workflowem

```
User vyplní formulář
  → klikne "Odeslat"
    → [Phase 1: Save] GitHub issue se vytvoří se statusem "conflict-check"
    → [Phase 1: Save] Wiki soubor se vytvoří (draft)
    → User vidí GitHub URL + timeline "draft"
    → [Phase 2: Validate — async] Product Owner, Conflict Detector, Architekt
      → Issue se aktualizuje s technickými poznatky
      → Pokud OK: status "validated"
      → Pokud konflikt: status "conflict-check" + error flag
    → User vidí finální story v GitHub
```

### Stavový diagram (GitHub issue body)

```
| Timeline krok | Issue status | Kdy se zapíše |
|---|---|---|
| draft | conflict-check | hned po Phase 1 save |
| conflict-check | conflict-check | během Conflict Detector (pokud konflikty) |
| arch-approved | validated | po Architekt Phase 1 OK |
| done | validated | (stejné jako arch-approved v current impl) |
```

<!-- /SECTION: story-save-validation-workflow -->
