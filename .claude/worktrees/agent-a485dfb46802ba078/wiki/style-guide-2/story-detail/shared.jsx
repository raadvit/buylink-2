// Shared atoms for both Task Forge variations.
// Czech labels preserved; design system stays consistent across variations.

const STEPS = [
  { id: 'draft',     label: 'Draft',       hint: 'Zachycení nápadu' },
  { id: 'konflikt',  label: 'Konflikt',    hint: 'Kontrola závislostí' },
  { id: 'arch',      label: 'Arch review', hint: 'Architektura' },
  { id: 'devplan',   label: 'Dev plán',    hint: 'Plánování práce' },
  { id: 'vyvoj',     label: 'Vývoj',       hint: 'Implementace' },
  { id: 'pr',        label: 'PR',          hint: 'Code review' },
  { id: 'done',      label: 'Done',        hint: 'Nasazeno' },
];

// Single canonical field list — same form, same order, regardless of step.
const ALL_FIELDS = [
  { id: 'why',     label: 'Why / Business Goal / Desired outcome', required: true,  type: 'textarea', placeholder: 'Proč to děláme? Jaký je cíl a měřitelný výsledek?', help: 'Cíl, ne řešení. Komu pomůžeme a jak to poznáme.' },
  { id: 'attach',  label: 'Attachment',                              required: false, type: 'file' },
  { id: 'shows',   label: 'Co se zobrazuje',                         required: true,  type: 'textarea', placeholder: 'Co uživatel uvidí na obrazovce?' },
  { id: 'behaves', label: 'Jak se to chová',                         required: true,  type: 'textarea', placeholder: 'Interakce, stavy, validace…' },
  { id: 'risk',    label: 'Rizikové situace / Nestandardní scénáře', required: false, type: 'textarea', placeholder: 'Edge cases, prázdné stavy, chyby…' },
  { id: 'tech',    label: 'Technické dopady',                        required: false, type: 'checks',   options: ['Napojení na API', 'Dopady na DB', 'Triggeruje notifikace', 'Security sensitive'] },
  { id: 'open',    label: 'Otevřené otázky / Blokery',               required: false, type: 'textarea', placeholder: 'Co zatím není rozhodnuto nebo může bránit realizaci.' },
  { id: 'ac',      label: 'Akceptační kritéria',                      required: false, type: 'textarea', placeholder: 'Nech prázdné — agent vygeneruje.', help: 'Seznam podmínek, které musí být splněny, aby story šla do hotovo.' },
];

const FIELD_GROUPS = new Proxy({}, { get: () => ALL_FIELDS });

// Sample agent messages keyed by active field
const AGENT_SCRIPTS = {
  idle: [
    { role: 'agent', text: 'Ahoj 👋 Pomůžu ti převést potřebu PO do jasné, strukturované user story.' },
    { role: 'agent', text: 'Začni názvem požadavku — krátce, věcně. Ostatní pole vyplním nebo navrhnu.' },
  ],
  konflikt: [
    { role: 'agent', text: 'Ahoj 👋 Při kontrole závislostí jsem našel **1 překryv** s aktivní story.' },
    { role: 'agent', kind: 'conflict', title: 'TF-218 „Sjednotit CTA barvy"', body: 'Stejné CTA barvy se řeší globálně přes design tokens. Doporučuji se s autorem TF-218 sladit, ať si nepřebíjíte změny.', action: 'Otevřít TF-218' },
    { role: 'agent', text: 'Až překryv vyřešíš, můžeme pokračovat na *Arch review*.' },
  ],
  title: [
    { role: 'agent', text: 'Dobrý název. Zaznamenávám změnu barvy CTA tlačítka.' },
    { role: 'agent', text: 'Mám se podívat, jestli neexistuje podobný požadavek?', action: 'Zkontrolovat duplicity' },
  ],
  why: [
    { role: 'agent', text: 'Pro „Business goal" zkus odpovědět na: kdo z toho má užitek a jak to měříme?' },
  ],
  shows: [
    { role: 'agent', text: 'Detekuji konflikt s EP-04: tam se barva CTA řeší globálně přes design tokens.' },
    { role: 'user',  text: 'Můžeš mi ukázat ten ticket?' },
    { role: 'agent', text: 'Jasně — TF-218 „Sjednotit CTA barvy". Otevřu vedle.', action: 'Otevřít TF-218' },
  ],
  behaves: [
    { role: 'agent', text: 'Doporučuji popsat i hover/focus stavy a chování s klávesnicí.' },
  ],
  tech: [
    { role: 'agent', text: 'Pokud měníš design token, dopady na DB pravděpodobně nebudou. Zruším náhodou zaškrtnutou položku?' },
  ],
};

