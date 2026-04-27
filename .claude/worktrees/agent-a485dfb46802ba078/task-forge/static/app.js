// ── Sekce 1: Formulář ────────────────────────────────────────────────────────

const required = ['name', 'epic', 'role', 'what', 'how'];

let _draftIssueNumber = null;
let _draftWikiPath = null;
let _uploadedFiles = [];

function check(id) {
  const card = document.getElementById('project-template-' + id);
  const si = document.getElementById('si-' + id);
  if (!card || !si) return;
  let filled = false;
  if (id === 'epic') filled = document.getElementById('f-epic').value !== '';
  else if (id === 'role') filled = document.querySelectorAll('#roles .chip.active').length > 0;
  else if (id === 'upload') filled = card.classList.contains('has-uploaded');
  else { const f = document.getElementById('f-' + id); if (f) filled = f.value.trim().length > 0; }
  card.classList.remove('filled', 'error');
  if (filled) { card.classList.add('filled'); si.textContent = '✓'; si.className = 'si done'; }
  else { si.textContent = ''; si.className = 'si'; }
}

function toggleChip(el, id) {
  el.classList.toggle('active');
  check(id);
}

function handleFile(input) {
  const remaining = 3 - _uploadedFiles.length;
  if (remaining <= 0) return;
  Array.from(input.files).slice(0, remaining).forEach(f => _uploadedFiles.push(f));
  input.value = '';
  _updateFileDisplay();
}

function _updateFileDisplay() {
  const dz = document.getElementById('dz');
  const label = document.getElementById('dz-label');
  const card = document.getElementById('project-template-upload');
  const si = document.getElementById('si-upload');
  if (_uploadedFiles.length === 0) {
    dz.classList.remove('has-file');
    label.textContent = 'Nahrát nebo přetáhnout';
    const existing = dz.querySelectorAll('.thumb-wrap');
    existing.forEach(el => el.remove());
    card.classList.remove('has-uploaded', 'filled');
    si.textContent = ''; si.className = 'si';
  } else {
    dz.classList.add('has-file');
    const existing = dz.querySelectorAll('.thumb-wrap');
    existing.forEach(el => el.remove());
    _uploadedFiles.forEach(file => {
      const wrap = document.createElement('div');
      wrap.className = 'thumb-wrap';
      if (file.type.startsWith('image/')) {
        const img = document.createElement('img');
        img.className = 'thumb';
        img.src = URL.createObjectURL(file);
        img.onload = () => URL.revokeObjectURL(img.src);
        wrap.appendChild(img);
      } else {
        const lbl = document.createElement('div');
        lbl.className = 'thumb-file';
        lbl.textContent = file.name.split('.').pop().toUpperCase();
        wrap.appendChild(lbl);
      }
      dz.appendChild(wrap);
    });
    const remaining = 3 - _uploadedFiles.length;
    label.textContent = remaining > 0 ? 'Lze přidat ' + remaining + ' další' : '';
    card.classList.add('has-uploaded', 'filled');
    si.textContent = '✓'; si.className = 'si done';
  }
}

function handleDrop(e) {
  e.preventDefault();
  const remaining = 3 - _uploadedFiles.length;
  if (remaining <= 0) return;
  Array.from(e.dataTransfer.files).slice(0, remaining).forEach(f => _uploadedFiles.push(f));
  _updateFileDisplay();
}

function validate() {
  let valid = true;
  required.forEach(id => {
    const card = document.getElementById('project-template-' + id);
    if (!card) return;
    let filled = false;
    if (id === 'epic') filled = document.getElementById('f-epic').value !== '';
    else if (id === 'role') filled = document.querySelectorAll('#roles .chip.active').length > 0;
    else { const f = document.getElementById('f-' + id); if (f) filled = f.value.trim().length > 0; }
    if (!filled) {
      card.classList.remove('filled');
      card.classList.add('error');
      const si = document.getElementById('si-' + id);
      if (si) { si.textContent = '!'; si.className = 'si err'; }
      valid = false;
    }
  });
  return valid;
}

function buildPayload() {
  return {
    name: document.getElementById('f-name').value.trim(),
    epic: document.getElementById('f-epic').value,
    role: Array.from(document.querySelectorAll('#roles .chip.active')).map(c => c.textContent),
    why: document.getElementById('f-why').value.trim(),
    what: document.getElementById('f-what').value.trim(),
    how: document.getElementById('f-how').value.trim(),
    scope: document.getElementById('f-scope').value.trim(),
    deps: document.getElementById('f-deps').value.trim(),
    ac: document.getElementById('f-ac').value.trim(),
  };
}

