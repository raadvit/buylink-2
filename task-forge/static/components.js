/* =====================================================
   Task forge — Komponenty
   Každá funkce vrací HTML string nebo renderuje do containeru.
   Zdroj pravdy: wiki/style-guide/
   ===================================================== */

// ── Helpers ──────────────────────────────────────────────────────────────────

function escapeHTML(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function formatCost(cost) {
  if (cost == null) return `<span class="cell-cost--empty">—</span>`;
  return `<span class="cell-cost__number">${cost.toLocaleString('cs-CZ', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}</span> <span class="cell-cost__cur">$</span>`;
}


// ── PageHeader ────────────────────────────────────────────────────────────────
// Použití: renderPageHeader({ breadcrumb: 'EP-01 · 3 epicy', title: 'Seznam stories' })

function renderPageHeader({ breadcrumb = '', title = '' } = {}) {
  return `
    <div class="page__header">
      ${breadcrumb ? `<div class="page__breadcrumb mono">${escapeHTML(breadcrumb)}</div>` : ''}
      <h1 class="page__title">${escapeHTML(title)}</h1>
    </div>`;
}


// ── FilterTabs ────────────────────────────────────────────────────────────────
// Použití:
//   renderFilterTabs({
//     tabs: [{ key: 'open', label: 'Otevřené', count: 7 }, ...],
//     active: 'open',
//     agentBanner: 'Agent právě reviewuje <b>2 stories</b>…',  // optional — trusted HTML only, never from API
//   })

function renderQueueChip({ label, count, key, active, activeBg, idleBg, idleBorder, idleColor, badgeBg }) {
  if (count === 0) {
    return `<span class="queue-chip queue-chip--empty" title="${escapeHTML(label)} — žádné stories">
      <span class="queue-chip__badge queue-chip__badge--empty">0</span>
      <span>${escapeHTML(label)}</span>
    </span>`;
  }
  return `<button class="queue-chip" data-filter="${escapeHTML(key)}" type="button"
      style="background:${active ? activeBg : idleBg};color:${active ? 'white' : idleColor};border-color:${active ? activeBg : idleBorder}">
    <span class="queue-chip__badge" style="background:${active ? 'rgba(255,255,255,0.22)' : badgeBg}">${count}</span>
    <span>${escapeHTML(label)}</span>
  </button>`;
}


function renderFilterTabs({ tabs = [], active = '', agentBanner = '', trailing = '' } = {}) {
  const tabsHtml = tabs.map(t => `
    <button class="tab${t.key === active ? ' is-active' : ''}"
            data-filter="${escapeHTML(t.key)}" type="button"
            role="tab" aria-selected="${t.key === active ? 'true' : 'false'}">
      ${escapeHTML(t.label)}
      ${t.count != null ? `<span class="tab__count">${t.count}</span>` : ''}
    </button>`).join('');

  const bannerHtml = agentBanner ? `
    <div class="agent-banner">
      <span class="agent-banner__avatar" aria-hidden="true">
        <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
          <path d="M8 2 L13 8 L8 14 L3 8 Z" fill="white" opacity="0.95"/>
          <circle cx="8" cy="8" r="2" fill="currentColor"/>
        </svg>
      </span>
      ${agentBanner}
    </div>` : '';

  return `
    <div class="filters">
      <div class="filters__tabs" role="tablist">${tabsHtml}</div>
      ${bannerHtml}
      ${trailing ? `<div class="filters__trailing">${trailing}</div>` : ''}
    </div>`;
}


// ── StatusPill ────────────────────────────────────────────────────────────────

const SPINNER_STATUSES = new Set(['Draft', 'Vývoj']);

function renderStatusPill(label, cls) {
  const spinner = SPINNER_STATUSES.has(label)
    ? `<svg class="status-pill__spinner" width="11" height="11" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-opacity="0.25" stroke-width="2"/>
        <path d="M8 2 a6 6 0 0 1 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
       </svg>`
    : '';
  return `<span class="status-pill ${cls}">${escapeHTML(label)}${spinner}</span>`;
}


// ── TableRow ──────────────────────────────────────────────────────────────────

const STATUS_CLASS = {
  'Draft':       'status-pill--draft',
  'Konflikt':    'status-pill--konflikt',
  'Arch review': 'status-pill--arch',
  'Dev plán':    'status-pill--devplan',
  'Testing':     'status-pill--verify',
  'Done':        'status-pill--done',
};

function renderTableRow(s) {
  const statusClass = STATUS_CLASS[s.status] || 'status-pill--draft';

  const conflictBadge = s.conflicts > 0
    ? `<span class="conflict-badge" title="${s.conflicts} konflikt">
         <span class="conflict-badge__dot"></span>${s.conflicts}
       </span>` : '';

  const agentDot = s.agentState
    ? `<span class="agent-dot agent-dot--${s.agentState}"
              title="${s.agentState === 'reviewing' ? 'Agent prochází závislosti' : 'Agent navrhuje akceptační kritéria'}">
         <span class="agent-dot__pulse"></span>
       </span>` : '';

  const typePill = s.isBug
    ? `<span class="type-pill type-pill--bug"><span class="type-pill__dot"></span>Bug</span>`
    : `<span class="type-pill type-pill--story"><span class="type-pill__dot"></span>User story</span>`;

  return `
    <div class="table__row${s.isSelected ? ' table__row--selected' : ''}" role="row" data-id="${escapeHTML(s.id)}">
      <div class="col-check"><input type="checkbox" class="row-check" aria-label="Vybrat řádek"></div>
      <div class="cell-id">
        ${s.detailUrl
          ? `<a href="${escapeHTML(s.detailUrl)}" class="cell-id__link">${escapeHTML(s.id)}</a>`
          : escapeHTML(s.id)}
        ${s.isBug ? '<span class="cell-id__bug-dot"></span>' : ''}
      </div>
      <div class="cell-title">
        ${s.detailUrl
          ? `<a class="cell-title__text" href="${escapeHTML(s.detailUrl)}">${escapeHTML(s.title)}</a>`
          : `<span class="cell-title__text">${escapeHTML(s.title)}</span>`}
        ${conflictBadge}${agentDot}
      </div>
      <div>${renderStatusPill(s.status, statusClass)}</div>
      <div class="cell-epic col-epic">${escapeHTML(s.epic)}</div>
      <div class="col-type">${typePill}</div>
      <div class="col-cost cell-cost">${formatCost(s.cost)}</div>
      <div class="col-duration"${s.durationDetail ? ` title="${escapeHTML(s.durationDetail)}"` : ''}>${escapeHTML(s.duration ?? '–')}</div>
    </div>`;
}


// ── Table ─────────────────────────────────────────────────────────────────────
// Použití: renderTable({ bodyId: 'storiesBody' })
// Řádky se renderují zvlášť přes renderTableRow a vkládají do bodyId.

function renderTable({ bodyId = 'storiesBody' } = {}) {
  return `
    <div class="table" role="table">
      <div class="table__head" role="row">
        <div role="columnheader" class="col-check"><input type="checkbox" id="selectAll" aria-label="Vybrat vše"></div>
        <div role="columnheader">ID</div>
        <div role="columnheader">Název</div>
        <div role="columnheader">Status</div>
        <div role="columnheader" class="col-epic">Epic</div>
        <div role="columnheader" class="col-type">Typ</div>
        <div role="columnheader" class="ta-right col-cost">Náklady</div>
        <div role="columnheader" class="ta-right col-duration">Duration</div>
      </div>
      <div class="table__body" id="${escapeHTML(bodyId)}"></div>
    </div>`;
}


// ── Pagination ────────────────────────────────────────────────────────────────
// Použití: renderPagination({ current, pageCount, pageSize, shownRange, totalCount })
// Tlačítka mají data-page atribut — click handlery připoj v nadřazeném kódu.

function renderPagination({ current = 1, pageCount = 1, pageSize = 50, shownRange = '0', totalCount = 0 } = {}) {
  const prevDisabled = current <= 1 ? ' disabled' : '';
  const nextDisabled = current >= pageCount ? ' disabled' : '';

  // Zobraz max 5 stránek kolem aktuální, zbytek zkrátit
  const visiblePages = [];
  for (let p = 1; p <= pageCount; p++) {
    if (p === 1 || p === pageCount || (p >= current - 2 && p <= current + 2)) {
      visiblePages.push(p);
    }
  }

  let pagesBtns = '';
  let prev = null;
  for (const p of visiblePages) {
    if (prev !== null && p - prev > 1) {
      pagesBtns += `<span class="pagination__ellipsis">…</span>`;
    }
    pagesBtns += `<button class="pagination__btn${p === current ? ' is-active' : ''}" type="button" data-page="${p}">${p}</button>`;
    prev = p;
  }

  return `
    <div class="page__footer">
      <span class="page__count">Zobrazeno <b>${escapeHTML(String(shownRange))}</b> z ${totalCount}</span>
      <div class="pagination">
        <span class="pagination__pagesize">${pageSize} na stránku</span>
        <span class="pagination__divider"></span>
        <button class="pagination__btn"${prevDisabled} data-page="${current - 1}" aria-label="Předchozí stránka">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M6.5 2 L3.5 5 L6.5 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        ${pagesBtns}
        <button class="pagination__btn"${nextDisabled} data-page="${current + 1}" aria-label="Další stránka">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M3.5 2 L6.5 5 L3.5 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </div>`;
}
