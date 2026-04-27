# TopNav

## Účel
Sdílená horizontální navigace zobrazená na všech stránkách aplikace. Poskytuje orientaci, přístup k hlavním akcím, vyhledávání, notifikace a uživatelský kontext.

## Design tokeny
- `--surface` — pozadí navbaru
- `--line` — spodní border a oddělovač
- `--ink`, `--ink-2`, `--ink-3` — text a ikony
- `--surface-2` — hover stav odkazů
- `--accent` — primární tlačítko

## Varianty
Komponenta je jednotná; liší se pouze aktivní stránka (`is-active` na nav-linku).

## Stavy

| Element | Stavy |
|---|---|
| `.nav-link` | `default`, `hover`, `is-active` |
| `.btn--primary`, `.btn--secondary` | `default`, `hover` |
| `.icon-btn` | `default`, `hover` |
| `.user-menu` | `default`, `hover`, `focus-visible` |

## Props / vstupy

| Prop | Typ | Popis |
|---|---|---|
| `activePage` | `'story' \| 'list' \| 'bug'` | Určuje, který nav-link dostane třídu `is-active` |

## Chování
- Sticky navigace — zůstává viditelná při scrollu (`position: sticky; top: 0; z-index: 10`)
- `initNav(activePage)` vloží `.topnav` jako první child `<body>` při volání
- Vyhledávání je vizuální (statické, bez funkcionality)
- Notifikační tlačítko je statické (bez akce)
- Uživatelské menu je statické (bez dropdownu)
- Na viewportu ≤ 880 px se `.user-menu__meta` a chevron ikona skryjí (jen avatar)

## A11y
- Logo `<a>` má viditelný text "Task Forge"
- Nav-linky jsou sémantické `<a>` elementy
- `.icon-btn` notifikace má `aria-label="Notifikace"`
- `.user-menu` má `role="button"`, `tabindex="0"` a `aria-label="Uživatelské menu"`

## Implementace
- Soubor: `task-forge/static/nav.js`
- CSS třídy: `.topnav`, `.topnav__left`, `.topnav__right`, `.topnav__logo`, `.topnav__logo-mark`, `.topnav__logo-name`, `.topnav__nav`, `.topnav__search-wrap`, `.topnav__divider`, `.nav-link`, `.nav-link.is-active`, `.search`, `.search__kbd`, `.btn`, `.btn--primary`, `.btn--secondary`, `.icon-btn`, `.user-menu`, `.user-menu__avatar`, `.user-menu__meta`, `.user-menu__name`, `.user-menu__role`
- Použití: přidat `<script src="/static/nav.js"></script>` do `<head>` a zavolat `initNav('story' | 'list' | 'bug')` na konci `<body>`