async function saveForm() {
  const name = document.getElementById('f-name').value.trim();
  if (!name) {
    const card = document.getElementById('project-template-name');
    card.classList.add('error');
    const si = document.getElementById('si-name');
    si.textContent = '!'; si.className = 'si err';
    return;
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try {
    const formData = new FormData();
    formData.append('data', JSON.stringify({ ...buildPayload(), type: "story" }));
    _uploadedFiles.forEach(f => formData.append('files', f));
    const res = await fetch('/api/save', { method: 'POST', body: formData });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || res.status); }
    const data = await res.json();
    _draftIssueNumber = data.issue_number;
    _draftWikiPath = data.wiki_path;
    _uploadedFiles = [];
    _updateFileDisplay();
    const tlWrap = document.getElementById('story-timeline-wrap');
    const tlContainer = document.getElementById('story-timeline-container');
    if (tlWrap && tlContainer) {
      renderTimeline(tlContainer, 'draft');
      tlWrap.hidden = false;
    }
    enterEditMode(data.issue_url);
  } catch (err) {
    console.error('Chyba při ukládání', err.message);
  }
}

function enterEditMode(issueUrl) {
  document.getElementById('btn-row-main').hidden = true;
  document.getElementById('btn-row-saved').hidden = false;
}

async function updateDraft() {
  const name = document.getElementById('f-name').value.trim();
  if (!name) {
    const card = document.getElementById('project-template-name');
    card.classList.add('error');
    document.getElementById('si-name').textContent = '!';
    document.getElementById('si-name').className = 'si err';
    return;
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try {
    const formData = new FormData();
    formData.append('data', JSON.stringify({ ...buildPayload(), issue_number: _draftIssueNumber, wiki_path: _draftWikiPath }));
    _uploadedFiles.forEach(f => formData.append('files', f));
    const res = await fetch('/api/update', { method: 'POST', body: formData });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || res.status); }
    const data = await res.json();
    _uploadedFiles = [];
    _updateFileDisplay();
  } catch (err) {
    console.error('Chyba při ukládání změny', err.message);
  }
}

function submitSaved() {
  document.getElementById('btn-row-saved').hidden = true;
  document.getElementById('btn-row-main').hidden = false;
  _draftIssueNumber = null;
  _draftWikiPath = null;
  submitForm();
}

function _clearEpicRole() {
  document.getElementById('f-epic').value = '';
  document.querySelectorAll('#roles .chip').forEach(c => c.classList.remove('active'));
}

function _resetForm() {
  document.getElementById('f-name').value = '';
  ['f-why','f-what','f-how','f-scope','f-deps','f-ac'].forEach(id => {
    const el = document.getElementById(id);
    el.value = '';
    el.style.height = '';
  });
  ['f-flag-ext-api','f-flag-db','f-flag-notif','f-flag-security'].forEach(id => {
    document.getElementById(id).checked = false;
  });
  ['name','epic','role','why','what','how','scope','deps','ac'].forEach(id => {
    const card = document.getElementById('project-template-' + id);
    if (card) card.classList.remove('filled','error');
    const si = document.getElementById('si-' + id);
    if (si) { si.textContent = ''; si.className = 'si'; }
  });
  _draftIssueNumber = null;
  _draftWikiPath = null;
  _uploadedFiles = [];
  _updateFileDisplay();
  sessionStorage.removeItem('active_session_id');
  const tlWrap = document.getElementById('story-timeline-wrap');
  if (tlWrap) tlWrap.hidden = true;
  document.getElementById('f-file').value = '';
  document.getElementById('btn-row-saved').hidden = true;
  document.getElementById('btn-row-main').hidden = false;
  document.getElementById('preview-section').hidden = true;
  document.getElementById('agent-msgs').innerHTML =
    '<div class="cat-waiting" id="cat-placeholder">' +
      '<dotlottie-wc src="/static/animations/cat.lottie" autoplay loop style="width:160px;height:160px"></dotlottie-wc>' +
      '<div class="cat-waiting-label">Zatím žádné dotazy</div>' +
    '</div>';
}

function newStory() {
  _resetForm();
  _clearEpicRole();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.getElementById('f-name').focus();
}

async function createIdea() {
  const nameEl = document.getElementById('f-name');
  const name = nameEl.value.trim();
  if (!name) {
    const card = document.getElementById('project-template-name');
    card.classList.add('error');
    const si = document.getElementById('si-name');
    si.textContent = '!'; si.className = 'si err';
    return;
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try {
    const formData = new FormData();
    formData.append('data', JSON.stringify({ ...buildPayload(), type: "idea" }));
    _uploadedFiles.forEach(f => formData.append('files', f));
    const res = await fetch('/api/save', { method: 'POST', body: formData });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || res.status); }
    const data = await res.json();
    _resetForm();
    _clearEpicRole();
    const tlWrap = document.getElementById('story-timeline-wrap');
    const tlContainer = document.getElementById('story-timeline-container');
    if (tlWrap && tlContainer) { renderTimeline(tlContainer, 'draft'); tlWrap.hidden = false; }
    document.getElementById('f-name').focus();
  } catch (err) {
    console.error('Chyba při ukládání myšlenky', err.message);
  }
}

