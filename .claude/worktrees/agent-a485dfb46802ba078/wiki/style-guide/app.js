/* =====================================================
   Task forge — Seznam stories
   Vanilla JS: filtering + row rendering
   ===================================================== */

const STORIES = [
  { id: 'TF-419', title: 'Vyřešit konflikt CTA barev v checkout flow', epic: 'EP-01', status: 'Konflikt',    cost: 1240, updated: '24. 4. 2026', conflicts: 1, agentState: 'reviewing', isBug: false },
  { id: 'TF-418', title: 'Sjednotit CTA barvy napříč produktem',        epic: 'EP-01', status: 'Dev plán',   cost: 2080, updated: '24. 4. 2026', conflicts: 0, agentState: null,        isBug: false },
  { id: 'TF-417', title: 'Onboarding pro nové sellery — krok 2',        epic: 'EP-02', status: 'Draft',      cost: null, updated: '24. 4. 2026', conflicts: 0, agentState: 'drafting',  isBug: false },
  { id: 'TF-416', title: 'Prázdný stav reportu po filtraci',            epic: 'EP-04', status: 'Arch review',cost: 640,  updated: '23. 4. 2026', conflicts: 0, agentState: null,        isBug: false },
  { id: 'TF-415', title: 'Validace IBAN při zadání platebního údaje',   epic: 'EP-03', status: 'Verify',     cost: 1320, updated: '23. 4. 2026', conflicts: 0, agentState: null,        isBug: false },
  { id: 'TF-414', title: 'Notifikace o blížícím se vypršení smlouvy',   epic: 'EP-04', status: 'Done',       cost: 1180, updated: '21. 4. 2026', conflicts: 0, agentState: null,        isBug: false },
  { id: 'TF-413', title: 'Editace adresy v profilu — chybové hlášky',   epic: 'EP-02', status: 'Draft',      cost: null, updated: '21. 4. 2026', conflicts: 2, agentState: 'reviewing', isBug: false },
  { id: 'TF-412', title: 'Bug: dvojklik na "Vytvořit story" duplikuje', epic: 'EP-01', status: 'Dev plán',   cost: 480,  updated: '18. 4. 2026', conflicts: 0, agentState: null,        isBug: true  },
  { id: 'TF-411', title: 'Refaktor: sjednotit ikonografii v navigaci',  epic: 'EP-01', status: 'Done',       cost: 720,  updated: '18. 4. 2026', conflicts: 0, agentState: null,        isBug: false },
];

// --- Status meta ---
const STATUS_CLASS = {
  'Draft':       'status-pill--draft',
  'Konflikt':    'status-pill--konflikt',
  'Arch review': 'status-pill--arch',
  'Dev plán':    'status-pill--devplan',
  'Verify':      'status-pill--verify',
  'Done':        'status-pill--done',
};


// --- Filters ---
const FILTERS = {
  open:      s => s.status !== 'Done',
  userstory: s => !s.isBug,
  bugs:      s => s.isBug,
  closed:    s => s.status === 'Done',
};

let currentFilter = 'open';


// --- Helpers ---
function escapeHTML(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function formatCost(cost) {
  if (cost == null) {
    return `<span class="cell-cost--empty">—</span>`;
  }
  return `${cost.toLocaleString('cs-CZ')} <span class="cell-cost__cur">$</span>`;
}


// --- Row template ---
function renderRow(s) {
  const statusClass = STATUS_CLASS[s.status] || 'status-pill--draft';

  const conflictBadge = s.conflicts > 0
    ? `<span class="conflict-badge" title="${s.conflicts} konflikt">
         <span class="conflict-badge__dot"></span>${s.conflicts}
       </span>`
    : '';

  const agentDot = s.agentState
    ? `<span class="agent-dot agent-dot--${s.agentState}"
              title="${s.agentState === 'reviewing'
                       ? 'Agent prochází závislosti'
                       : 'Agent navrhuje akceptační kritéria'}">
         <span class="agent-dot__pulse"></span>
       </span>`
    : '';

  const typePill = s.isBug
    ? `<span class="type-pill type-pill--bug"><span class="type-pill__dot"></span>Bug</span>`
    : `<span class="type-pill type-pill--story"><span class="type-pill__dot"></span>User story</span>`;

  const idCell = `
    <div class="cell-id">
      ${s.isBug ? '<span class="cell-id__bug-dot"></span>' : ''}
      ${escapeHTML(s.id)}
    </div>`;

  return `
    <div class="table__row" role="row" data-id="${escapeHTML(s.id)}">
      ${idCell}
      <div class="cell-title">
        <span class="cell-title__text">${escapeHTML(s.title)}</span>
        ${conflictBadge}
        ${agentDot}
      </div>
      <div><span class="status-pill ${statusClass}">${escapeHTML(s.status)}</span></div>
      <div class="cell-epic col-epic">${escapeHTML(s.epic)}</div>
      <div class="col-type">${typePill}</div>
      <div class="col-cost cell-cost">${formatCost(s.cost)}</div>
      <div class="cell-date col-updated">${escapeHTML(s.updated)}</div>
    </div>`;
}


// --- Render ---
function render() {
  const filterFn = FILTERS[currentFilter] || (() => true);
  const rows = STORIES.filter(filterFn);

  document.getElementById('storiesBody').innerHTML = rows.map(renderRow).join('');

  // Update tab counts
  Object.entries(FILTERS).forEach(([key, fn]) => {
    const tab = document.querySelector(`[data-filter="${key}"]`);
    if (!tab) return;
    const count = STORIES.filter(fn).length;
    let countEl = tab.querySelector('.tab__count');
    if (countEl) countEl.textContent = String(count);
  });

  // Update range label
  document.getElementById('rangeShown').textContent = rows.length === 0 ? '0' : `1–${rows.length}`;
  document.getElementById('rangeTotal').textContent = String(rows.length);
}


// --- Tab interaction ---
document.querySelectorAll('.filters__tabs .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filters__tabs .tab').forEach(t => {
      t.classList.remove('is-active');
      t.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('is-active');
    tab.setAttribute('aria-selected', 'true');
    currentFilter = tab.dataset.filter;
    render();
  });
});


// --- Row click (placeholder — open detail) ---
document.getElementById('storiesBody').addEventListener('click', e => {
  const row = e.target.closest('.table__row');
  if (!row) return;
  console.log('open story', row.dataset.id);
});


// --- Init ---
render();
