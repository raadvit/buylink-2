# Instrukce pro Claude Code

## Setup nového projektu
- pustit `uv pip install certifi`


### Předpoklady

- **`uv`** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **`gh`** — GitHub CLI (`brew install gh`)

### MCP — Figma

Soubor `.mcp.json` v kořeni repozitáře (již přítomen, zkopírovat beze změn):
```json
{
  "mcpServers": {
    "figma": {
      "command": "npx",
      "args": ["-y", "figma-mcp"],
      "env": { "FIGMA_API_KEY": "$FIGMA_API_KEY" }
    }
  }
}
```

Soubor `.claude/settings.local.json` — přidat:
```json
{
  "permissions": { "allow": ["mcp__figma__*"] },
  "enabledMcpjsonServers": ["figma"]
}
```

### MCP — Jira (Atlassian)

`.mcp.json` již přítomen. Do `.env` přidat:
```
JIRA_URL=https://jira.alza.cz
JIRA_USERNAME=<jmeno.prijmeni@alza.cz>
JIRA_PERSONAL_TOKEN=<token z jira → profil → Personal Access Tokens>
JIRA_SSL_VERIFY=false
```

Do `.claude/settings.local.json` přidat `"mcp__jira__*"` do `allow` a `"mcp-atlassian"` do `enabledMcpjsonServers`.

### Proměnné prostředí — `.env` (nezavazovat do gitu)

```
FIGMA_API_KEY=<token z figma.com/settings → Personal access tokens>

JIRA_URL=https://jira.alza.cz
JIRA_USERNAME=<email>
JIRA_PERSONAL_TOKEN=<token>
JIRA_SSL_VERIFY=false
JIRA_PROJECTS_FILTER=DSC

GITHUB_REPO=<owner/repo>
PROJECT_NAME=<název projektu>
MAX_WORKERS=1
PORT=5001

# Provider abstrakce (US-188): aktivní úložiště issues
TARGET_SYSTEM=github  # nebo `jira`

# JIRA status mapping — interní status → JIRA name
JIRA_STATUS_DRAFT=To Do
JIRA_STATUS_CONFLICT_CHECK=To Do
JIRA_STATUS_READY_FOR_ARCH=To Do
JIRA_STATUS_VALIDATED=Selected for Development
JIRA_STATUS_IN_DEVELOPMENT=In Progress
JIRA_STATUS_READY_FOR_REVIEW=In Review
JIRA_STATUS_READY_FOR_TESTING=Testing
JIRA_STATUS_DONE=Done
JIRA_STATUS_BLOCKED=Blocked
JIRA_STATUS_CANCELLED=Cancelled
```

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

- Repozitář: `raadvit/buylink-2`
- Hlavní větev: `main`
- Pracovní větev: `feature/next`
- Squash merge přes PR, nikdy přímý push do main

## Styl odpovědí

- Česky
- Stručně
- Bez zbytečného komentáře co jsi udělal

## API odpovědi (Flask/jsonify)

- Chyba: `{"error": "popis"}` + příslušný HTTP kód
- Jednoduchý úspěch: `{"ok": True}` s 200
- Úspěch s daty: flat JSON objekt s relevatními klíči, 200
- Asynchronní spuštění: `{"success": True, "session_id": "..."}` s 202
- Selhání externí závislosti (gh CLI, git, subprocess): 502
- Špatný/chybějící vstup: 400; sémanticky nevalidní: 422

## Testování

- Testovat: každý nový API endpoint přes Flask `test_client` (integrace)
- Mockovat: pouze vnější závislosti — `subprocess`, gh CLI, síť; nikdy Flask routing ani Pydantic
- Struktura: `unittest.TestCase`, třídy per endpoint, popisné názvy metod
- Povinné třídy testů: validace vstupu, chyba externí závislosti, happy path
- Coverage: 100 % větví každého nového endpointu; při úpravě existující logiky přidáš testy pro větve které měníš nebo přidáváš

## Formát PR a commitů

- Prefix: `feat:` (nová funkce) nebo `fix:` (oprava bugu)
- Squash merge — PR popis = commit message pro `main`; piš ho tak
- Čísla issues a PR na konci: `(#42–#45) (#46)`
- Jazyk: česky

## Formulářový stav

- Každý formulář má jediný `editable: bool` prop — rozhoduje o všem
- Read-only stav = všechna pole `disabled`, žádná akční tlačítka
- Nikdy nesměšovat editable/read-only uvnitř jednoho sfField renderu