function loadDraft() {
  const raw = localStorage.getItem('us-draft');
  if (!raw) return;
  try {
    const d = JSON.parse(raw);
    if (d.name) document.getElementById('f-name').value = d.name;
    if (d.epic) document.getElementById('f-epic').value = d.epic;
    if (Array.isArray(d.role)) {
      d.role.forEach(r => {
        const chip = Array.from(document.querySelectorAll('#roles .chip')).find(c => c.textContent === r);
        if (chip) chip.classList.add('active');
      });
    }
    if (d.why) { const el = document.getElementById('f-why'); el.value = d.why; autoGrow(el); }
    if (d.what) { const el = document.getElementById('f-what'); el.value = d.what; autoGrow(el); }
    if (d.how) { const el = document.getElementById('f-how'); el.value = d.how; autoGrow(el); }
    if (d.scope) { const el = document.getElementById('f-scope'); el.value = d.scope; autoGrow(el); }
    if (d.deps) { const el = document.getElementById('f-deps'); el.value = d.deps; autoGrow(el); }
    if (d.ac) { const el = document.getElementById('f-ac'); el.value = d.ac; autoGrow(el); }
    if (Array.isArray(d.flags)) {
      const flagMap = { 'ext-api': 'f-flag-ext-api', db: 'f-flag-db', notif: 'f-flag-notif', security: 'f-flag-security' };
      d.flags.forEach(f => { const el = document.getElementById(flagMap[f]); if (el) el.checked = true; });
    }
    required.forEach(id => check(id));
    check('why'); check('scope'); check('deps'); check('ac');
  } catch (e) {
    // poškozený draft v localStorage — tiše ignorovat
  }
}

function collectFlags() {
  const flags = [];
  if (document.getElementById('f-flag-ext-api').checked) flags.push('ext-api');
  if (document.getElementById('f-flag-db').checked) flags.push('db');
  if (document.getElementById('f-flag-notif').checked) flags.push('notif');
  if (document.getElementById('f-flag-security').checked) flags.push('security');
  return flags;
}

function _phaseHasConflict(data) {
  if (data.validation_phase !== 'conflict_detector') return false;
  return Array.isArray(data.review_comments) && data.review_comments.length > 0;
}

function _updateLayoutForStatus(phase) {
  const main = document.querySelector('.r-main');
  if (!main) return;
  const reversedPhases = new Set([
    'draft-start', 'draft-finished',
    'conflict-check-start', 'conflict-check-finished', 'conflict-check-failed',
    'arch-review-start', 'arch-review-finished',
    'dev-plan-start', 'dev-plan-finished',
    'development-start', 'development-finish',
    // zpětná kompatibilita
    'product_owner', 'conflict_detector', 'architect',
  ]);
  if (reversedPhases.has(phase)) {
    main.classList.add('layout-reversed');
  } else {
    main.classList.remove('layout-reversed');
  }
}

function _updateTimelineForPhase(phase, hasConflict) {
  const tlWrap = document.getElementById('story-timeline-wrap');
  const tlContainer = document.getElementById('story-timeline-container');
  if (!tlWrap || !tlContainer) return;
  tlWrap.hidden = false;
  const phaseMap = {
    // ── granulární stavy ──────────────────────────────────────────────────────
    'draft-start':             { status: 'draft-start',             activeStep: 'draft',          errorStep: null,             statusLabel: 'Product Owner zpracovává zadání',      statusState: 'working' },
    'draft-finished':          { status: 'draft-finished',          activeStep: null,             errorStep: null,             statusLabel: 'Zadání - zaseknuto',                   statusState: 'working' },
    'conflict-check-start':    { status: 'conflict-check-start',    activeStep: 'conflict-check', errorStep: null,             statusLabel: 'Kontrola konfliktů',                  statusState: 'working' },
    'conflict-check-finished': { status: 'conflict-check-finished', activeStep: null,             errorStep: null,             statusLabel: 'Konflikty - zaseknuto',              statusState: 'working' },
    'conflict-check-failed':   { status: 'conflict-check-failed',   activeStep: null,             errorStep: 'conflict-check', statusLabel: 'Konflikty detekovány',                 statusState: 'error',   noNextHighlight: true },
    'arch-review-start':       { status: 'arch-review-start',       activeStep: 'ready-for-arch', errorStep: null,             statusLabel: 'Architekt přidává technické anotace', statusState: 'working' },
    'arch-review-finished':    { status: 'arch-review-finished',    activeStep: null,             errorStep: null,             statusLabel: 'Arch review - zaseknuto',            statusState: null,      showImplBtn: true },
    'dev-plan-start':          { status: 'dev-plan-start',          activeStep: 'arch-approved',  errorStep: null,             statusLabel: 'Architekt vytváří plán vývoje',        statusState: 'working' },
    'dev-plan-finished':       { status: 'dev-plan-finished',       activeStep: null,             errorStep: null,             statusLabel: 'Připraveno k implementaci',            statusState: 'working', showImplBtn: !!window._implPlanInAnalysis },
    'development-start':       { status: 'development-start',       activeStep: 'in-development', errorStep: null,             statusLabel: 'Už programuje, může to chvíli trvat', statusState: 'working' },
    'development-finish':      { status: 'development-finish',      activeStep: null,             errorStep: null,             statusLabel: 'Development - zaseknuto',                statusState: 'working' },
    'ready_for_testing-start': { status: 'ready_for_testing-start', activeStep: null,             errorStep: null,             statusLabel: 'Připraveno k testování',               statusState: null,      noNextHighlight: true },
    'ready_for_testing-finish':{ status: 'ready_for_testing-finish',activeStep: null,             errorStep: null,             statusLabel: 'Uzavíráme tiket',                      statusState: 'working' },
    'done':                    { status: 'done',                    activeStep: null,             errorStep: null,             statusLabel: 'Hotovo',                               statusState: 'done' },
    // ── zpětná kompatibilita — staré klíče ────────────────────────────────────
    'product_owner':     { status: 'draft-start',          activeStep: 'draft',          errorStep: null,                                    statusLabel: 'Product Owner zpracovává zadání',         statusState: 'working' },
    'conflict_detector': { status: 'conflict-check-start', activeStep: 'conflict-check', errorStep: hasConflict ? 'conflict-check' : null,   statusLabel: hasConflict ? 'Konflikty detekováno' : 'Kontrola konfliktů…', statusState: hasConflict ? 'error' : 'working', noNextHighlight: hasConflict },
    'architect':         { status: 'arch-review-start',    activeStep: 'ready-for-arch', errorStep: null,                                    statusLabel: 'Architekt přidává technické anotace',    statusState: 'working' },
  };
  const cfg = phaseMap[phase];
  if (!cfg) return;
  const showImplBtn = cfg.showImplBtn != null
    ? cfg.showImplBtn
    : (cfg.showImplBtn === false ? false : undefined);
  renderTimeline(tlContainer, cfg.status, {
    activeStep: cfg.activeStep,
    errorStep: cfg.errorStep,
    statusLabel: cfg.statusLabel,
    statusState: cfg.statusState,
    noNextHighlight: cfg.noNextHighlight || false,
    showImplBtn: cfg.showImplBtn != null ? cfg.showImplBtn : undefined,
  });
  _updateLayoutForStatus(phase);
}

