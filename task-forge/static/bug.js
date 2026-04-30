// ── Bug formulář ─────────────────────────────────────────────────────────────

const _bugUploadedFiles = [];

// ── Auto-grow ────────────────────────────────────────────────────────────────
function _bugAutoGrow(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ── Fill indicators ──────────────────────────────────────────────────────────
function _bugUpdateSi(id, filled) {
  const si = document.getElementById('si-' + id);
  if (!si) return;
  si.textContent = filled ? '✓' : '';
  si.className = 'si' + (filled ? ' done' : '');
}

function _bugCheckField(fieldId, wrapperId) {
  const el = document.getElementById(fieldId);
  const filled = el ? el.value.trim().length > 0 : false;
  _bugUpdateSi(fieldId.replace('f-', '').replace('-', '_'), filled);
  const fw = document.getElementById(wrapperId);
  if (fw) fw.classList.toggle('tf-field--filled', filled);
  return filled;
}

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Textareas — auto-grow + fill indicator
  const textareas = [
    { id: 'f-what-happened', fw: 'fw-what-happened' },
    { id: 'f-expected',      fw: 'fw-expected' },
    { id: 'f-steps',         fw: 'fw-steps' },
    { id: 'f-details',       fw: 'fw-details' },
  ];
  textareas.forEach(({ id, fw }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => { _bugAutoGrow(el); _bugCheckField(id, fw); });
    _bugAutoGrow(el);
  });

  // Title
  const nameEl = document.getElementById('f-name');
  if (nameEl) {
    nameEl.addEventListener('input', () => {
      const filled = nameEl.value.trim().length > 0;
      nameEl.style.borderColor = '';
      nameEl.style.boxShadow = '';
    });
  }

  // Epic input + fill indicator
  const epicEl = document.getElementById('f-epic');
  if (epicEl) {
    epicEl.addEventListener('input', () => _bugCheckField('f-epic', 'fw-epic'));
    _bugCheckField('f-epic', 'fw-epic');
  }

  // Role — init fill state for pre-selected chips
  const roleFw = document.getElementById('fw-role');
  if (roleFw) roleFw.classList.toggle('tf-field--filled', !!document.querySelector('#roles .tf-chip.on'));

  // Chips — role
  document.querySelectorAll('#roles .tf-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.classList.toggle('on');
      const filled = !!document.querySelector('#roles .tf-chip.on');
      const fw = document.getElementById('fw-role');
      if (fw) fw.classList.toggle('tf-field--filled', filled);
    });
  });

  // Attachment dropzone
  const dz = document.getElementById('bug-dz');
  const dzLabel = document.getElementById('bug-dz-label');
  const fileInput = document.getElementById('bug-f-file');

  function addFiles(files) {
    const remaining = 3 - _bugUploadedFiles.length;
    Array.from(files).slice(0, remaining).forEach(f => _bugUploadedFiles.push(f));
    updateDz();
  }

  function updateDz() {
    if (!dz) return;
    dz.querySelectorAll('.thumb-wrap').forEach(e => e.remove());
    if (_bugUploadedFiles.length === 0) {
      dz.classList.remove('has-file');
      if (dzLabel) dzLabel.textContent = 'Nahrát nebo přetáhnout';
    } else {
      dz.classList.add('has-file');
      _bugUploadedFiles.forEach(file => {
        const wrap = document.createElement('div');
        wrap.className = 'thumb-wrap';
        if (file.type.startsWith('image/')) {
          const img = document.createElement('img');
          img.className = 'thumb'; img.src = URL.createObjectURL(file);
          wrap.appendChild(img);
        } else {
          const lbl = document.createElement('div');
          lbl.className = 'thumb-file';
          lbl.textContent = file.name.split('.').pop().toUpperCase();
          wrap.appendChild(lbl);
        }
        dz.appendChild(wrap);
      });
      if (dzLabel) dzLabel.textContent = _bugUploadedFiles.length < 3 ? `+ přidat (${3 - _bugUploadedFiles.length} zbývá)` : '';
    }
  }

  if (dz && fileInput) {
    dz.addEventListener('click', () => fileInput.click());
    dz.addEventListener('dragover', e => e.preventDefault());
    dz.addEventListener('drop', e => { e.preventDefault(); addFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });
  }

  // Load epics for datalist
  fetch('/api/issues')
    .then(r => r.json())
    .then(issues => {
      const epics = [...new Set(issues.map(i => i.epic).filter(Boolean))];
      const dl = document.getElementById('bug-epic-suggestions');
      if (dl) dl.innerHTML = epics.map(e => `<option value="${e}">`).join('');
    })
    .catch(() => {});

  // Buttons
  document.getElementById('btn-submit')  ?.addEventListener('click', submitBug);
  document.getElementById('btn-new')     ?.addEventListener('click', newBug);
  document.getElementById('btn-duplicate')?.addEventListener('click', duplicateBug);

  // Prefill from sessionStorage
  _prefillNewBug();
  _prefillDuplicate();
  _prefillFromIssue();
});

