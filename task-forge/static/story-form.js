/**
 * story-form.js — Sdílená komponenta formuláře story
 * Používá /create-story-2 (editable) i /us-{id} (read-only)
 *
 * initStoryForm(container, data, opts)
 *   container — DOM element kam renderovat
 *   data      — { title, epic, role, why, shows, behaves, risk, open, ac, status, issueId }
 *   opts      — { editable: bool, breadcrumb: html, onSave, onSubmit }
 */

function _sfAutoGrow(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

function parseWikiSections(md) {
  if (!md) return {};
  const out = {};
  let key = 'Metadata', buf = [];
  for (const line of md.split('\n')) {
    if (/^## /.test(line)) {
      if (buf.length) out[key] = buf.join('\n').trim();
      key = line.slice(3).trim();
      buf = [];
    } else {
      buf.push(line);
    }
  }
  if (buf.length) out[key] = buf.join('\n').trim();
  return out;
}

function parseMetadata(metaSection) {
  const out = {};
  for (const line of (metaSection || '').split('\n')) {
    // Starý formát: "- Key: value" i nový YAML formát: "key: value"
    const m = line.match(/^-?\s*(\w[\w\s\/]*?):\s*(.+)/);
    if (m) out[m[1].trim().toLowerCase()] = m[2].trim();
  }
  return out;
}

function storyDataFromApi(apiData) {
  const sections = parseWikiSections(apiData.wiki || apiData.body || '');
  const meta     = parseMetadata(sections['Metadata'] || '');
  const roles    = (meta['role'] || apiData.role || '')
    .split(/[,\s]+/).map(r => r.trim()).filter(Boolean);

  return {
    issueId:  apiData.id,
    title:    apiData.title || '',
    epic:     apiData.epic  || meta['epic'] || '',
    status:   apiData.story_status || meta['status'] || '',
    role:     roles,
    why:      sections['Why / Business Goal'] || sections['Business popis'] || sections['Business Context'] || '',
    shows:    sections['Co se zobrazuje'] || '',
    behaves:  sections['Jak se to chová']  || '',
    risk:     sections['Rizikové situace / Nestandardní scénáře'] || '',
    open:     sections['Otevřené otázky / Blokery'] || sections['Open Questions'] || '',
    ac:            sections['Acceptance Criteria'] || sections['Akceptační kritéria'] || '',
    techNotes:     sections['Technické poznámky (Architekt)'] || sections['Technické poznámky'] || sections['Architecture Notes'] || '',
    domainChanges: sections['Domain Changes'] || sections['Doménové změny'] || '',
    implPlan:      sections['Implementation Plan'] || sections['Implementační plán'] || '',
  };
}

// ── Field renderer ──────────────────────────────────────────────────────────

function sfField({ id, label, required, help, value, placeholder, type, editable, options, allOptions }) {
  const reqMark = required ? '<span class="req">*</span>' : '';
  const helpHtml = help ? `<div class="tf-help">${help}</div>` : '';

  if (type === 'chips') {
    const allRoles = allOptions || ['buyer', 'seller', 'admin', 'api'];
    const active   = Array.isArray(options) ? options : [];
    const chips = allRoles.map(r =>
      `<button class="tf-chip${active.includes(r) ? ' on' : ''}" data-role="${r}" type="button"${editable ? '' : ' disabled'}>${r}</button>`
    ).join('');
    return `<div class="tf-field">
      <label class="tf-label">${label} ${reqMark}<span class="si" id="si-${id}"></span></label>
      <div class="tf-chips" id="${id}">${chips}</div>
    </div>`;
  }

  if (type === 'attachment') {
    if (!editable) return '';
    const ACCEPT = "image/*,.pdf,.js,.jsx,.ts,.tsx,.json,.xml,.html,.htm,.css,.scss,.txt,.csv,.md,.yaml,.yml,.toml,.sql,.py,.rb,.java,.kt,.swift,.go,.rs,.cpp,.project-template,.h,.sh";
    return `<div class="tf-field">
      <label class="tf-label">${label}</label>
      <div class="drop-zone" id="sf-dz" tabindex="0">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
        <span id="sf-dz-label">Nahrát nebo přetáhnout</span>
      </div>
      <input type="file" id="sf-f-file" accept="${ACCEPT}" multiple style="display:none" />
    </div>`;
  }

  if (editable) {
    const listAttr = id === 'f-epic' ? ' list="epic-suggestions"' : '';
    const input = type === 'input'
      ? `<input class="tf-input" id="${id}" type="text" value="${sfEsc(value)}" placeholder="${sfEsc(placeholder || '')}"${listAttr} />`
      : `<textarea class="tf-textarea" id="${id}" placeholder="${sfEsc(placeholder || '')}">${sfEsc(value)}</textarea>`;
    return `<div class="tf-field">${helpHtml}<label class="tf-label" for="${id}">${label} ${reqMark}<span class="si" id="si-${id}"></span></label>${input}</div>`;
  } else {
    const input = type === 'input'
      ? `<input class="tf-input" id="${id}" type="text" value="${sfEsc(value)}" placeholder="—" disabled />`
      : `<textarea class="tf-textarea" id="${id}" placeholder="—" disabled>${sfEsc(value)}</textarea>`;
    return `<div class="tf-field">
      <label class="tf-label" for="${id}">${label}</label>
      ${helpHtml}${input}
    </div>`;
  }
}

function sfEsc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Main render ─────────────────────────────────────────────────────────────

function initStoryForm(container, data = {}, opts = {}) {
  const editable = opts.editable !== false;
  const breadcrumb = opts.breadcrumb ||
    `<a href="/list">Všechny user stories</a><span class="sep">/</span><span>${sfEsc(data.title || 'Nová story')}</span>`;

  const fields = [
    sfField({ id:'f-why', label:'Why / Business Goal', required:true,
      value:data.why, placeholder:'Proč to děláme?', type:'textarea', editable }),
    sfField({ id:'sf-upload', label:'Attachment', type:'attachment', editable }),
    `<div class="sf-inline-group">
       ${sfField({ id:'f-epic', label:'Epic', required:true,
         value:data.epic, placeholder:'EP-01 Task-forge', type:'input', editable })}
       ${sfField({ id:'roles', label:'Role', required:true,
         type:'chips', options:data.role, editable })}
     </div>`,
    sfField({ id:'f-shows', label:'Co se zobrazuje', required:true,
      value:data.shows, placeholder:'Co uživatel uvidí na obrazovce?', type:'textarea', editable }),
    sfField({ id:'f-behaves', label:'Jak se to chová', required:true,
      value:data.behaves, placeholder:'Interakce, stavy, validace…', type:'textarea', editable }),
    sfField({ id:'f-risk', label:'Rizikové situace / Nestandardní scénáře',
      value:data.risk, placeholder:'Edge cases, prázdné stavy, chyby…', type:'textarea', editable }),
    sfField({ id:'f-open', label:'Otevřené otázky / Blokery',
      value:data.open, placeholder:'Co zatím není rozhodnuto nebo může bránit realizaci.', type:'textarea', editable }),
    sfField({ id:'f-ac', label:'Akceptační kritéria',
      help: editable ? 'Nech prázdné — agent vygeneruje.' : '',
      value:data.ac, placeholder:'Seznam podmínek, které musí být splněny.', type:'textarea', editable }),
  ];

  if (!editable && data.techNotes) {
    fields.push(sfField({ id:'f-tech', label:'Architecture Notes',
      value:data.techNotes, type:'textarea', editable: false }));
  }
  if (!editable && data.domainChanges) {
    fields.push(sfField({ id:'f-domain', label:'Domain Changes',
      value:data.domainChanges, type:'textarea', editable: false }));
  }
  if (!editable && data.implPlan) {
    fields.push(sfField({ id:'f-impl', label:'Implementation Plan',
      value:data.implPlan, type:'textarea', editable: false }));
  }

  const saveLabel   = opts.saveLabel   || 'Uložit na později';
  const submitLabel = opts.submitLabel || 'Odeslat týmu k validaci →';
  const dupBtn = opts.onDuplicate
    ? `<button class="tf-btn tf-btn-ghost" type="button" id="btn-duplicate">Duplikovat</button>`
    : '';
  const delBtn = opts.onDelete
    ? `<button class="tf-btn tf-btn-ghost" type="button" id="btn-delete">Smazat</button>`
    : '';
  const isVerify = data.status === 'ready_for_testing' || data.status === 'ready-for-testing';
  const isDone   = data.status === 'done';
  const footerHtml = (editable || opts.onDuplicate || opts.onDelete)
    ? `<div class="cs-footer">
         <div style="display:flex;gap:8px;margin-right:auto">${delBtn}${dupBtn}</div>
         ${isVerify
           ? `<button class="tf-btn tf-btn-secondary" type="button" id="btn-create-bug">Vytvořit bug</button>
              <button class="tf-btn" style="background:var(--ok);color:#fff" type="button" id="btn-close-story">Zavřít</button>`
           : isDone
           ? `<button class="tf-btn tf-btn-secondary" type="button" id="btn-create-bug">Vytvořit bug</button>`
           : editable ? `<button class="tf-btn tf-btn-secondary" type="button" id="btn-save">${saveLabel}</button>
              <button class="tf-btn tf-btn-primary" type="button" id="btn-submit">${submitLabel}</button>` : ''}
       </div>`
    : '';

  const agentStatus = editable ? 'Aktivní · čeká na vyplnění' : `Status: ${sfEsc(data.status || '—')}`;
  const agentInitMsg = editable
    ? `<div class="cs-msg agent">Ahoj 👋 Pomůžu ti převést potřebu PO do jasné, strukturované user story.</div>
       <div class="cs-msg agent">Začni názvem požadavku — krátce, věcně. Ostatní pole vyplním nebo navrhnu.</div>`
    : '';

  container.innerHTML = `
    <div class="cs-layout">
      <div class="cs-body">
        <main class="cs-form-wrap">
          <div class="cs-form-content">
            <div class="cs-breadcrumb">${breadcrumb}</div>
            ${editable
              ? `<input class="cs-title-input" id="f-title" type="text" value="${sfEsc(data.title)}" placeholder="Název story…" maxlength="120" />
                 <datalist id="epic-suggestions"></datalist>`
              : `<h1 class="cs-title-input">${sfEsc(data.title)}</h1>`}
            <div id="story-timeline-container"></div>
            <div class="cs-fields">${fields.join('')}</div>
          </div>
          ${footerHtml}
        </main>

        <aside class="cs-agent">
          <div class="cs-agent-head">
            <div class="cs-agent-avatar">F</div>
            <div>
              <div class="cs-agent-name">Forge Agent</div>
              <div class="cs-agent-status">
                <span class="cs-agent-status-dot"></span>
                ${agentStatus}
              </div>
            </div>
            ${!editable && data.status === 'validated' ? `<button id="btn-start-dev" class="btn-start-dev">&#9654; Spustit vývoj</button>` : ''}
          </div>
          <div class="cs-chat" id="agentChat">${agentInitMsg}</div>
          <div class="cs-chat-input-wrap">
            <div class="cs-chat-input">
              <input type="text" placeholder="Zeptej se agenta…" id="agentInput" />
              <button class="tf-btn tf-btn-primary" style="padding:5px 10px;font-size:12px" type="button" id="agentSend">Odeslat</button>
            </div>
            <div class="cs-quick-btns">
              <button class="cs-quick-btn" type="button">Vygeneruj AC</button>
              <button class="cs-quick-btn" type="button">Najdi duplicity</button>
              <button class="cs-quick-btn" type="button">Odhadni složitost</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  `;

  // Auto-grow všech textarí (editable i read-only)
  container.querySelectorAll('textarea').forEach(el => _sfAutoGrow(el));

  // Role chips toggle (only editable)
  if (editable) {
    container.querySelectorAll('#roles .tf-chip').forEach(chip => {
      chip.addEventListener('click', () => chip.classList.toggle('on'));
    });
  }

  // Expose helpers for read-back
  container._getFormData = function() {
    return {
      title:  (container.querySelector('#f-title')?.value || '').trim(),
      epic:   (container.querySelector('#f-epic')?.value  || '').trim(),
      role:   Array.from(container.querySelectorAll('#roles .tf-chip.on')).map(c => c.dataset.role),
      why:    (container.querySelector('#f-why')?.value   || '').trim(),
      what:   (container.querySelector('#f-shows')?.value  || '').trim(),
      how:    (container.querySelector('#f-behaves')?.value|| '').trim(),
      scope:  (container.querySelector('#f-risk')?.value  || '').trim(),
      deps:   (container.querySelector('#f-open')?.value  || '').trim(),
      ac:     (container.querySelector('#f-ac')?.value    || '').trim(),
    };
  };

  // Field fill indicators (.si)
  if (editable) {
    function updateSi(el) {
      const si = container.querySelector(`#si-${el.id}`);
      if (!si) return;
      const filled = el.value.trim().length > 0;
      si.textContent = filled ? '✓' : '';
      si.className = 'si' + (filled ? ' done' : '');
      el.closest('.tf-field')?.classList.toggle('tf-field--filled', filled);
    }
    container.querySelectorAll('.tf-input, .tf-textarea').forEach(el => {
      el.addEventListener('input', () => { updateSi(el); if (el.tagName === 'TEXTAREA') _sfAutoGrow(el); });
      updateSi(el);
      if (el.tagName === 'TEXTAREA') _sfAutoGrow(el);
    });
  }

  // Attachment dropzone
  const uploadedFiles = [];
  const dz       = container.querySelector('#sf-dz');
  const dzLabel  = container.querySelector('#sf-dz-label');
  const fileInput = container.querySelector('#sf-f-file');

  function addFiles(fileList) {
    const remaining = 3 - uploadedFiles.length;
    Array.from(fileList).slice(0, remaining).forEach(f => uploadedFiles.push(f));
    updateDz();
  }

  function updateDz() {
    if (!dz) return;
    dz.querySelectorAll('.thumb-wrap').forEach(e => e.remove());
    if (uploadedFiles.length === 0) {
      dz.classList.remove('has-file');
      if (dzLabel) dzLabel.textContent = 'Nahrát nebo přetáhnout';
    } else {
      dz.classList.add('has-file');
      uploadedFiles.forEach(file => {
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
      if (dzLabel) dzLabel.textContent = uploadedFiles.length < 3 ? `+ přidat (${3 - uploadedFiles.length} zbývá)` : '';
    }
  }

  if (dz && fileInput) {
    dz.addEventListener('click', () => fileInput.click());
    dz.addEventListener('dragover', e => e.preventDefault());
    dz.addEventListener('drop', e => { e.preventDefault(); addFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });
  }

  container._uploadedFiles = uploadedFiles;

  // Wire footer buttons if callbacks provided
  if (opts.onSave)      container.querySelector('#btn-save')     ?.addEventListener('click', opts.onSave);
  if (opts.onSubmit)    container.querySelector('#btn-submit')   ?.addEventListener('click', opts.onSubmit);
  if (opts.onDuplicate) container.querySelector('#btn-duplicate')?.addEventListener('click', opts.onDuplicate);
  if (opts.onDelete)    container.querySelector('#btn-delete')   ?.addEventListener('click', opts.onDelete);

  return container;
}

/**
 * sfValidate(container) — označí neplatná povinná pole červeně, scrolluje na první chybu.
 * Vrátí true pokud je vše OK, false pokud existují chyby.
 */
function sfValidate(container) {
  // Vymaž předchozí chyby
  container.querySelectorAll('.tf-field--error').forEach(el => el.classList.remove('tf-field--error'));

  const checks = [
    { el: container.querySelector('#f-epic'),    test: el => el?.value?.trim() },
    { el: container.querySelector('#roles'),     test: el => el?.querySelector('.tf-chip.on') },
    { el: container.querySelector('#f-shows'),   test: el => el?.value?.trim() },
    { el: container.querySelector('#f-behaves'), test: el => el?.value?.trim() },
  ];

  let firstError = null;
  for (const { el, test } of checks) {
    if (!el) continue;
    if (!test(el)) {
      const field = el.closest('.tf-field') || el.parentElement;
      if (field) field.classList.add('tf-field--error');
      if (!firstError) firstError = field || el;
    }
  }

  // Titul nemá .tf-field wrapper — označit speciálně
  const titleEl = container.querySelector('#f-title');
  if (titleEl && !titleEl.value?.trim()) {
    titleEl.style.borderColor = 'var(--danger)';
    titleEl.style.boxShadow   = '0 0 0 3px var(--danger-2)';
    if (!firstError) firstError = titleEl;
  } else if (titleEl) {
    titleEl.style.borderColor = '';
    titleEl.style.boxShadow   = '';
  }

  if (firstError) {
    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
  }
  return true;
}