// Tiny stylesheet shared via <style> tag injection
const SHARED_CSS = `
  :root {
    --bg:        oklch(98.5% 0.005 95);
    --surface:   oklch(100% 0 0);
    --surface-2: oklch(97% 0.005 95);
    --line:      oklch(91% 0.006 95);
    --line-2:    oklch(85% 0.008 95);
    --ink:       oklch(22% 0.01 270);
    --ink-2:     oklch(40% 0.012 270);
    --ink-3:     oklch(58% 0.012 270);
    --ink-4:     oklch(72% 0.012 270);
    --accent:    oklch(52% 0.18 290);
    --accent-2:  oklch(96% 0.03 290);
    --accent-ink:oklch(38% 0.14 290);
    --ok:        oklch(58% 0.13 150);
    --ok-2:      oklch(96% 0.04 150);
    --warn:      oklch(70% 0.14 75);
    --warn-2:    oklch(96% 0.05 75);
    --danger:    oklch(58% 0.18 25);
  }
  * { box-sizing: border-box; }
  body, html { margin: 0; padding: 0; background: var(--bg); color: var(--ink);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-feature-settings: 'cv11', 'ss01';
    -webkit-font-smoothing: antialiased;
  }
  .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  /* form atoms */
  .tf-label { font-size: 13px; font-weight: 550; color: var(--ink); letter-spacing: -0.005em; display: flex; align-items: center; gap: 6px; }
  .tf-label .req { color: var(--accent); font-weight: 700; }
  .tf-label .help-dot { width: 14px; height: 14px; border-radius: 50%; background: var(--surface-2); color: var(--ink-3); font-size: 10px; display: inline-flex; align-items: center; justify-content: center; cursor: help; border: 1px solid var(--line); }
  .tf-help { font-size: 12px; color: var(--ink-3); margin-top: 4px; line-height: 1.45; }

  .tf-input, .tf-textarea, .tf-select {
    width: 100%; background: var(--surface); border: 1px solid var(--line);
    border-radius: 8px; padding: 10px 12px; font: inherit; color: var(--ink);
    font-size: 14px; transition: border-color 120ms, box-shadow 120ms, background 120ms;
    outline: none;
  }
  .tf-input:hover, .tf-textarea:hover, .tf-select:hover { border-color: var(--line-2); }
  .tf-input:focus, .tf-textarea:focus, .tf-select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-2); }
  .tf-textarea { resize: vertical; min-height: 80px; line-height: 1.5; }

  .tf-field { display: flex; flex-direction: column; gap: 6px; }
  .tf-field.valid .tf-input, .tf-field.valid .tf-textarea, .tf-field.valid .tf-select {
    border-color: oklch(80% 0.08 150);
  }

  .tf-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .tf-chip { padding: 5px 10px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); font-size: 12.5px; color: var(--ink-2); cursor: pointer; transition: all 120ms; }
  .tf-chip:hover { border-color: var(--line-2); }
  .tf-chip.on { background: var(--accent); color: white; border-color: var(--accent); }

  .tf-checks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }
  .tf-check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-2); cursor: pointer; }
  .tf-check input { accent-color: var(--accent); width: 14px; height: 14px; }

  .tf-file {
    border: 1px dashed var(--line-2); border-radius: 8px; padding: 14px;
    text-align: center; font-size: 13px; color: var(--ink-3); background: var(--surface-2);
    cursor: pointer; transition: all 120ms;
  }
  .tf-file:hover { border-color: var(--accent); color: var(--accent-ink); }

  /* buttons */
  .tf-btn { display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px; border-radius: 8px; font: inherit; font-size: 13.5px; font-weight: 550; border: 1px solid transparent; cursor: pointer; transition: all 120ms; letter-spacing: -0.005em; white-space: nowrap; }
  .tf-btn-primary { background: var(--accent); color: white; }
  .tf-btn-primary:hover { background: oklch(48% 0.19 290); }
  .tf-btn-secondary { background: var(--surface); color: var(--ink); border-color: var(--line); }
  .tf-btn-secondary:hover { background: var(--surface-2); border-color: var(--line-2); }
  .tf-btn-ghost { background: transparent; color: var(--ink-2); }
  .tf-btn-ghost:hover { background: var(--surface-2); color: var(--ink); }

  /* checkmark */
  .tf-check-mark { width: 16px; height: 16px; border-radius: 50%; background: var(--ok); color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }

  /* nav */
  .tf-nav-link {
    padding: 7px 12px; border-radius: 7px; font-size: 13px; font-weight: 500;
    color: var(--ink-2); cursor: pointer; border: none; background: transparent;
    font-family: inherit; transition: all 120ms; display: inline-flex; align-items: center; gap: 6px;
  }
  .tf-nav-link:hover { background: var(--surface-2); color: var(--ink); }
  .tf-nav-link.active { background: var(--ink); color: white; }

  /* agent */
  .agent-msg { font-size: 13.5px; line-height: 1.55; }
  .agent-msg.agent { color: var(--ink); }
  .agent-msg.user  { color: var(--ink-2); }

  /* scrollbars subtle */
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 10px; border: 2px solid var(--bg); }
  ::-webkit-scrollbar-track { background: transparent; }
`;

