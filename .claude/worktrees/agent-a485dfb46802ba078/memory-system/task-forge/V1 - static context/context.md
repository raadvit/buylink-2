# Kontext — Task Forge

Task Forge je interní admin nástroj pro správu user stories a agentového workflow.

## Technický stack
- Backend: Python / Flask
- Frontend: Vanilla JS, HTML, CSS (vlastní design systém)
- Integrace: GitHub CLI (`gh`), Claude Code CLI (`claude`)

## Struktura projektu
| Adresář | Popis |
|---|---|
| `task-forge/` | Samotná aplikace |
| `task-forge/static/` | Frontend (HTML, CSS, JS) |
| `wiki/stories/` | Story soubory (markdown) |
| `wiki/style-guide/` | Design systém (source of truth) |
| `docs/components/` | Komponentová knihovna |

## URL struktura
| URL | Stránka |
|---|---|
| `/` | Homepage |
| `/list` | Seznam stories |
| `/create-story` | Nový požadavek |
| `/create-bug` | Nahlásit bug |
| `/us-{id}` | Detail story |
| `/preview` | Design preview |
