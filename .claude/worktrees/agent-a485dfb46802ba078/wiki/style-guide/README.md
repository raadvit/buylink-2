# Task forge — Seznam stories (standalone export)

Self-contained vanilla HTML/CSS/JS implementation of the **Stories list** screen + **Top navigation** header.

No build step, no framework — open `index.html` in any browser and it works.

## Files

| File | Purpose |
|---|---|
| `index.html` | Markup for the top nav, page header, filter tabs, table, and pagination. |
| `styles.css` | All styling. Design tokens are CSS custom properties at the top of the file (`:root`). |
| `app.js` | Story data + render loop + filter tab interaction. |

## Customization

- **Brand color** — change `--accent` in `styles.css` (it's `oklch(52% 0.18 290)`, hue `290` = purple).
- **Story data** — edit the `STORIES` array at the top of `app.js`. Each row needs: `id`, `title`, `epic`, `status`, `cost`, `updated`, `conflicts`, `agentState`, `isBug`.
- **Status colors** — see `.status-pill--*` classes in `styles.css`.
- **New filter tabs** — add a button with `data-filter="key"` in `index.html` and a matching predicate in the `FILTERS` object in `app.js`.

## Notes

- Row click currently logs to console — wire `app.js`'s row-click handler to your routing.
- "Vytvořit bug" / "+ Vytvořit story" buttons in the top nav are not wired — add your own click handlers.
- Search input has no behavior yet.
- Pagination is visual only.

## Browser support

Uses `oklch()` colors and CSS Grid — works in all evergreen browsers (Chrome, Safari, Firefox, Edge from late 2023 onward).