// ---------- Reusable bits ----------

function HelpDot({ tip }) {
  return <span className="help-dot" title={tip}>?</span>;
}

function FieldLabel({ label, required, valid, help }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span className="tf-label">
        {required && <span className="req">•</span>}
        {label}
        {help && <HelpDot tip={help} />}
      </span>
      {valid && <span className="tf-check-mark">✓</span>}
    </div>
  );
}

function Field({ field, value, onChange, focused, onFocus }) {
  const valid = !!value && (typeof value === 'string' ? value.length > 3 : true);
  return (
    <div className={`tf-field ${valid ? 'valid' : ''}`} onFocus={onFocus} tabIndex={-1}
         style={{
           padding: focused ? '12px 14px' : '0',
           background: focused ? 'var(--accent-2)' : 'transparent',
           borderRadius: 10,
           transition: 'all 180ms',
           margin: focused ? '-2px -14px' : '0',
         }}>
      <FieldLabel label={field.label} required={field.required} valid={valid} help={field.help} />
      {field.type === 'text' && (
        <input className="tf-input" value={value || ''} placeholder={field.placeholder}
               onChange={e => onChange(e.target.value)} />
      )}
      {field.type === 'textarea' && (
        <textarea className="tf-textarea" value={value || ''} placeholder={field.placeholder}
                  rows={3} onChange={e => onChange(e.target.value)} />
      )}
      {field.type === 'select' && (
        <select className="tf-select" value={value || field.options[0]}
                onChange={e => onChange(e.target.value)}>
          {field.options.map(o => <option key={o}>{o}</option>)}
        </select>
      )}
      {field.type === 'chips' && (
        <div className="tf-chips">
          {field.options.map(o => {
            const sel = (value || field.selected || []).includes(o);
            return (
              <button key={o} className={`tf-chip ${sel ? 'on' : ''}`}
                      onClick={() => {
                        const cur = value || field.selected || [];
                        onChange(sel ? cur.filter(x => x !== o) : [...cur, o]);
                      }}>{o}</button>
            );
          })}
        </div>
      )}
      {field.type === 'checks' && (
        <div className="tf-checks">
          {field.options.map(o => {
            const sel = (value || []).includes(o);
            return (
              <label key={o} className="tf-check">
                <input type="checkbox" checked={sel}
                       onChange={() => {
                         const cur = value || [];
                         onChange(sel ? cur.filter(x => x !== o) : [...cur, o]);
                       }} />
                {o}
              </label>
            );
          })}
        </div>
      )}
      {field.type === 'file' && (
        <div className="tf-file">↥ Nahrát nebo přetáhnout</div>
      )}
    </div>
  );
}

// ---------- Top navigation (shared across both variations) ----------

