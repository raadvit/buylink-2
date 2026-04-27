function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Loading spinner pro .tf-btn ──
// Click → data-loading="1" na 1.4s, blokuje double-click, ukazuje rotující kolečko.
// Opt-out: data-no-loading="1"
(function () {
  if (window.__tfBtnLoadingBound) return;
  window.__tfBtnLoadingBound = true;
  const DURATION_MS = 1400;
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.tf-btn');
    if (!btn) return;
    if (btn.disabled) return;
    if (btn.dataset.loading === '1') return;
    if (btn.dataset.noLoading === '1') return;
    btn.dataset.loading = '1';
    setTimeout(function () { delete btn.dataset.loading; }, DURATION_MS);
  }, true);
})();

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ── Story timeline widget ──
const _TIMELINE_STEPS = [
  { key: 'draft',          label: 'Draft' },
  { key: 'conflict-check', label: 'Konflikt' },
  { key: 'ready-for-arch', label: 'Arch review' },
  { key: 'arch-approved',  label: 'Dev plán' },
  { key: 'in-development', label: 'Vývoj' },
  { key: 'ready-for-pr',   label: 'Testing' },
  { key: 'done',           label: 'Done' },
];

const _STATUS_TO_STEP = {
  'new':             '',
  'draft':           '',
  'conflict-check':  'draft',
  'ready-for-arch':  'conflict-check',
  'validated':       'ready-for-arch',
  'in_development':      'in-development',
  'in-development':      'in-development',
  'ready_for_testing':   'in-development',
  'ready-for-testing':   'in-development',
  'ready for testing':   'in-development',
  'ready_for_review':    'in-development',
  'ready-for-review':    'in-development',
  'ready-for-pr':        'ready-for-pr',
  'done':            'done',
  'blocked':         'draft',
  'cancelled':       'done',
  // granulární -start/-finished stavy
  'draft-start':              '',
  'draft-finished':           'draft',
  'conflict-check-start':     'draft',
  'conflict-check-finished':  'conflict-check',
  'conflict-check-failed':    'draft',
  'arch-review-start':        'conflict-check',
  'arch-review-finished':     'ready-for-arch',
  'dev-plan-start':           'ready-for-arch',
  'dev-plan-finished':        'arch-approved',
  'development-start':        'arch-approved',
  'development-finish':       'in-development',
  'ready_for_testing-start':  'in-development',
  'ready_for_testing-finish': 'ready-for-pr',
};

// Stavy kde next step NEMÁ svítit modře — uživatel musí explicitně kliknout
const _STATUS_NO_NEXT_HIGHLIGHT = new Set([
  'validated', 'arch-review-finished', 'dev-plan-finished',
  'in_development', 'in-development',
  'ready_for_testing-start', 'ready_for_testing-finish',
]);

// Stavy kde konkrétní krok je červený (selhání)
const _STATUS_BLOCKED_STEP = {
  'conflict-check-failed': 'conflict-check',
  'blocked':               'conflict-check',
};

const _STATUS_DEFAULT_LABEL = {
  'draft': 'Draft uložen',
  'conflict-check': 'Kontrola konfliktů…',
  'ready-for-arch': 'Čeká na architekturu',
  'validated': 'Připraveno k implementaci',
  'in_development': 'Ve vývoji', 'in-development': 'Ve vývoji',
  'ready_for_testing': 'Připraveno k testování', 'ready-for-testing': 'Připraveno k testování',
  'ready-for-pr': 'Připraveno k PR',
  'done': 'Hotovo',
  // granulární -start/-finished stavy
  'draft-start':              'Product Owner zpracovává zadání',
  'draft-finished':           'Předáváme na konflikt check',
  'conflict-check-start':     'Kontrola konfliktů',
  'conflict-check-finished':  'Předáváme na arch review',
  'conflict-check-failed':    'Konflikty detekovány',
  'arch-review-start':        'Architekt přidává technické anotace',
  'arch-review-finished':     'Připraveno k implementaci',
  'dev-plan-start':           'Architekt vytváří plán vývoje',
  'dev-plan-finished':        'Připraveno k implementaci',
  'development-start':        'Už programuje, může to chvíli trvat',
  'development-finish':       'Předáváme k testování',
  'ready_for_testing-start':  'Připraveno k testování',
  'ready_for_testing-finish': 'Uzavíráme tiket',
};

