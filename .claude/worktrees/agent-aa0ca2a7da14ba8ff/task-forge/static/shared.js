function showStatus(state, title, detail) {
  const bar = document.getElementById('status-bar');
  const iconEl = document.getElementById('status-icon');
  const titleEl = document.getElementById('status-title');
  const detailEl = document.getElementById('status-detail');
  bar.hidden = false;
  bar.className = 'status-' + state;
  if (state === 'loading') {
    iconEl.innerHTML = '<div class="loading-spinner"></div>';
  } else if (state === 'success') {
    iconEl.innerHTML = '<svg class="status-icon-svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 00-1.414 0L8 12.586 4.707 9.293a1 1 0 00-1.414 1.414l4 4a1 1 0 001.414 0l8-8a1 1 0 000-1.414z" clip-rule="evenodd"/></svg>';
  } else {
    iconEl.innerHTML = '<svg class="status-icon-svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>';
  }
  // title může obsahovat bezpečné HTML (odkaz sestavený přes escHtml) — ale jen pokud obsahuje <a>
  if (typeof title === 'string' && title.includes('<a ')) {
    titleEl.innerHTML = title;
  } else {
    titleEl.textContent = title;
  }
  if (detail) {
    detailEl.textContent = detail;
    detailEl.hidden = false;
  } else {
    detailEl.textContent = '';
    detailEl.hidden = true;
  }
}

function hideStatus() {
  document.getElementById('status-bar').hidden = true;
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}