function TopNav({ active = 'stories' }) {
  return (
    <header style={{
      background: 'var(--bg)', borderBottom: '1px solid var(--line)',
      padding: '10px 28px', display: 'grid',
      gridTemplateColumns: 'auto 1fr auto',
      alignItems: 'center', gap: 24, flexShrink: 0,
    }}>
      {/* LEFT: logo + primary nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--ink)',
                        color: 'white', display: 'flex', alignItems: 'center',
                        justifyContent: 'center', fontWeight: 700, fontSize: 13 }}>TF</div>
          <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.01em' }}>Task forge</div>
        </div>
        <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <a href="../stories-list/index.html" className={`tf-nav-link ${active === 'stories' ? 'active' : ''}`} style={{ textDecoration: 'none' }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="2" y="3" width="10" height="1.5" rx="0.5" fill="currentColor"/>
              <rect x="2" y="6.25" width="10" height="1.5" rx="0.5" fill="currentColor"/>
              <rect x="2" y="9.5" width="10" height="1.5" rx="0.5" fill="currentColor"/>
            </svg>
            Seznam stories
          </a>
        </nav>
      </div>

      {/* CENTER: search */}
      <div style={{ justifySelf: 'center', width: '100%', maxWidth: 480 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--surface)', border: '1px solid var(--line)',
          borderRadius: 7, padding: '6px 10px',
        }}>
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
            <circle cx="6" cy="6" r="4" stroke="var(--ink-3)" strokeWidth="1.5"/>
            <path d="M9 9 L12 12" stroke="var(--ink-3)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none',
                          font: 'inherit', fontSize: 12.5, color: 'var(--ink)' }}
                 placeholder="Hledat tickety, epicy, lidi…" />
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-4)',
                                          padding: '1px 5px', border: '1px solid var(--line-2)',
                                          borderRadius: 4 }}>⌘K</span>
        </div>
      </div>

      {/* RIGHT: actions + user */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="tf-btn tf-btn-secondary" style={{ color: 'var(--danger)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)' }}/>
          Vytvořit bug
        </button>
        <button className="tf-btn tf-btn-primary">+ Vytvořit story</button>
        <div style={{ width: 1, height: 24, background: 'var(--line)' }}/>
        <button className="tf-btn tf-btn-ghost" style={{ padding: 6, position: 'relative' }} title="Notifikace">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3.5 11 V7.5 a4.5 4.5 0 0 1 9 0 V11 l1 1.5 H2.5 Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
            <path d="M6.5 13.5 a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          <span style={{ position: 'absolute', top: 4, right: 4, width: 6, height: 6,
                         borderRadius: '50%', background: 'var(--accent)' }}/>
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px 4px 4px',
                      borderRadius: 7, cursor: 'pointer', transition: 'background 120ms' }}
             onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
             onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
          <div style={{ width: 28, height: 28, borderRadius: '50%',
                        background: 'oklch(75% 0.1 60)', color: 'white',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11.5, fontWeight: 600 }}>JK</div>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
            <span style={{ fontSize: 12.5, fontWeight: 550 }}>Jana Kovářová</span>
            <span style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>Product Owner</span>
          </div>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ marginLeft: 2 }}>
            <path d="M2 4 L5 7 L8 4" stroke="var(--ink-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
    </header>
  );
}

// ---------- Horizontal stepper (compact, read-only flow indicator) ----------
// Shows status icons:
//   ✓ green  — krok je hotový
//   ●︎ accent (animated) — krok právě probíhá
//   ✕ red    — krok selhal

