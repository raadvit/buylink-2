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
  showStatus('loading', 'Ukládám draft…');
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
    enterEditMode(data.issue_url);
  } catch (err) {
    showStatus('error', 'Chyba při ukládání', err.message);
  }
}

function enterEditMode(issueUrl) {
  document.getElementById('btn-row-main').hidden = true;
  document.getElementById('btn-row-saved').hidden = false;
  showStatus('success', 'Draft uložen: <a href="' + escHtml(issueUrl) + '" target="_blank">' + escHtml(issueUrl) + '</a>');
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
  showStatus('loading', 'Ukládám změnu…');
  try {
    const formData = new FormData();
    formData.append('data', JSON.stringify({ ...buildPayload(), issue_number: _draftIssueNumber, wiki_path: _draftWikiPath }));
    _uploadedFiles.forEach(f => formData.append('files', f));
    const res = await fetch('/api/update', { method: 'POST', body: formData });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || res.status); }
    const data = await res.json();
    _uploadedFiles = [];
    _updateFileDisplay();
    showStatus('success', 'Změna uložena: <a href="' + escHtml(data.issue_url) + '" target="_blank">' + escHtml(data.issue_url) + '</a>');
  } catch (err) {
    showStatus('error', 'Chyba při ukládání změny', err.message);
  }
}

function submitSaved() {
  document.getElementById('btn-row-saved').hidden = true;
  document.getElementById('btn-row-main').hidden = false;
  _draftIssueNumber = null;
  _draftWikiPath = null;
  hideStatus();
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
  document.getElementById('f-file').value = '';
  document.getElementById('btn-row-saved').hidden = true;
  document.getElementById('btn-row-main').hidden = false;
  document.getElementById('preview-section').hidden = true;
  document.getElementById('done-section').hidden = true;
  document.getElementById('agent-msgs').innerHTML =
    '<div class="cat-waiting" id="cat-placeholder">' +
      '<dotlottie-wc src="/static/animations/cat.lottie" autoplay loop style="width:160px;height:160px"></dotlottie-wc>' +
      '<div class="cat-waiting-label">Zatím žádné dotazy</div>' +
    '</div>';
}

function newStory() {
  _resetForm();
  _clearEpicRole();
  hideStatus();
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
  showStatus('loading', 'Ukládám myšlenku…');
  try {
    const formData = new FormData();
    formData.append('data', JSON.stringify({ ...buildPayload(), type: "idea" }));
    _uploadedFiles.forEach(f => formData.append('files', f));
    const res = await fetch('/api/save', { method: 'POST', body: formData });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || res.status); }
    const data = await res.json();
    _resetForm();
    _clearEpicRole();
    showStatus('success', 'Myšlenka uložena: <a href="' + escHtml(data.issue_url) + '" target="_blank">' + escHtml(data.issue_url) + '</a>');
    document.getElementById('f-name').focus();
  } catch (err) {
    showStatus('error', 'Chyba při ukládání myšlenky', err.message);
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

// ── Sekce 2: Submit a polling ─────────────────────────────────────────────────

let _sessionId = null;
let _pollInterval = null;

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

  window.scrollTo({ top: 0, behavior: 'smooth' });
  showStatus('loading', 'Odesílám zadání agentovi…');
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
    localStorage.removeItem('us-draft');
    showStatus('loading', 'Agent zpracovává zadání…');
    showProgressBar();
    startPolling();
  } catch (err) {
    showStatus('error', 'Chyba při odesílání', err.message);
    setFormDisabled(false);
  }
}

function startPolling() {
  if (_pollInterval) clearInterval(_pollInterval);
  _pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/session?session_id=' + encodeURIComponent(_sessionId));
      if (!res.ok) throw new Error('Server odpověděl stavem ' + res.status);
      const data = await res.json();
      handleSessionData(data);
    } catch (err) {
      stopPolling();
      showStatus('error', 'Chyba při načítání stavu', err.message);
    }
  }, 2000);
}

function stopPolling() {
  if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
}

function handleSessionData(data) {
  const status = data.status;
  if (status === 'asking_questions') {
    showStatus('success', 'Agent čeká na vaše odpovědi.');
    if (Array.isArray(data.questions)) renderQuestions(data.questions);
  } else if (status === 'preview') {
    stopPolling();
    showStatus('success', 'Zkontrolujte náhled story před vytvořením issue.');
    renderPreview(data.preview);
  } else if (status === 'reviewing') {
    clearInterval(_pollInterval);
    _pollInterval = null;
    renderReview(data.review_summary, data.review_comments);
  } else if (status === 'done') {
    stopPolling();
    renderDone(data.result, data.total_tokens);
  } else if (status === 'error') {
    stopPolling();
    showStatus('error', 'Agent nahlásil chybu', data.error || 'Neznámá chyba');
  } else if (status === 'waiting_for_validation' || status === 'building') {
    showStatus('loading', 'Agent zpracovává zadání…');
  }
}

// ── Sekce 3: Agent UI ─────────────────────────────────────────────────────────

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
      '<div class="agent-msg"><span class="tag">' + escHtml(q.tag || '') + '</span>' + escHtml(q.text) + '</div>' +
      '<div class="agent-reply">' +
        '<textarea oninput="autoGrow(this)" placeholder="Vaše odpověď…"></textarea>' +
        '<button onclick="sendAnswer(' + JSON.stringify(q.id) + ', this)">Odpovědět</button>' +
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
    if (wrap) wrap.classList.add('question-answered');
    showStatus('loading', 'Odpověď odeslána, agent zpracovává…');
    if (!_pollInterval) startPolling();
  } catch (err) {
    btn.disabled = false;
    textarea.disabled = false;
    showStatus('error', 'Chyba při odesílání odpovědi', err.message);
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
  showStatus('loading', 'Vytvářím GitHub issue…');
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
    showStatus('error', 'Chyba při potvrzení', err.message);
  }
}

