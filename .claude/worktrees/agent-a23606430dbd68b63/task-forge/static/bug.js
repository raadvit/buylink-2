// ── Bug formulář ─────────────────────────────────────────────────────────────

const _bugRequired = {
  name: 'si-name',
  epic: 'si-epic',
  role: 'si-role',
  what_happened: 'si-what-happened',
  expected: 'si-expected',
};

const _bugCardMap = {
  name: 'c-name',
  epic: 'project-template-epic',
  role: 'project-template-role',
  what_happened: 'project-template-what-happened',
  expected: 'project-template-expected',
};

const _chips = {};

function toggleChip(el, group) {
  el.classList.toggle('active');
  if (!_chips[group]) _chips[group] = new Set();
  if (el.classList.contains('active')) {
    _chips[group].add(el.textContent.trim());
  } else {
    _chips[group].delete(el.textContent.trim());
  }
  check(group);
}

function getChips(group) {
  return _chips[group] ? [..._chips[group]] : [];
}

function val(id) {
  return (document.getElementById(id)?.value || '').trim();
}

function fieldValue(field) {
  if (field === 'role') return getChips('role').join(', ');
  if (field === 'epic') return val('f-epic');
  if (field === 'what_happened') return val('f-what-happened');
  if (field === 'expected') return val('f-expected');
  return val('f-' + field);
}

function check(field) {
  const siId = _bugRequired[field];
  if (!siId) return;
  const v = fieldValue(field);
  const si = document.getElementById(siId);
  const card = document.getElementById(_bugCardMap[field]);
  if (v) {
    if (si) { si.textContent = '✓'; si.className = 'si done'; }
    if (card) { card.classList.add('filled'); card.classList.remove('error'); }
  } else {
    if (si) { si.textContent = ''; si.className = 'si'; }
    if (card) { card.classList.remove('filled'); }
  }
}

async function submitBug() {
  const fields = Object.keys(_bugRequired);
  let valid = true;
  for (const f of fields) {
    const v = fieldValue(f);
    const card = document.getElementById(_bugCardMap[f]);
    if (!v) {
      if (card) card.classList.add('error');
      valid = false;
    }
  }
  if (!valid) return;

  window.scrollTo({ top: 0, behavior: 'smooth' });

  const payload = {
    name: val('f-name'),
    epic: val('f-epic'),
    role: getChips('role').join(', '),
    what_happened: val('f-what-happened'),
    expected: val('f-expected'),
    steps: val('f-steps'),
    details: val('f-details'),
  };

  try {
    const res = await fetch('/api/submit-bug', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) { console.error('Chyba při vytváření issue.', json.error || ''); return; }
    const tlWrap = document.getElementById('story-timeline-wrap');
    const tlContainer = document.getElementById('story-timeline-container');
    if (tlWrap && tlContainer) { renderTimeline(tlContainer, 'draft'); tlWrap.hidden = false; }
    document.querySelector('.btn-send').disabled = true;
  } catch (e) {
    console.error('Síťová chyba.', e.message);
  }
}

function _prefillFromIssue() {
  const raw = sessionStorage.getItem('gh-issue-prefill');
  if (!raw) return;
  sessionStorage.removeItem('gh-issue-prefill');
  let issue;
  try { issue = JSON.parse(raw); } catch { return; }

  const nameEl = document.getElementById('f-name');
  if (nameEl && issue.title) { nameEl.value = issue.title; check('name'); }

  const epicEl = document.getElementById('f-epic');
  if (epicEl && issue.epic) {
    for (const opt of epicEl.options) {
      if (opt.text === issue.epic || opt.text.startsWith(issue.epic.split(' ')[0])) {
        epicEl.value = opt.value;
        break;
      }
    }
    check('epic');
  }

  const body = (issue.body || '').replace(/\r\n/g, '\n');

  const roleMatch = body.match(/- Role:\s*(.+)/);
  if (roleMatch) {
    const roles = roleMatch[1].split(/[,\s]+/).map(r => r.trim().toLowerCase()).filter(Boolean);
    document.querySelectorAll('#roles .chip').forEach(c => {
      if (roles.includes(c.textContent.trim().toLowerCase())) {
        c.classList.add('active');
        if (!_chips['role']) _chips['role'] = new Set();
        _chips['role'].add(c.textContent.trim());
      }
    });
    check('role');
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
    if (el) { el.value = m ? m[1].trim() : ''; autoGrow(el); }
  }
  check('what_happened');
  check('expected');
}

document.addEventListener('DOMContentLoaded', _prefillFromIssue);

function newBug() {
  document.getElementById('f-name').value = '';
  document.getElementById('f-epic').value = '';
  document.querySelectorAll('#roles .chip').forEach(c => c.classList.remove('active'));
  Object.keys(_chips).forEach(k => { _chips[k] = new Set(); });
  ['f-what-happened', 'f-expected', 'f-steps', 'f-details'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = ''; el.style.height = ''; }
  });
  Object.keys(_bugCardMap).forEach(field => {
    const card = document.getElementById(_bugCardMap[field]);
    if (card) card.classList.remove('filled', 'error');
    const si = document.getElementById(_bugRequired[field]);
    if (si) { si.textContent = ''; si.className = 'si'; }
  });
  document.querySelector('.btn-send').disabled = false;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.getElementById('f-name').focus();
}