function HorizontalStepper({ stepIdx, failedIdx = null }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      width: '100%',
      padding: '6px 4px',
      userSelect: 'none',
    }}>
      {STEPS.map((s, i) => {
        const failed = i === failedIdx;
        const active = !failed && i === stepIdx;
        const past   = i < stepIdx && !failed;

        // Visual: ring + optional inner dot (no checkmarks / Xs).
        let ringColor, dotColor, labelColor;
        if (failed) {
          ringColor = 'var(--danger)';
          dotColor  = 'var(--danger)';
          labelColor = 'var(--danger)';
        } else if (active) {
          ringColor = 'var(--accent)';
          dotColor  = 'var(--accent)';
          labelColor = 'var(--accent-ink)';
        } else if (past) {
          ringColor = 'var(--ok)';
          dotColor  = 'var(--ok)';
          labelColor = 'var(--ink-2)';
        } else {
          ringColor = 'var(--line-2)';
          dotColor  = null; // empty future step
          labelColor = 'var(--ink-4)';
        }

        return (
          <React.Fragment key={s.id}>
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: 10,
              flexShrink: 0,
            }}>
              <span style={{
                width: 14, height: 14, borderRadius: '50%',
                border: `1.5px solid ${ringColor}`,
                background: 'var(--surface)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 200ms',
                boxShadow: active
                  ? `0 0 0 4px color-mix(in oklch, ${ringColor} 14%, transparent)`
                  : 'none',
              }}>
                {dotColor && (
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: dotColor,
                    animation: active ? 'stepPulse 1.6s ease-in-out infinite' : 'none',
                  }}/>
                )}
              </span>
              <span style={{
                fontWeight: 600,
                fontSize: 10.5,
                letterSpacing: '0.09em',
                textTransform: 'uppercase',
                color: labelColor,
                whiteSpace: 'nowrap',
              }}>{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <span style={{
                flex: 1,
                height: 1,
                background: 'var(--line-2)',
                margin: '0 10px',
                marginBottom: 22, // align to circle row, not labels
              }}/>
            )}
          </React.Fragment>
        );
      })}
      <style>{`
        @keyframes stepPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%      { opacity: 0.55; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}

// ---------- Agent components ----------

function AgentAvatar({ size = 28, pulse = false }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: 8,
      background: 'var(--accent)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'white', fontWeight: 700, fontSize: size * 0.42,
      boxShadow: pulse ? '0 0 0 0 oklch(52% 0.18 290 / 0.5)' : 'none',
      animation: pulse ? 'agentPulse 1.6s ease-out infinite' : 'none',
      flexShrink: 0,
    }}>
      <svg width={size * 0.55} height={size * 0.55} viewBox="0 0 16 16" fill="none">
        <path d="M8 2 L13 8 L8 14 L3 8 Z" fill="white" opacity="0.95"/>
        <circle cx="8" cy="8" r="2" fill="var(--accent)"/>
      </svg>
    </div>
  );
}

function AgentMessage({ msg }) {
  if (msg.role === 'user') {
    return (
      <div style={{ alignSelf: 'flex-end', maxWidth: '85%',
                    background: 'var(--ink)', color: 'white',
                    padding: '8px 12px', borderRadius: '12px 12px 2px 12px',
                    fontSize: 13.5, lineHeight: 1.45 }}>
        {msg.text}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <AgentAvatar size={26} />
      <div style={{ flex: 1 }}>
        {msg.kind === 'conflict' ? (
          <div style={{
            background: 'var(--warn-2)',
            border: '1px solid oklch(88% 0.05 75)',
            borderRadius: 10, padding: '10px 12px',
            display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7,
                           fontSize: 11, fontWeight: 600, color: 'oklch(38% 0.13 75)',
                           textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--warn)' }}/>
              Konflikt
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>{msg.title}</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45 }}>{msg.body}</div>
            {msg.action && (
              <button style={{
                marginTop: 4, alignSelf: 'flex-start',
                padding: '5px 10px', borderRadius: 6,
                border: '1px solid oklch(82% 0.08 75)', background: 'var(--surface)',
                fontSize: 12, color: 'oklch(38% 0.13 75)', cursor: 'pointer',
                fontWeight: 600,
              }}>{msg.action} →</button>
            )}
          </div>
        ) : (
          <>
            <div className="agent-msg agent" dangerouslySetInnerHTML={{
              __html: (msg.text || '').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
                                       .replace(/\*([^*]+)\*/g, '<i>$1</i>')
            }}/>
            {msg.action && (
              <button style={{
                marginTop: 6, padding: '5px 10px', borderRadius: 6,
                border: '1px solid var(--line)', background: 'var(--surface)',
                fontSize: 12, color: 'var(--accent-ink)', cursor: 'pointer',
                fontWeight: 550,
              }}>{msg.action} →</button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ConflictBanner({ count = 1 }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 12px', background: 'var(--warn-2)',
      border: '1px solid oklch(85% 0.08 75)', borderRadius: 8,
      fontSize: 13, color: 'oklch(38% 0.13 75)',
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--warn)' }}/>
      <span style={{ flex: 1 }}>Conflict Detector našel <b>{count} překryv</b> — TF-218 „Sjednotit CTA barvy"</span>
      <button className="tf-btn tf-btn-ghost" style={{ padding: '4px 8px', fontSize: 12 }}>Zobrazit</button>
    </div>
  );
}

// expose globals
Object.assign(window, {
  STEPS, FIELD_GROUPS, AGENT_SCRIPTS, SHARED_CSS,
  Field, FieldLabel, HelpDot,
  TopNav, HorizontalStepper,
  AgentAvatar, AgentMessage, ConflictBanner,
});