// ── Sekce 2: Submit a polling ─────────────────────────────────────────────────

let _sessionId = null;
let _pollInterval = null;
let _pollDeadline = null;

function setFormDisabled(disabled) {
  const inputs = document.querySelectorAll('#f-name,#f-epic,#f-why,#f-what,#f-how,#f-scope,#f-deps,#f-ac,#f-file');
  inputs.forEach(el => el.disabled = disabled);
  document.querySelectorAll('#roles .chip').forEach(c => {
    c.style.pointerEvents = disabled ? 'none' : '';
    c.style.opacity = disabled ? '0.5' : '';
  });
  document.querySelectorAll('.btn-save,.btn-send').forEach(b => b.disabled = disabled);
}

async function submitForm() {
  if (!validate()) return;

  const payload = { ...buildPayload(), flags: collectFlags() };
  if (_draftIssueNumber) payload.issue_number = _draftIssueNumber;
  if (_draftWikiPath) payload.wiki_path = _draftWikiPath;

  window.scrollTo({ top: 0, behavior: 'smooth' });
  setFormDisabled(true);

  try {
    const res = await fetch('/api/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
    const data = await res.json();
    _sessionId = data.session_id;
    if (data.issue_number) { _draftIssueNumber = data.issue_number; _draftWikiPath = data.wiki_path; }
    localStorage.removeItem('us-draft');
    showProgressBar();
    startPolling();
    sessionStorage.setItem('active_session_id', _sessionId);
    _updateTimelineForPhase('product_owner', false);
  } catch (err) {
    console.error('Chyba při odesílání', err.message);
    setFormDisabled(false);
  }
}

function startPolling() {
  if (_pollInterval) clearInterval(_pollInterval);
  _pollDeadline = Date.now() + 10 * 60 * 1000; // max 10 minut
  _pollInterval = setInterval(async () => {
    if (Date.now() > _pollDeadline) {
      stopPolling();
      setFormDisabled(false);
      return;
    }
    try {
      const res = await fetch('/api/session?session_id=' + encodeURIComponent(_sessionId));
      if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
      const data = await res.json();
      handleSessionData(data);
    } catch (err) {
      stopPolling();
      console.error('Chyba při načítání stavu', err.message);
      setFormDisabled(false);
    }
  }, 2000);
}

function stopPolling() {
  if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
}

function handleSessionData(data) {
  if (data.impl_plan_in_analysis !== undefined) {
    window._implPlanInAnalysis = data.impl_plan_in_analysis;
  }
  const status = data.status;
  if (status === 'asking_questions') {
    if (Array.isArray(data.questions)) renderQuestions(data.questions);
    if (data.validation_phase) _updateTimelineForPhase(data.validation_phase, _phaseHasConflict(data));
  } else if (status === 'preview') {
    stopPolling();
    renderPreview(data.preview);
  } else if (status === 'reviewing') {
    if (data.validation_phase && data.validation_phase !== 'done') {
      document.querySelectorAll('.agent-q-wrap').forEach(el => el.remove());
      showProgressBar();
      updateProgressLabel(data.review_summary);
      _updateTimelineForPhase(data.validation_phase, _phaseHasConflict(data));
    } else {
      clearInterval(_pollInterval);
      _pollInterval = null;
      _updateTimelineForPhase('done', false);
      renderReview(data.review_summary, data.review_comments);
    }
  } else if (status === 'in_development') {
    if (data.validation_phase) _updateTimelineForPhase(data.validation_phase, false);
  } else if (status === 'done') {
    stopPolling();
    if (data.validation_phase === 'ready_for_testing-start') {
      _updateTimelineForPhase('ready_for_testing-start', false);
      const progressEl = document.getElementById('agent-progress');
      if (progressEl) progressEl.remove();
    } else {
      _updateTimelineForPhase('done', false);
      renderDone(data.result, data.total_cost_usd);
    }
  } else if (status === 'error') {
    stopPolling();
    sessionStorage.removeItem('active_session_id');
    setFormDisabled(false);
  } else if (status === 'building') {
    _updateTimelineForPhase('done', false);
  }
}

// ── Sekce 3: Agent UI ─────────────────────────────────────────────────────────

function updateProgressLabel(text) {
  const el = document.getElementById('agent-progress');
  if (el) {
    const label = el.querySelector('.progress-agent-label');
    if (label && text) label.textContent = text;
  }
}

function showProgressBar() {
  const msgs = document.getElementById('agent-msgs');
  const placeholder = msgs.querySelector('.cat-waiting, .progress-agent');
  if (placeholder) placeholder.remove();
  const el = document.createElement('div');
  el.className = 'progress-agent';
  el.id = 'agent-progress';
  el.innerHTML =
    '<div class="progress-bar-wrap"><div class="progress-bar-inner"></div></div>' +
    '<div class="progress-agent-label">Agenti pracují…</div>';
  msgs.insertBefore(el, msgs.firstChild);
}

function renderQuestions(questions) {
  const msgs = document.getElementById('agent-msgs');
  questions.forEach(q => {
    if (document.getElementById('aq-' + q.id)) return;
    const empty = msgs.querySelector('.cat-waiting, .empty-agent, .progress-agent');
    if (empty) empty.remove();
    const wrap = document.createElement('div');
    wrap.className = 'agent-q-wrap';
    wrap.id = 'aq-' + q.id;
    wrap.innerHTML =
      '<div class="agent-msg"><span class="tag">' + escHtml(q.agent || '') + '</span>' + escHtml(q.text) + '</div>' +
      '<div class="agent-reply">' +
        '<textarea oninput="autoGrow(this)" placeholder="Vaše odpověď…"></textarea>' +
        "<button onclick=\"sendAnswer('" + q.id + "', this)\">Odpovědět</button>" +
      '</div>';
    msgs.appendChild(wrap);
  });
}

async function sendAnswer(id, btn) {
  const textarea = btn.previousElementSibling;
  const answer = textarea.value.trim();
  if (!answer) return;

  btn.disabled = true;
  textarea.disabled = true;

  try {
    const res = await fetch('/api/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _sessionId, question_id: id, answer }),
    });
    if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
    const wrap = document.getElementById('aq-' + id);
    if (wrap) wrap.remove();
    const remaining = document.querySelectorAll('.agent-q-wrap').length;
    if (remaining === 0) showProgressBar();
    if (!_pollInterval) startPolling();
  } catch (err) {
    btn.disabled = false;
    textarea.disabled = false;
    console.error('Chyba při odesílání odpovědi', err.message);
  }
}

