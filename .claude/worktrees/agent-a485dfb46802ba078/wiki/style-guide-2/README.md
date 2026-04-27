# Task forge — Static export

Two pages, fully self-contained. Open either `index.html` directly in a browser — no build step, no server required.

## Structure

```
export/
├── shared.css                  Design tokens + TopNav/buttons/forms primitives (used by stories-list)
├── stories-list/
│   ├── index.html              Plain HTML page
│   ├── styles.css              Page-specific styles (table, filters, epic side panel)
│   └── app.js                  Vanilla JS — data, filtering, panel open/close
└── story-detail/
    ├── index.html              Loads React + Babel and the two .jsx files below
    ├── shared.jsx              TopNav, stepper, agent components, SHARED_CSS string
    └── variation-a.jsx         The story-detail layout (form + agent chat)
```

## Cross-page navigation

- **Stories list** → click any row to open `../story-detail/index.html`
- **Story detail** → click "Seznam stories" in the top nav, or the "Stories" breadcrumb, to return

## Tech notes

- Stories list is plain HTML/CSS/JS — easy to wire to a real API, just replace the `STORIES` array in `app.js`.
- Story detail uses in-browser Babel for JSX (development only). For production, precompile the two `.jsx` files to `.js`.
- Both pages load Inter + JetBrains Mono from Google Fonts.
- Czech labels are preserved verbatim.
