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

Timeline se vykresluje komponentou `renderTimeline()` v `shared.js`. Zobrazuje 7 kroků životního cyklu story.

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

### GET `/api/eur-rate`
Načte aktuální kurz EUR/CZK z ČNB XML feedu.
- **Odpověď**: `{ rate: float }` nebo `{ error: "unavailable" }`
- **Zdroj**: `https://www.cnb.cz/cs/financni_trhy/devizovy_trh/kurzy_devizoveho_trhu/denni_kurz.xml`

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