function renderPreview(preview) {
  const section = document.getElementById('preview-section');
  const pre = document.getElementById('preview-content');
  pre.textContent = preview.body;
  section.hidden = false;
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function confirmPreview() {
  document.querySelector('.btn-confirm').disabled = true;
  try {
    const res = await fetch('/api/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _sessionId }),
    });
    if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
    startPolling();
  } catch (err) {
    document.querySelector('.btn-confirm').disabled = false;
    console.error('Chyba při potvrzení', err.message);
  }
}

function renderDone(result, totalCostUsd) {
  setFormDisabled(false);
  document.getElementById('preview-section').hidden = true;
  if (_uploadedFiles.length && result && result.wiki_path) {
    const issueMatch = (result.issue_url || '').match(/\/issues\/(\d+)$/);
    const issueNumber = issueMatch ? parseInt(issueMatch[1]) : null;
    if (issueNumber) _attachFilesToStory(issueNumber, result.wiki_path, [..._uploadedFiles]);
  }
  _resetForm();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function _attachFilesToStory(issueNumber, wikiPath, files) {
  const fd = new FormData();
  fd.append('data', JSON.stringify({ issue_number: issueNumber, wiki_path: wikiPath }));
  files.forEach(f => fd.append('files', f));
  try {
    const res = await fetch('/api/attach', { method: 'POST', body: fd });
    if (!res.ok) console.warn('[attach] Přílohy se nepodařilo uložit ke story (HTTP ' + res.status + ').');
  } catch (e) {
    console.warn('[attach] Přílohy se nepodařilo uložit ke story.', e);
  }
}

function renderReview(summary, comments) {
  window.scrollTo({ top: 0, behavior: 'smooth' });
  const msgs = document.getElementById('agent-msgs');
  const placeholder = document.getElementById('cat-placeholder');
  if (placeholder) placeholder.remove();
  msgs.innerHTML = '';

  const reviewSummary = summary || 'Vše vypadá skvěle, mám vytvořit storku nebo ještě něco máš?';

  (comments || []).forEach(c => {
    if (c.text) {
      const userWrap = document.createElement('div');
      userWrap.className = 'agent-q-wrap';
      userWrap.innerHTML = '<div class="agent-msg"><span class="tag">Tvůj dotaz</span>' + escHtml(c.text) + '</div>';
      msgs.appendChild(userWrap);
    }
    if (c.reply) {
      const replyWrap = document.createElement('div');
      replyWrap.className = 'agent-q-wrap';
      replyWrap.innerHTML = '<div class="agent-msg"><span class="tag">Agent</span>' + escHtml(c.reply) + '</div>';
      msgs.appendChild(replyWrap);
    }
  });

  const feedbackWrap = document.createElement('div');
  feedbackWrap.className = 'agent-q-wrap';
  feedbackWrap.id = 'review-feedback-wrap';
  feedbackWrap.innerHTML =
    '<div class="agent-msg"><span class="tag">Agent</span>' + escHtml(reviewSummary) + '</div>' +
    '<div class="agent-reply" id="review-buttons">' +
      '<button class="btn btn-save" style="font-size:12px;padding:.45rem .8rem" onclick="showReviewCommentInput(this)">Odeslat dotaz</button>' +
    '</div>';
  msgs.appendChild(feedbackWrap);
}


function showReviewCommentInput(btn) {
  const buttons = document.getElementById('review-buttons');
  buttons.innerHTML =
    '<textarea id="review-comment-ta" style="font-size:12px;min-height:52px;width:100%;margin-bottom:4px" placeholder="Napiš dotaz nebo komentář…"></textarea>' +
    '<button onclick="submitReviewComment(this)" style="align-self:flex-end;font-size:11px;padding:3px 10px;border-radius:6px;border:0.5px solid #e0e0e0;background:#fff;cursor:pointer;font-family:inherit">Odeslat</button>';
  document.getElementById('review-comment-ta').focus();
}

async function submitReviewComment(btn) {
  const ta = document.getElementById('review-comment-ta');
  const comment = ta ? ta.value.trim() : '';
  if (!comment) return;
  btn.disabled = true;
  try {
    const res = await fetch('/api/review-comment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _sessionId, comment }),
    });
    if (!res.ok) throw new Error('Chyba serveru ' + res.status);
    startPolling();
  } catch (err) {
    console.error('Chyba při odesílání komentáře', err.message);
    btn.disabled = false;
  }
}

