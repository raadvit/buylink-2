function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ── Story timeline widget ──
const _TIMELINE_STEPS = [
  { key: 'draft',           label: 'Draft' },
  { key: 'conflict-check',  label: 'Konflikt' },
  { key: 'ready-for-arch',  label: 'Arch review' },
  { key: 'arch-approved',   label: 'Dev plán' },
  { key: 'in-development',  label: 'Vývoj' },
  { key: 'ready-for-pr',    label: 'PR' },
  { key: 'done',            label: 'Done' },
];

const _STATUS_TO_STEP = {
  'draft':           'draft',
  'conflict-check':  'draft',
  'ready-for-arch':  'conflict-check',
  'validated':       'arch-approved',
  'in_development':      'in-development',
  'in-development':      'in-development',
  'ready_for_testing':   'in-development',
  'ready-for-testing':   'in-development',
  'ready for testing':   'in-development',
  'ready-for-pr':        'ready-for-pr',
  'done':            'done',
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

  const steps = _TIMELINE_STEPS.map((step, idx) => {
    let cls = '';
    if (idx === errorIdx) cls = 'blocked';
    else if (idx <= lastIdx || idx === activeIdx) cls = 'done';
    else if ((activeIdx >= 0 && idx === activeIdx + 1) || (activeIdx === -1 && lastIdx >= 0 && idx === lastIdx + 1)) cls = 'current';
    return '<div class="story-step ' + cls + '" data-step="' + step.key + '"><div class="story-dot"></div><div class="story-label">' + step.label + '</div></div>';
  }).join('');

  const showImplBtn = (storyStatus === 'ready-for-arch' || storyStatus === 'validated');

  let bannerHtml = '';
  if (statusLabel) {
    const stateClass = statusState ? ' ' + statusState : '';
    let iconHtml = '';
    if (statusState === 'working') {
      iconHtml = '<div class="story-status-icon"><div class="story-status-dots"><span></span><span></span><span></span></div></div>';
    } else if (statusState === 'done') {
      iconHtml = '<div class="story-status-icon"><div class="story-check-mini"><svg viewBox="0 0 10 10" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,5 4,8 8,2"/></svg></div></div>';
    }
    const implBtnHtml = showImplBtn
      ? '<button id="btn-run-implementation" class="btn-implementation" aria-label="Pustit implementaci">Pustit implementaci</button>'
      : '';
    bannerHtml = '<div class="story-status' + stateClass + '">' + iconHtml + '<div class="story-status-text"><span class="who">' + statusLabel + '</span></div>' + implBtnHtml + '</div>';
  }

  container.innerHTML = '<div class="story-widget"><div class="story-timeline"><div class="story-track"><div class="story-track-fill" style="width:' + fillPct + '%"></div></div>' + steps + '</div>' + bannerHtml + '</div>';
}