// ── Validation ───────────────────────────────────────────────────────────────
function _bugValidate() {
  let valid = true;
  let first = null;

  function require(fwId, getValue) {
    const fw = document.getElementById(fwId);
    const ok = !!getValue();
    if (fw) fw.classList.toggle('tf-field--error', !ok);
    if (!ok && !first) first = fw;
    if (!ok) valid = false;
  }

  // Title — special (no fw wrapper)
  const nameEl = document.getElementById('f-name');
  const nameOk = nameEl?.value.trim();
  if (nameEl) {
    nameEl.style.borderColor = nameOk ? '' : 'var(--danger)';
    nameEl.style.boxShadow   = nameOk ? '' : '0 0 0 3px var(--danger-2)';
    if (!nameOk && !first) first = nameEl;
    if (!nameOk) valid = false;
  }

  require('fw-what-happened', () => document.getElementById('f-what-happened')?.value.trim());
  require('fw-expected',      () => document.getElementById('f-expected')?.value.trim());
  require('fw-epic',          () => document.getElementById('f-epic')?.value.trim());
  require('fw-role',          () => document.querySelector('#roles .tf-chip.on'));

  if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return valid;
}

// ── Submit ───────────────────────────────────────────────────────────────────
async function submitBug() {
  if (!_bugValidate()) return;

  const payload = {
    name:          document.getElementById('f-name').value.trim(),
    epic:          document.getElementById('f-epic').value.trim(),
    role:          [...document.querySelectorAll('#roles .tf-chip.on')].map(c => c.dataset.role).join(', '),
    what_happened: document.getElementById('f-what-happened').value.trim(),
    expected:      document.getElementById('f-expected').value.trim(),
    steps:         document.getElementById('f-steps')?.value.trim() || '',
    details:       document.getElementById('f-details')?.value.trim() || '',
  };

  _bugSetStatus('Vytvářím issue…');
  document.getElementById('btn-submit').disabled = true;

  try {
    const fd = new FormData();
    fd.append('data', JSON.stringify(payload));
    _bugUploadedFiles.forEach(f => fd.append('files', f));
    const res = await fetch('/api/submit-bug', { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || res.status);
    _bugSetStatus('Hotovo');
    if (json.issue_number) {
      window.location = `/bug-${json.issue_number}`;
    } else {
      _bugAddChat('✓ Bug issue vytvořen: ' + (json.issue_url || ''));
    }
  } catch (e) {
    _bugAddChat('Chyba: ' + e.message);
    _bugSetStatus('Chyba');
    document.getElementById('btn-submit').disabled = false;
  }
}

// ── New bug ──────────────────────────────────────────────────────────────────
function newBug() {
  ['f-name', 'f-epic', 'f-what-happened', 'f-expected', 'f-steps', 'f-details'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = ''; el.style.height = ''; el.style.borderColor = ''; el.style.boxShadow = ''; }
  });
  document.querySelectorAll('#roles .tf-chip').forEach(c => c.classList.remove('on'));
  document.querySelectorAll('.tf-field--error, .tf-field--filled').forEach(el => {
    el.classList.remove('tf-field--error', 'tf-field--filled');
  });
  document.querySelectorAll('.si').forEach(el => { el.textContent = ''; el.className = 'si'; });
  _bugUploadedFiles.length = 0;
  const dz = document.getElementById('bug-dz');
  if (dz) { dz.classList.remove('has-file'); dz.querySelectorAll('.thumb-wrap').forEach(e => e.remove()); }
  const dzLabel = document.getElementById('bug-dz-label');
  if (dzLabel) dzLabel.textContent = 'Nahrát nebo přetáhnout';
  document.getElementById('btn-submit').disabled = false;
  _bugSetStatus('Připraveno k odeslání');
  document.getElementById('f-name')?.focus();
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _bugSetStatus(text) {
  const el = document.getElementById('bug-agent-status');
  if (el) el.textContent = text;
}