// ── Sekce 4: Issue modal ──────────────────────────────────────────────────────

let _ghIssues = [];
let _ghFilter = 'all';
let _ghReadyFilter = localStorage.getItem('gh-status-filter') === 'ready';
let _ghFetching = false;

async function openIssueModal() {
  if (_ghFetching) return;
  document.getElementById('ghOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  _ghFilter = 'all';
  _ghReadyFilter = localStorage.getItem('gh-status-filter') === 'ready';
  document.querySelectorAll('.gh-filter').forEach(b => {
    b.className = 'gh-filter' + (b.id === 'gff-all' ? ' active-all' : '');
  });
  const readyBtn = document.getElementById('gff-ready');
  if (readyBtn) {
    if (_ghReadyFilter) {
      readyBtn.classList.add('active-ready');
      readyBtn.setAttribute('aria-pressed', 'true');
    } else {
      readyBtn.setAttribute('aria-pressed', 'false');
    }
  }
  document.getElementById('ghList').innerHTML =
    '<div class="skel-row"><div class="skel" style="width:8px;height:8px;border-radius:50%"></div><div class="skel" style="flex:1;height:13px"></div></div>'.repeat(4);
  document.getElementById('ghFooter').textContent = 'Načítám…';
  _ghFetching = true;
  try {
    const res = await fetch('/api/issues');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    _ghIssues = await res.json();
    _applyGhFilters();
  } catch (err) {
    document.getElementById('ghList').innerHTML = '<div class="gh-empty">Nepodařilo se načíst issues: ' + escHtml(err.message) + '</div>';
    document.getElementById('ghFooter').textContent = 'Chyba';
  } finally {
    _ghFetching = false;
  }
}

function closeGhModal() {
  document.getElementById('ghOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

function handleOverlayClick(e) {
  if (e.target === document.getElementById('ghOverlay')) closeGhModal();
}

function setGhFilter(type, btn) {
  _ghFilter = type;
  document.querySelectorAll('.gh-filter:not(#gff-ready)').forEach(b => {
    b.className = 'gh-filter';
    if (b.id === 'gff-' + type) b.classList.add('active-' + type);
  });
  _applyGhFilters();
}

function setReadyFilter(btn) {
  _ghReadyFilter = !_ghReadyFilter;
  if (_ghReadyFilter) {
    localStorage.setItem('gh-status-filter', 'ready');
    btn.classList.add('active-ready');
    btn.setAttribute('aria-pressed', 'true');
  } else {
    localStorage.removeItem('gh-status-filter');
    btn.classList.remove('active-ready');
    btn.setAttribute('aria-pressed', 'false');
  }
  _applyGhFilters();
}

function _applyGhFilters() {
  let filtered = _ghFilter === 'all' ? _ghIssues : _ghIssues.filter(i => i.type === _ghFilter);
  if (_ghReadyFilter) {
    filtered = filtered.filter(i =>
      (Array.isArray(i.labels) && i.labels.some(l => ['ready for testing', 'ready-for-testing', 'ready_for_testing'].includes(l))) ||
      ['ready_for_testing', 'ready-for-testing', 'ready for testing'].includes(i.story_status)
    );
  }
  _renderGhIssues(filtered);
}

function _renderGhIssues(items) {
  const list = document.getElementById('ghList');
  const footer = document.getElementById('ghFooter');
  footer.textContent = items.length + ' issues';
  const labelMap = { idea: 'idea', story: 'user story', bug: 'bug', other: 'other' };
  if (!items.length) {
    list.innerHTML = '<div class="gh-empty">Žádné issues neodpovídají filtru</div>';
    return;
  }
  list.innerHTML = items.map(i =>
    '<div class="gh-item" onclick="selectGhIssue(' + i.id + ')">' +
      '<span class="gh-dot ' + escHtml(i.type) + '"></span>' +
      '<div class="gh-item-body">' +
        '<div class="gh-item-title">#' + i.id + ' ' + escHtml(i.title) + '</div>' +
        '<div class="gh-item-meta">' +
          '<span class="gh-badge ' + escHtml(i.type) + '">' + escHtml(labelMap[i.type] || i.type) + '</span>' +
          '<span>' + escHtml(i.epic) + '</span>' +
          '<span style="margin-left:auto">' + escHtml(i.date) + '</span>' +
        '</div>' +
      '</div>' +
      '<span class="gh-arrow">›</span>' +
    '</div>'
  ).join('');
}

function selectGhIssue(id) {
  const issue = _ghIssues.find(i => i.id === id);
  if (!issue) return;

  if (issue.type === 'bug') {
    sessionStorage.setItem('gh-issue-prefill', JSON.stringify(issue));
    closeGhModal();
    window.location.href = '/bug/new';
    return;
  }

  document.getElementById('f-name').value = issue.title;
  check('name');

  const epicEl = document.getElementById('f-epic');
  for (const opt of epicEl.options) {
    if (issue.epic && (opt.text === issue.epic || opt.text.startsWith(issue.epic.split(' ')[0]))) {
      epicEl.value = opt.value;
      break;
    }
  }
  check('epic');

  const body = (issue.body || '').replace(/\r\n/g, '\n');

  const roleMatch = body.match(/- Role:\s*(.+)/);
  if (roleMatch) {
    const roles = roleMatch[1].split(/[,\s]+/).map(r => r.trim().toLowerCase()).filter(Boolean);
    document.querySelectorAll('#roles .chip').forEach(c => {
      c.classList.toggle('active', roles.includes(c.textContent.trim().toLowerCase()));
    });
    check('role');
  }

  const sections = {
    why:   /## Why \/ Business Goal\n([\s\S]*?)(?=\n##|$)/,
    what:  /## Co se zobrazuje\n([\s\S]*?)(?=\n##|$)/,
    how:   /## Jak se to chová\n([\s\S]*?)(?=\n##|$)/,
    scope: /## Rizikové situace\n([\s\S]*?)(?=\n##|$)/,
    deps:  /## Otevřené otázky\n([\s\S]*?)(?=\n##|$)/,
    ac:    /## Acceptance criteria\n([\s\S]*?)(?=\n##|$)/,
  };
  for (const [field, re] of Object.entries(sections)) {
    const m = body.match(re);
    const el = document.getElementById('f-' + field);
    if (el) {
      el.value = m ? m[1].trim() : '';
      autoGrow(el);
      check(field);
    }
  }

  _draftIssueNumber = issue.id;
  _draftWikiPath = issue.wiki_path;
  document.getElementById('btn-row-main').hidden = true;
  document.getElementById('btn-row-saved').hidden = false;

  const tlWrap = document.getElementById('story-timeline-wrap');
  const tlContainer = document.getElementById('story-timeline-container');
  if (issue.story_status && tlWrap && tlContainer) {
    renderTimeline(tlContainer, issue.story_status);
    tlWrap.hidden = false;
  } else if (tlWrap) {
    tlWrap.hidden = true;
  }

  closeGhModal();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}


// ── Sekce 5: Implementace ─────────────────────────────────────────────────────

let _implDisabled = false;

function _bindImplButton() {
  const btn = document.getElementById('btn-run-implementation');
  if (!btn) return;
  if (_implDisabled) {
    btn.disabled = true;
    btn.style.cursor = 'not-allowed';
    btn.style.opacity = '0.5';
  }
  btn.addEventListener('click', _onImplClick, { once: true });
}

async function _onImplClick() {
  if (_implDisabled) return;
  _implDisabled = true;

  const btn = document.getElementById('btn-run-implementation');
  if (btn) {
    btn.disabled = true;
    btn.style.cursor = 'not-allowed';
    btn.style.opacity = '0.5';
  }

  // Skrýt případnou předchozí inline chybu
  const existingErr = document.getElementById('impl-error-msg');
  if (existingErr) existingErr.remove();

  showProgressBar();
  updateProgressLabel('Programátoři pracují na implementaci');

  try {
    const res = await fetch('/api/implement', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ story_id: _draftIssueNumber, issue_number: _draftIssueNumber }),
    });
    if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
    const data = await res.json();
    if (data.session_id) {
      _sessionId = data.session_id;
      sessionStorage.setItem('active_session_id', _sessionId);
      _updateTimelineForPhase('development-start', false);
      startPolling();
    }
  } catch (err) {
    console.error('Chyba při spuštění implementace', err.message);
    const tlWrap = document.getElementById('story-timeline-wrap');
    if (tlWrap) {
      const errEl = document.createElement('div');
      errEl.id = 'impl-error-msg';
      errEl.className = 'impl-error';
      errEl.textContent = 'Nepodařilo se spustit implementaci: ' + err.message;
      tlWrap.insertAdjacentElement('afterend', errEl);
    }
  }
}