function renderDone(result, totalTokens) {
  setFormDisabled(false);
  document.getElementById('preview-section').hidden = true;
  if (result && result.issue_url) {
    showStatus('success', 'Story vytvořena: <a href="' + escHtml(result.issue_url) + '" target="_blank" rel="noopener">' + escHtml(result.issue_url) + '</a>');
  } else {
    showStatus('success', 'Story byla úspěšně vytvořena.');
  }
  if (_uploadedFiles.length && result && result.wiki_path) {
    const issueMatch = (result.issue_url || '').match(/\/issues\/(\d+)$/);
    const issueNumber = issueMatch ? parseInt(issueMatch[1]) : null;
    if (issueNumber) _attachFilesToStory(issueNumber, result.wiki_path, [..._uploadedFiles]);
  }
  _resetForm();
  _showDoneSection(result, totalTokens);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function _showDoneSection(result, totalTokens) {
  const section = document.getElementById('done-section');
  const content = document.getElementById('done-content');
  let html = '';
  if (result && result.issue_url) {
    html += '<a class="done-link" href="' + escHtml(result.issue_url) + '" target="_blank" rel="noopener">' + escHtml(result.issue_url) + '</a>';
  }
  if (typeof totalTokens === 'number' && totalTokens > 0) {
    html += '<span class="done-tokens">' + _formatTokens(totalTokens) + ' tokenů</span>';
  }
  content.innerHTML = html;
  section.hidden = false;
}

function _formatTokens(n) {
  if (n >= 1000) return Math.round(n / 100) / 10 + 'k';
  return String(n);
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
      '<button class="btn btn-send" style="font-size:12px;padding:.45rem .8rem" onclick="confirmReview(this)">Potvrdit vytvoření story</button>' +
      '<button class="btn btn-save" style="font-size:12px;padding:.45rem .8rem;margin-top:4px" onclick="showReviewCommentInput(this)">Odeslat dotaz</button>' +
    '</div>';
  msgs.appendChild(feedbackWrap);
}

async function confirmReview(btn) {
  const buttonsEl = document.getElementById('review-buttons');
  if (buttonsEl) {
    buttonsEl.innerHTML =
      '<div class="progress-agent" style="padding:.5rem 0">' +
        '<div class="progress-bar-wrap"><div class="progress-bar-inner"></div></div>' +
        '<div class="progress-agent-label">Vytvářím story…</div>' +
      '</div>';
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  showStatus('loading', 'Vytvářím story…');
  try {
    const res = await fetch('/api/review-confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _sessionId }),
    });
    if (!res.ok) throw new Error('Chyba serveru ' + res.status);
    startPolling();
  } catch (err) {
    showStatus('error', 'Chyba při potvrzení', err.message);
    if (buttonsEl) {
      buttonsEl.innerHTML =
        '<button class="btn btn-send" style="font-size:12px;padding:.45rem .8rem" onclick="confirmReview(this)">Potvrdit vytvoření story</button>' +
        '<button class="btn btn-save" style="font-size:12px;padding:.45rem .8rem;margin-top:4px" onclick="showReviewCommentInput(this)">Odeslat dotaz</button>';
    }
  }
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
  showStatus('loading', 'Agent zpracovává komentář…');
  try {
    const res = await fetch('/api/review-comment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: _sessionId, comment }),
    });
    if (!res.ok) throw new Error('Chyba serveru ' + res.status);
    startPolling();
  } catch (err) {
    showStatus('error', 'Chyba při odesílání komentáře', err.message);
    btn.disabled = false;
  }
}

// ── Sekce 4: Issue modal ──────────────────────────────────────────────────────

let _ghIssues = [];
let _ghFilter = 'all';
let _ghFetching = false;

async function openIssueModal() {
  if (_ghFetching) return;
  document.getElementById('ghOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  _ghFilter = 'all';
  document.querySelectorAll('.gh-filter').forEach(b => {
    b.className = 'gh-filter' + (b.id === 'gff-all' ? ' active-all' : '');
  });
  document.getElementById('ghList').innerHTML =
    '<div class="skel-row"><div class="skel" style="width:8px;height:8px;border-radius:50%"></div><div class="skel" style="flex:1;height:13px"></div></div>'.repeat(4);
  document.getElementById('ghFooter').textContent = 'Načítám…';
  _ghFetching = true;
  try {
    const res = await fetch('/api/issues');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    _ghIssues = await res.json();
    _renderGhIssues(_ghIssues);
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
  document.querySelectorAll('.gh-filter').forEach(b => {
    b.className = 'gh-filter';
    if (b.id === 'gff-' + type) b.classList.add('active-' + type);
  });
  const filtered = type === 'all' ? _ghIssues : _ghIssues.filter(i => i.type === type);
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

  closeGhModal();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  showStatus('success', 'Issue #' + id + ' načteno: ' + escHtml(issue.title));
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', loadDraft);

async function loadEurRate() {
  try {
    const res = await fetch('/api/eur-rate');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const el = document.getElementById('eur-value');
    if (!el) return;
    el.textContent = '1 EUR = ' + String(data.rate.toFixed(2)).replace('.', ',') + ' Kč';
    el.classList.remove('eur-error');
  } catch (e) {
    const el = document.getElementById('eur-value');
    if (!el) return;
    el.textContent = 'Kurz není k dispozici';
    el.classList.add('eur-error');
  }
}

document.addEventListener('DOMContentLoaded', loadEurRate);