function renderTimeline(container, storyStatus, opts) {
  if (!container) return;
  const lastSuccess = _STATUS_TO_STEP[storyStatus] || '';
  const lastIdx = _TIMELINE_STEPS.findIndex(s => s.key === lastSuccess);
  const activeStep = opts && opts.activeStep ? opts.activeStep : null;
  const errorStep = opts && opts.errorStep ? opts.errorStep : null;
  const statusLabel = opts && opts.statusLabel != null ? opts.statusLabel : (_STATUS_DEFAULT_LABEL[storyStatus] || '');
  const statusState = opts && opts.statusState ? opts.statusState : (storyStatus === 'done' ? 'done' : null);
  const activeIdx = activeStep ? _TIMELINE_STEPS.findIndex(s => s.key === activeStep) : -1;
  const errorIdx = errorStep ? _TIMELINE_STEPS.findIndex(s => s.key === errorStep) : -1;

  const fillPct = lastIdx > 0 ? Math.round(lastIdx / (_TIMELINE_STEPS.length - 1) * 100) : 0;

  const noNext = (opts && opts.noNextHighlight) || _STATUS_NO_NEXT_HIGHLIGHT.has(storyStatus);
  const steps = _TIMELINE_STEPS.map((step, idx) => {
    let cls = '';
    if (idx === errorIdx) cls = 'blocked';
    else if (idx === activeIdx) cls = 'current';
    else if (idx <= lastIdx) cls = 'done';
    else if (!noNext && activeIdx === -1 && lastIdx >= 0 && idx === lastIdx + 1) cls = 'current';
    else if (!noNext && activeIdx === -1 && lastIdx < 0 && storyStatus && storyStatus !== 'new' && idx === 0) cls = 'current';
    return '<div class="story-step ' + cls + '" data-step="' + step.key + '"><div class="story-dot"></div><div class="story-label">' + step.label + '</div></div>';
  }).join('');

  const showImplBtn = (opts && opts.showImplBtn != null)
    ? opts.showImplBtn
    : (storyStatus === 'ready-for-arch' || storyStatus === 'validated');

  let bannerHtml = '';
  if (statusLabel) {
    const stateClass = statusState ? ' ' + statusState : '';
    let iconHtml = '';
    if (statusState === 'working') {
      iconHtml = '<div class="story-status-icon"><div class="story-status-dots"><span></span><span></span><span></span></div></div>';
    } else if (statusState === 'done') {
      iconHtml = '<div class="story-status-icon"><div class="story-check-mini"><svg viewBox="0 0 10 10" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,5 4,8 8,2"/></svg></div></div>';
    } else if (statusState === 'error') {
      iconHtml = '<div class="story-status-icon"><div class="story-error-icon"><svg viewBox="0 0 10 10" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg></div></div>';
    }
    const implBtnHtml = showImplBtn
      ? '<button id="btn-run-implementation" class="btn-implementation" aria-label="Pustit implementaci">Pustit implementaci</button>'
      : '';
    bannerHtml = '<div class="story-status' + stateClass + '">' + iconHtml + '<div class="story-status-text"><span class="who">' + statusLabel + '</span></div>' + implBtnHtml + '</div>';
  }

  container.innerHTML = '<div class="story-widget"><div class="story-timeline"><div class="story-track"><div class="story-track-fill" style="width:' + fillPct + '%"></div></div>' + steps + '</div>' + bannerHtml + '</div>';
}

function renderTimelineInline(container, storyStatus) {
  if (!container) return;
  const lastSuccess = _STATUS_TO_STEP[storyStatus] || '';
  const lastIdx = _TIMELINE_STEPS.findIndex(s => s.key === lastSuccess);
  const noNext = _STATUS_NO_NEXT_HIGHLIGHT.has(storyStatus);
  const blockedKey = _STATUS_BLOCKED_STEP[storyStatus] || '';
  const blockedIdx = blockedKey ? _TIMELINE_STEPS.findIndex(s => s.key === blockedKey) : -1;

  const parts = [];
  _TIMELINE_STEPS.forEach((step, idx) => {
    if (idx > 0) parts.push('<div class="tl-conn"></div>');
    let cls = '';
    if (idx < lastIdx) cls = 'is-done';
    else if (idx === lastIdx) cls = lastIdx >= 0 ? 'is-done' : '';
    if (!noNext && lastIdx >= 0 && idx === lastIdx + 1) cls = 'is-current';
    if (!noNext && lastIdx < 0 && storyStatus && storyStatus !== 'new' && idx === 0) cls = 'is-current';
    if (blockedIdx >= 0 && idx === blockedIdx) cls = 'is-blocked';
    parts.push('<div class="tl-step ' + cls + '" data-step="' + step.key + '"><div class="tl-dot"></div><div class="tl-lbl">' + step.label + '</div></div>');
  });

  container.innerHTML = '<div class="tl">' + parts.join('') + '</div>';
}
