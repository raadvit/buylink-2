# Konfigurace projektu

## GitHub repozitáře

- **Main_repo** (user stories, issues, PR): `/`

## QA



## Implementace

- **architect_creates_implementation_plan**: `true`
  - `true` → Architekt Fáze 1 (validace story) přibalí do story i implementační plán dle handshake formátu z `agents.md`. `/implement` pak Fáze 2 Architekta přeskočí a použije plán přímo ze story.
  - `false` → Standardní flow: Fáze 1 Architekt píše jen tech. anotace; Fáze 2 Architekt v `/implement` vytvoří implementační plán.

## UX

- **EP-01 Task-forge**: vlastní design systém — viz `wiki/style-guide/styles.css` a `docs/components/index.md`
  - Žádný Material Design 3
  - Vždy CSS tokeny z `:root`, existující třídy z style guide
  - Komponentová knihovna: `docs/components/` — designer-ux udržuje, developer-fe doplňuje implementaci
- **Ostatní epics**: Material Design 3 — https://m3.material.io/components

## UX designer — kdy zapojit do analýzy

Designer-ux se přidává do architektonické analýzy (vedle Architekta) pokud story:
- mění vizuální design, layout nebo styling (`writes_sections` obsahuje `timeline-widget`, `layout`, `ui`, `style`)
- přidává nebo mění UI komponenty
- zavádí nové barevné nebo typografické prvky
- je označena jako redesign nebo restyling