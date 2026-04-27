/**
 * Task Forge — sdílená TopNav
 * initNav(activePage) — vloží .topnav jako první child <body>
 * @param {'home' | 'list' | 'create-story' | 'create-bug'} activePage
 */

// Inject link resets raz za session — text-decoration pro <a> tagy, BEZ color override
// (btn varianty potřebují vlastní barvy: btn--primary white, btn--bug danger)
if (!document.getElementById('nav-link-resets')) {
  const s = document.createElement('style');
  s.id = 'nav-link-resets';
  s.textContent = 'a.topnav__logo{text-decoration:none;color:inherit} a.btn{text-decoration:none} a.nav-link,.nav-link,.nav-link:hover,.nav-link.is-active{background:var(--ink)!important;color:white!important;text-decoration:none}';
  document.head.appendChild(s);
}

function initNav(activePage) {
  const nav = document.createElement('header');
  nav.className = 'topnav';
  nav.innerHTML = `
    <!-- Left: logo + primary nav -->
    <div class="topnav__left">
      <a href="/list" class="topnav__logo">
        <div class="topnav__logo-mark">TF</div>
        <div class="topnav__logo-name">Task Forge</div>
      </a>
      <nav class="topnav__nav">
        <a href="/list" class="nav-link${activePage === 'list' ? ' is-active' : ''}" aria-current="${activePage === 'list' ? 'page' : 'false'}">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <rect x="2" y="3"    width="10" height="1.5" rx="0.5" fill="currentColor"/>
            <rect x="2" y="6.25" width="10" height="1.5" rx="0.5" fill="currentColor"/>
            <rect x="2" y="9.5"  width="10" height="1.5" rx="0.5" fill="currentColor"/>
          </svg>
          Seznam stories
        </a>
      </nav>
    </div>

    <!-- Center: search -->
    <div class="topnav__search-wrap">
      <div class="search">
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <circle cx="6" cy="6" r="4" stroke="currentColor" stroke-width="1.5"/>
          <path d="M9 9 L12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input type="text" placeholder="Hledat tickety, epicy, lidi…" tabindex="-1" readonly />
        <span class="search__kbd mono">⌘K</span>
      </div>
    </div>

    <!-- Right: actions + user -->
    <div class="topnav__right">
      <a href="/create-bug" class="btn btn--secondary btn--bug">
        <span class="dot dot--danger"></span>
        Vytvořit bug
      </a>
      <a href="/create-story-2" class="btn btn--primary">+ Vytvořit story</a>
      <span class="topnav__divider"></span>

      <button class="icon-btn" type="button" aria-label="Notifikace">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3.5 11 V7.5 a4.5 4.5 0 0 1 9 0 V11 l1 1.5 H2.5 Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
          <path d="M6.5 13.5 a1.5 1.5 0 0 0 3 0" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        <span class="icon-btn__badge"></span>
      </button>

      <div class="user-menu" tabindex="0" role="button" aria-label="Uživatelské menu">
        <div class="user-menu__avatar">RV</div>
        <div class="user-menu__meta">
          <span class="user-menu__name">Radek Vít</span>
          <span class="user-menu__project"></span>
        </div>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
          <path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    </div>
  `;

  document.body.insertBefore(nav, document.body.firstChild);

  fetch('/api/config')
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      const el = document.querySelector('.user-menu__project');
      if (el && data && data.project_name) {
        el.textContent = data.project_name;
      }
    })
    .catch(() => {});
}
