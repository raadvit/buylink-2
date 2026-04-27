let _listIssues = [];
let _listFilter = 'all';

const _LIST_TYPE_CLASS = { all: 'active-all', idea: 'active-idea', story: 'active-story', bug: 'active-bug', ready: 'active-ready' };
const _LIST_LABEL_MAP = { idea: 'idea', story: 'user story', bug: 'bug', other: 'other' };

function _isReadyForTesting(issue) {
  return (
    (Array.isArray(issue.labels) && issue.labels.some(l => ['ready for testing', 'ready-for-testing', 'ready_for_testing'].includes(l))) ||
    ['ready_for_testing', 'ready-for-testing', 'ready for testing'].includes(issue.story_status)
  );
}

function applyListFilters() {
  const q = (document.getElementById('listSearchInput').value || '').toLowerCase().trim();
  let filtered = _listIssues;
  if (_listFilter === 'ready') {
    filtered = filtered.filter(_isReadyForTesting);
  } else if (_listFilter !== 'all') {
    filtered = filtered.filter(i => i.type === _listFilter);
  }
  if (q) {
    filtered = filtered.filter(i =>
      i.title.toLowerCase().includes(q) ||
      (i.epic || '').toLowerCase().includes(q) ||
      ('#' + i.id).includes(q)
    );
  }
  _renderListIssues(filtered);
}

function setListFilter(type, btn) {
  _listFilter = type;
  document.querySelectorAll('.gh-filter').forEach(b => {
    b.className = 'gh-filter';
    b.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add(_LIST_TYPE_CLASS[type] || 'active-all');
  btn.setAttribute('aria-pressed', 'true');
  if (type === 'all') {
    localStorage.removeItem('gh-status-filter');
  } else {
    localStorage.setItem('gh-status-filter', type);
  }
  applyListFilters();
}

function _renderListIssues(items) {
  const tbody = document.getElementById('listTbody');
  const footer = document.getElementById('listFooterCount');
  footer.textContent = items.length + (items.length === 1 ? ' issue' : ' issues');
  if (!items.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="4">Žádné issues neodpovídají filtru</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(i => `
    <tr onclick="selectListIssue(${i.id})" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();selectListIssue(${i.id})}">
      <td>
        <div class="issue-title-cell">
          <span class="gh-dot ${escHtml(i.type)}"></span>
          <span class="issue-id">#${i.id}</span>
          <span class="issue-title-text">${escHtml(i.title)}</span>
        </div>
      </td>
      <td><span class="gh-badge ${escHtml(i.type)}">${escHtml(_LIST_LABEL_MAP[i.type] || i.type)}</span></td>
      <td class="cell-meta col-epic">${escHtml(i.epic || '')}</td>
      <td class="cell-meta">${escHtml(i.date || '')}</td>
    </tr>
  `).join('');
}

function selectListIssue(id) {
  const issue = _listIssues.find(i => i.id === id);
  if (!issue) return;
  if (issue.type === 'bug') {
    window.location.href = `/bug-${issue.id}`;
    return;
  }
  localStorage.setItem('gh-issue-load', JSON.stringify(issue));
  window.location.href = '/';
}

function _restoreListFilter() {
  const saved = localStorage.getItem('gh-status-filter');
  if (!saved) return;
  const btnId = { idea: 'lff-idea', story: 'lff-story', bug: 'lff-bug', ready: 'lff-ready' }[saved];
  if (!btnId) return;
  const btn = document.getElementById(btnId);
  if (!btn) return;
  _listFilter = saved;
  document.querySelectorAll('.gh-filter').forEach(b => {
    b.className = 'gh-filter';
    b.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add(_LIST_TYPE_CLASS[saved]);
  btn.setAttribute('aria-pressed', 'true');
}

async function _loadListIssues() {
  const tbody = document.getElementById('listTbody');
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:2rem;color:#aaa;font-size:13px">Načítám…</td></tr>';
  try {
    const res = await fetch('/api/issues', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    _listIssues = await res.json();
    applyListFilters();
    _applyPendingBadges();
  } catch (err) {
    document.getElementById('listTbody').innerHTML =
      '<tr class="empty-row"><td colspan="4">Nepodařilo se načíst issues: ' + escHtml(err.message) + '</td></tr>';
    document.getElementById('listFooterCount').textContent = '';
  }
}

let _pendingByIssue = {};

function _applyPendingBadges() {
  document.querySelectorAll('#listTbody tr[onclick]').forEach(row => {
    const m = row.getAttribute('onclick').match(/selectListIssue\((\d+)\)/);
    if (!m) return;
    const id = parseInt(m[1], 10);
    const existing = row.querySelector('.pending-question-badge');
    if (_pendingByIssue[id]) {
      if (!existing) {
        const badge = document.createElement('span');
        badge.className = 'pending-question-badge';
        badge.title = 'Agent čeká na odpověď';
        badge.textContent = '? Odpověz';
        badge.style.cssText = 'margin-left:8px;font-size:11px;font-weight:600;color:#fff;background:oklch(62% 0.18 55);border-radius:4px;padding:1px 6px;vertical-align:middle;';
        const titleCell = row.querySelector('.issue-title-text');
        if (titleCell) titleCell.after(badge);
      }
    } else if (existing) {
      existing.remove();
    }
  });
}

async function _pollPendingSessions() {
  try {
    const res = await fetch('/api/sessions/pending', { cache: 'no-store' });
    if (!res.ok) return;
    const sessions = await res.json();
    _pendingByIssue = {};
    sessions.forEach(s => { if (s.issue_number) _pendingByIssue[s.issue_number] = true; });
    _applyPendingBadges();
  } catch {}
}

document.addEventListener('DOMContentLoaded', () => {
  _restoreListFilter();
  _loadListIssues();
  _pollPendingSessions();
  setInterval(_pollPendingSessions, 15000);
});