// ── Sekce 6: Načtení issue z /list ────────────────────────────────────────────

function _loadGhIssueFromList() {
  const raw = localStorage.getItem('gh-issue-load');
  if (!raw) return;
  localStorage.removeItem('gh-issue-load');
  try {
    const issue = JSON.parse(raw);
    if (!issue || typeof issue !== 'object') return;

    document.getElementById('f-name').value = issue.title || '';
    check('name');

    const epicEl = document.getElementById('f-epic');
    if (issue.epic) {
      for (const opt of epicEl.options) {
        if (opt.text === issue.epic || opt.text.startsWith(issue.epic.split(' ')[0])) {
          epicEl.value = opt.value;
          break;
        }
      }
    }
    check('epic');

    const body = (issue.body || '').replace(/\r\n/g, '\n');
    const roleMatch = body.match(/- Role:\s*(.+)/);
    if (roleMatch) {
      const roles = roleMatch[1].split(/[,\s]+/).map(r => r.trim().toLowerCase()).filter(Boolean);
      document.querySelectorAll('#roles .chip').forEach(c => {
        c.classList.toggle('active', roles.includes(c.textContent.trim().toLowerCase()));
      });
      check('role');
    }

    const sections = {
      why:   /## Why \/ Business Goal\n([\s\S]*?)(?=\n##|$)/,
      what:  /## Co se zobrazuje\n([\s\S]*?)(?=\n##|$)/,
      how:   /## Jak se to chová\n([\s\S]*?)(?=\n##|$)/,
      scope: /## Rizikové situace\n([\s\S]*?)(?=\n##|$)/,
      deps:  /## Otevřené otázky\n([\s\S]*?)(?=\n##|$)/,
      ac:    /## Acceptance criteria\n([\s\S]*?)(?=\n##|$)/,
    };
    for (const [field, re] of Object.entries(sections)) {
      const m = body.match(re);
      const el = document.getElementById('f-' + field);
      if (el) {
        el.value = m ? m[1].trim() : '';
        autoGrow(el);
        check(field);
      }
    }

    _draftIssueNumber = issue.id;
    _draftWikiPath = issue.wiki_path;
    document.getElementById('btn-row-main').hidden = true;
    document.getElementById('btn-row-saved').hidden = false;

    const tlWrap = document.getElementById('story-timeline-wrap');
    const tlContainer = document.getElementById('story-timeline-container');
    if (issue.story_status && tlWrap && tlContainer) {
      renderTimeline(tlContainer, issue.story_status);
      tlWrap.hidden = false;
    } else if (tlWrap) {
      tlWrap.hidden = true;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (e) {
    // poškozená data — tiše ignorovat
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', loadDraft);
document.addEventListener('DOMContentLoaded', _loadGhIssueFromList);

document.addEventListener('DOMContentLoaded', () => {
  const savedSession = sessionStorage.getItem('active_session_id');
  if (savedSession) {
    _sessionId = savedSession;
    startPolling();
  }
});

// Napojení tlačítka implementace po každém překreslení timeline
const _origRenderTimeline = typeof renderTimeline === 'function' ? renderTimeline : null;
document.addEventListener('DOMContentLoaded', () => {
  const tlContainer = document.getElementById('story-timeline-container');
  if (!tlContainer) return;
  const observer = new MutationObserver(() => _bindImplButton());
  observer.observe(tlContainer, { childList: true, subtree: false });
});


