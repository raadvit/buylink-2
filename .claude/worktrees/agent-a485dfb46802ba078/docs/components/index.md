# Komponentová knihovna — Task Forge

Každá komponenta má vlastní spec soubor. Vytvářejí/aktualizují je designer-ux a developer-fe.

## Primitiva

| Komponenta | Soubor | Stav |
|---|---|---|
| Button | [button.md](button.md) | — |
| IconButton | [icon-button.md](icon-button.md) | — |
| Badge / Pill | [badge.md](badge.md) | — |
| Tab | [tab.md](tab.md) | — |
| Input / Search | [input.md](input.md) | — |

## Layout

| Komponenta | Soubor | Stav |
|---|---|---|
| TopNav | [topnav.md](topnav.md) | — |
| PageLayout | [page-layout.md](page-layout.md) | — |
| Table | [table.md](table.md) | — |

## Domain komponenty (Task Forge)

| Komponenta | Soubor | Stav |
|---|---|---|
| StoryRow | [story-row.md](story-row.md) | — |
| StoryTimeline | [story-timeline.md](story-timeline.md) | — |
| AgentBanner | [agent-banner.md](agent-banner.md) | — |
| StatusPill | [status-pill.md](status-pill.md) | — |
| FilterTabs | [filter-tabs.md](filter-tabs.md) | — |

---

## Jak přidat novou komponentu

1. Přidej řádek do tabulky výše
2. Vytvoř soubor `docs/components/{název}.md` dle šablony níže
3. Frontend Developer doplní implementační detaily po kódování

```markdown
# [NázevKomponenty]

## Účel
Co komponenta dělá a kdy se používá.

## Design tokeny
Které CSS custom properties z `:root` používá.

## Varianty
- `default` —
- (další varianty)

## Stavy
- `default` / `hover` / `active` / `disabled` / `loading` / `error`

## Props / vstupy

| Prop | Typ | Popis |
|---|---|---|

## Chování
Interakce, přechody, animace.

## A11y
ARIA role, keyboard navigation.

## Implementace
> Doplní developer-fe po kódování.
- Soubor: `task-forge/static/...`
- CSS třídy: `.xxx`
```
