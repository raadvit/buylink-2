/* =====================================================
   Task forge — Stories list page logic
   Plain JS, no framework. Renders rows, handles filter
   tabs, the epic side panel, and pagination ranges.
   ===================================================== */

/* ---------- Data ---------- */
const STORIES = [
  { id: 'TF-419', title: 'Vyřešit konflikt CTA barev v checkout flow',  epic: 'EP-01 Task-forge', status: 'Konflikt',    cost: 1240, updated: '24. 4. 2026', conflicts: 1, agentState: 'reviewing' },
  { id: 'TF-418', title: 'Sjednotit CTA barvy napříč produktem',         epic: 'EP-01 Task-forge', status: 'Dev plán',    cost: 2080, updated: '24. 4. 2026', conflicts: 0, agentState: 'idle' },
  { id: 'TF-417', title: 'Onboarding pro nové sellery — krok 2',         epic: 'EP-02 Onboarding', status: 'Draft',       cost: null, updated: '24. 4. 2026', conflicts: 0, agentState: 'drafting' },
  { id: 'TF-416', title: 'Prázdný stav reportu po filtraci',             epic: 'EP-04 Reporting',  status: 'Arch review', cost: 640,  updated: '23. 4. 2026', conflicts: 0, agentState: 'idle' },
  { id: 'TF-415', title: 'Validace IBAN při zadání platebního údaje',    epic: 'EP-03 Billing',    status: 'Verify',      cost: 1320, updated: '23. 4. 2026', conflicts: 0, agentState: 'idle' },
  { id: 'TF-414', title: 'Notifikace o blížícím se vypršení smlouvy',    epic: 'EP-04 Reporting',  status: 'Done',        cost: 1180, updated: '21. 4. 2026', conflicts: 0, agentState: 'idle' },
  { id: 'TF-413', title: 'Editace adresy v profilu — chybové hlášky',    epic: 'EP-02 Onboarding', status: 'Draft',       cost: null, updated: '21. 4. 2026', conflicts: 2, agentState: 'reviewing' },
  { id: 'TF-412', title: 'Bug: dvojklik na "Vytvořit story" duplikuje',  epic: 'EP-01 Task-forge', status: 'Dev plán',     cost: 480,  updated: '18. 4. 2026', conflicts: 0, agentState: 'idle', isBug: true },
  { id: 'TF-411', title: 'Refaktor: sjednotit ikonografii v navigaci',   epic: 'EP-01 Task-forge', status: 'Done',        cost: 720,  updated: '18. 4. 2026', conflicts: 0, agentState: 'idle' },
];

/* ---------- Helpers ---------- */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const STATUS_CLASS = {
  'Draft':       'status-pill--draft',
  'Konflikt':    'status-pill--konflikt',
  'Arch review': 'status-pill--arch',
  'Dev plán':    'status-pill--devplan',
  'Verify':      'status-pill--verify',
  'Done':        'status-pill--done',
};

const formatCost = c => c == null ? '—' : `${c.toLocaleString('cs-CZ')} Kč`;

/* ---------- State ---------- */
const state = { filter: 'open', epicFilter: null };

/* ---------- Rendering ---------- */
function getFiltered() {
  let rows = STORIES;
  if (state.epicFilter) rows = rows.filter(s => s.epic === state.epicFilter);
  if (state.filter === 'userstory') return rows.filter(s => !s.isBug);
  if (state.filter === 'bugs')      return rows.filter(s =>  s.isBug);
  if (state.filter === 'closed')    return rows.filter(s => s.status === 'Done');
  return rows.filter(s => s.status !== 'Done'); // 'open'
}