function _bugAddChat(text) {
  const chat = document.getElementById('bugChat');
  if (!chat) return;
  const div = document.createElement('div');
  div.className = 'cs-msg agent';
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

// ── Prefill nového bugu z verify flow ────────────────────────────────────────
function _prefillNewBug() {
  const raw = sessionStorage.getItem('tf-new-bug');
  if (!raw) return;
  sessionStorage.removeItem('tf-new-bug');
  let d;
  try { d = JSON.parse(raw); } catch { return; }
  const nameEl = document.getElementById('f-name');
  if (nameEl && d.name) { nameEl.value = d.name; nameEl.focus(); }
  if (d.epic) {
    const epicEl = document.getElementById('f-epic');
    if (epicEl) { epicEl.value = d.epic; _bugCheckField('f-epic', 'fw-epic'); }
  }
  if (Array.isArray(d.roles) && d.roles.length > 0) {
    document.querySelectorAll('#roles .tf-chip').forEach(c => {
      c.classList.toggle('on', d.roles.includes(c.dataset.role));
    });
    const fw = document.getElementById('fw-role');
    if (fw) fw.classList.toggle('tf-field--filled', true);
  }
}

// ── Load duplicate data ───────────────────────────────────────────────────────
function _prefillDuplicate() {
  const raw = sessionStorage.getItem('tf-bug-duplicate');
  if (!raw) return;
  sessionStorage.removeItem('tf-bug-duplicate');
  let d;
  try { d = JSON.parse(raw); } catch { return; }

  if (d.name)          { const el = document.getElementById('f-name');          if (el) el.value = d.name; }
  if (d.epic)          { const el = document.getElementById('f-epic');          if (el) el.value = d.epic; _bugCheckField('f-epic', 'fw-epic'); }
  if (d.what_happened) { const el = document.getElementById('f-what-happened'); if (el) { el.value = d.what_happened; _bugAutoGrow(el); _bugCheckField('f-what-happened', 'fw-what-happened'); } }
  if (d.expected)      { const el = document.getElementById('f-expected');      if (el) { el.value = d.expected;      _bugAutoGrow(el); _bugCheckField('f-expected', 'fw-expected'); } }
  if (d.steps)         { const el = document.getElementById('f-steps');         if (el) { el.value = d.steps;         _bugAutoGrow(el); } }
  if (d.details)       { const el = document.getElementById('f-details');       if (el) { el.value = d.details;       _bugAutoGrow(el); } }
  if (Array.isArray(d.roles)) {
    document.querySelectorAll('#roles .tf-chip').forEach(c => {
      c.classList.toggle('on', d.roles.includes(c.dataset.role));
    });
    const fw = document.getElementById('fw-role');
    if (fw) fw.classList.toggle('tf-field--filled', d.roles.length > 0);
  }
}

// ── Duplicate ─────────────────────────────────────────────────────────────────
function duplicateBug() {
  const data = {
    name:          document.getElementById('f-name')?.value.trim() || '',
    epic:          document.getElementById('f-epic')?.value.trim() || '',
    roles:         [...document.querySelectorAll('#roles .tf-chip.on')].map(c => c.dataset.role),
    what_happened: document.getElementById('f-what-happened')?.value.trim() || '',
    expected:      document.getElementById('f-expected')?.value.trim() || '',
    steps:         document.getElementById('f-steps')?.value.trim() || '',
    details:       document.getElementById('f-details')?.value.trim() || '',
  };
  sessionStorage.setItem('tf-bug-duplicate', JSON.stringify(data));
  window.location = '/create-bug';
}

// ── Prefill from sessionStorage ───────────────────────────────────────────────
function _prefillFromIssue() {
  const raw = sessionStorage.getItem('gh-issue-prefill');
  if (!raw) return;
  sessionStorage.removeItem('gh-issue-prefill');
  let issue;
  try { issue = JSON.parse(raw); } catch { return; }

  const nameEl = document.getElementById('f-name');
  if (nameEl && issue.title) nameEl.value = issue.title;

  const epicEl = document.getElementById('f-epic');
  if (epicEl && issue.epic) epicEl.value = issue.epic;

  const body = (issue.body || '').replace(/\r\n/g, '\n');
  const roleMatch = body.match(/- Role:\s*(.+)/);
  if (roleMatch) {
    const roles = roleMatch[1].split(/[,\s]+/).map(r => r.trim().toLowerCase()).filter(Boolean);
    document.querySelectorAll('#roles .tf-chip').forEach(c => {
      c.classList.toggle('on', roles.includes(c.dataset.role));
    });
    const fw = document.getElementById('fw-role');
    if (fw) fw.classList.toggle('tf-field--filled', !!document.querySelector('#roles .tf-chip.on'));
  }

  const sections = {
    'what-happened': /## Co se stalo\n([\s\S]*?)(?=\n+##|$)/,
    'expected':      /## Očekávaný výsledek\n([\s\S]*?)(?=\n+##|$)/,
    'steps':         /## Kroky k reprodukci\n([\s\S]*?)(?=\n+##|$)/,
    'details':       /## Další detaily\n([\s\S]*?)(?=\n+##|$)/,
  };
  for (const [field, re] of Object.entries(sections)) {
    const m = body.match(re);
    const el = document.getElementById('f-' + field);
    if (el) { el.value = m ? m[1].trim() : ''; _bugAutoGrow(el); }
  }
}