function renderRows() {
  const rows = getFiltered();
  const body = $('#storiesBody');
  body.innerHTML = rows.map(s => {
    const conflictBadge = s.conflicts > 0
      ? `<span class="conflict-badge"><span class="conflict-badge__dot"></span>${s.conflicts}</span>`
      : '';
    const agentDot = s.agentState && s.agentState !== 'idle'
      ? `<span class="agent-dot agent-dot--${s.agentState}" title="Agent ${s.agentState === 'reviewing' ? 'právě reviewuje' : 'právě píše draft'}"><span class="agent-dot__pulse"></span></span>`
      : '';
    const idCell = s.isBug
      ? `<span class="cell-id__bug-dot" aria-label="Bug"></span><span>${s.id}</span>`
      : `<span>${s.id}</span>`;
    const typePill = s.isBug
      ? `<span class="type-pill type-pill--bug">● Bug</span>`
      : `<span class="type-pill">User story</span>`;

    return `
      <a class="table__row" role="row" href="../story-detail/index.html">
        <div class="cell-id" role="cell">${idCell}</div>
        <div class="cell-title" role="cell">
          ${agentDot}
          <span class="cell-title__text">${s.title}</span>
          ${conflictBadge}
        </div>
        <div role="cell"><span class="status-pill ${STATUS_CLASS[s.status]}">${s.status}</span></div>
        <div class="cell-epic col-epic" role="cell">${s.epic}</div>
        <div class="col-type" role="cell">${typePill}</div>
        <div class="cell-cost ta-right col-cost" role="cell">${formatCost(s.cost)}</div>
        <div class="cell-updated ta-right col-updated" role="cell">${s.updated}</div>
      </a>
    `;
  }).join('');

  // Counts on tabs
  const baseRows = state.epicFilter ? STORIES.filter(s => s.epic === state.epicFilter) : STORIES;
  $('#cnt-open').textContent      = baseRows.filter(s => s.status !== 'Done').length;
  $('#cnt-userstory').textContent = baseRows.filter(s => !s.isBug).length;
  $('#cnt-bugs').textContent      = baseRows.filter(s =>  s.isBug).length;
  $('#cnt-closed').textContent    = baseRows.filter(s => s.status === 'Done').length;

  // Pagination range
  $('#rangeShown').textContent = rows.length === 0 ? '0' : `1–${rows.length}`;
  $('#rangeTotal').textContent = rows.length;

  // Page title + breadcrumb
  const epics = buildEpics();
  if (state.epicFilter) {
    const e = epics.find(x => x.full === state.epicFilter);
    $('#pageTitle').textContent = e ? e.name : 'Seznam stories';
    $('#breadcrumb').innerHTML  = `<a id="bcAll">Všechny epicy</a> <span class="sep">›</span> <span class="mono">${e.id}</span> · ${e.count} stories`;
    $('#bcAll').addEventListener('click', () => { state.epicFilter = null; renderAll(); });
  } else {
    $('#pageTitle').textContent = 'Seznam stories';
    $('#breadcrumb').innerHTML  = `<span class="mono">EP-01 Task-forge</span> · ${epics.length} epiky v sprintu`;
  }
}

function buildEpics() {
  const map = new Map();
  STORIES.forEach(s => {
    if (!map.has(s.epic)) {
      map.set(s.epic, {
        id:    s.epic.split(' ')[0],
        name:  s.epic.split(' ').slice(1).join(' '),
        full:  s.epic,
        count: 0, openCount: 0,
      });
    }
    const o = map.get(s.epic);
    o.count++;
    if (s.status !== 'Done') o.openCount++;
  });
  return Array.from(map.values());
}

function renderEpicPanel() {
  const epics = buildEpics();
  const html = [
    `<button class="epic-row epic-row--all ${!state.epicFilter ? 'is-active' : ''}" data-epic="" type="button">
       <div class="epic-row__main">
         <span class="epic-row__square"></span>
         <span class="epic-row__name">Všechny epicy</span>
       </div>
       <span class="epic-row__count">${STORIES.length}</span>
     </button>`,
    `<div class="epic-list__sep"></div>`,
    ...epics.map(e => `
      <button class="epic-row ${state.epicFilter === e.full ? 'is-active' : ''}" data-epic="${e.full}" type="button">
        <div class="epic-row__main">
          <div class="epic-row__line">
            <span class="epic-row__id mono">${e.id}</span>
          </div>
          <span class="epic-row__name">${e.name}</span>
          <span class="epic-row__sub">${e.openCount} otevřených · ${e.count} celkem</span>
        </div>
        <span class="epic-row__count">${e.count}</span>
      </button>
    `),
  ].join('');
  $('#epicList').innerHTML = html;

  $$('#epicList .epic-row').forEach(btn => {
    btn.addEventListener('click', () => {
      const v = btn.getAttribute('data-epic');
      state.epicFilter = v || null;
      closeEpicPanel();
      renderAll();
    });
  });
}

function renderAll() {
  renderEpicPanel();
  renderRows();
}

/* ---------- Filter tabs ---------- */
$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => { t.classList.remove('is-active'); t.setAttribute('aria-selected', 'false'); });
    tab.classList.add('is-active');
    tab.setAttribute('aria-selected', 'true');
    state.filter = tab.getAttribute('data-filter');
    renderRows();
  });
});

/* ---------- Epic panel open/close ---------- */
function openEpicPanel() {
  $('#epicPanel').classList.add('is-open');
  $('#epicPanel').setAttribute('aria-hidden', 'false');
  $('#epicScrim').hidden = false;
}
function closeEpicPanel() {
  $('#epicPanel').classList.remove('is-open');
  $('#epicPanel').setAttribute('aria-hidden', 'true');
  $('#epicScrim').hidden = true;
}
$('#epicOpen').addEventListener('click', openEpicPanel);
$('#epicClose').addEventListener('click', closeEpicPanel);
$('#epicScrim').addEventListener('click', closeEpicPanel);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeEpicPanel(); });

/* ---------- Boot ---------- */
renderAll();
