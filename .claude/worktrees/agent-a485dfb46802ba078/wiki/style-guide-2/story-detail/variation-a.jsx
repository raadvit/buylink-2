// Variation A: TopNav + horizontal stepper above content + form left + agent chat right.

function VariationA() {
  const [stepIdx, setStepIdx] = React.useState(1);
  const [values, setValues] = React.useState({
    title: 'Změna barvy tlačítka odeslat týmu k validaci na žlutou',
    why:   'Stávající modré CTA splývá se zápatím a uživatelé ho přehlížejí — chceme zvýšit počet odeslaných požadavků k validaci.',
    epic: 'EP-01 Task-forge',
    role: ['admin'],
    shows:   'Tlačítko „Odeslat týmu k validaci" v patičce formuláře.',
    behaves: 'Žlutá barva pro klidový stav, hover ztmavne, focus s prstencem dle design tokens.',
    tech: ['Triggeruje notifikace'],
  });
  const [focused, setFocused] = React.useState(null);
  const [agentLog, setAgentLog] = React.useState(AGENT_SCRIPTS.konflikt);
  const chatRef = React.useRef(null);

  const step = STEPS[stepIdx];
  const fields = FIELD_GROUPS[step.id] || [];

  function setField(id, val) { setValues(v => ({ ...v, [id]: val })); }
  function focusField(id) {
    setFocused(id);
    if (AGENT_SCRIPTS[id]) setAgentLog(AGENT_SCRIPTS[id]);
  }

  const completed = (() => {
    const counts = {};
    Object.entries(FIELD_GROUPS).forEach(([k, fs]) => {
      const req = fs.filter(f => f.required);
      const done = req.filter(f => values[f.id] && (typeof values[f.id] === 'string' ? values[f.id].length > 3 : values[f.id].length > 0));
      counts[k] = { done: done.length, total: req.length };
    });
    return counts;
  })();

  React.useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [agentLog]);

  return (
    <div style={{ width: 1440, height: 900, display: 'flex', flexDirection: 'column',
                  background: 'var(--surface)', overflow: 'hidden' }}>

      <TopNav active="stories" />

      {/* Body — form left, agent right */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 380px', overflow: 'hidden' }}>

        {/* ---- Form ---- */}
        <main style={{ overflow: 'auto', padding: '32px 56px 120px', position: 'relative' }}>
          {/* Breadcrumb + story title + stepper-under-title */}
          <div style={{ marginBottom: 28, maxWidth: 880 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12,
                          color: 'var(--ink-3)', marginBottom: 8 }}>
              <a href="../stories-list/index.html" style={{ cursor: 'pointer', color: 'inherit', textDecoration: 'underline', textDecorationColor: 'var(--line-2)', textUnderlineOffset: 3 }}>Stories</a>
              <span style={{ color: 'var(--ink-4)' }}>/</span>
              <span className="mono">EP-01 Task-forge</span>
              <span style={{ color: 'var(--ink-4)' }}>/</span>
              <span className="mono" style={{ color: 'var(--ink-2)' }}>TF-419</span>
            </div>
            <input
              value={values.title || ''}
              onChange={e => setField('title', e.target.value)}
              placeholder="Nová user story"
              style={{
                display: 'block', margin: '0 0 14px -10px',
                fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em',
                lineHeight: 1.3, width: 'calc(100% + 10px)', border: '1px solid transparent',
                background: 'transparent', color: 'var(--ink)', padding: '6px 10px',
                borderRadius: 8, fontFamily: 'inherit', outline: 'none',
                transition: 'all 120ms',
              }}
              onFocus={e => { e.target.style.background = 'var(--surface)'; e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px var(--accent-2)'; }}
              onBlur={e => { e.target.style.background = 'transparent'; e.target.style.borderColor = 'transparent'; e.target.style.boxShadow = 'none'; }}
            />
            <HorizontalStepper stepIdx={stepIdx} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 720 }}>
            {fields.map(f => (
              <Field key={f.id} field={f}
                     value={values[f.id]}
                     onChange={v => setField(f.id, v)}
                     focused={focused === f.id}
                     onFocus={() => focusField(f.id)} />
            ))}
          </div>

          {/* Footer actions */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, var(--surface) 70%, transparent)',
            padding: '20px 56px 28px',
            display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
          }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="tf-btn tf-btn-secondary">Uložit na později</button>
              <button className="tf-btn tf-btn-primary"
                      onClick={() => setStepIdx(Math.min(STEPS.length - 1, stepIdx + 1))}>
                Pokračovat na {STEPS[Math.min(STEPS.length - 1, stepIdx + 1)].label} →
              </button>
            </div>
          </div>
        </main>

        {/* ---- Agent chat ---- */}
        <aside style={{ background: 'var(--surface)', borderLeft: '1px solid var(--line)',
                        display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)',
                        display: 'flex', alignItems: 'center', gap: 12 }}>
            <AgentAvatar size={32} pulse={true} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>Forge Agent</div>
              <div style={{ fontSize: 11.5, color: 'var(--ok)', display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ok)' }}/>
                Aktivní · Conflict Detector
              </div>
            </div>
            <button
              title="Předat story k vývoji"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '7px 11px', borderRadius: 7,
                background: 'var(--ok)',
                color: 'white',
                border: 'none',
                font: 'inherit', fontSize: 12.5, fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 1px 2px oklch(50% 0.13 150 / 0.25)',
                flexShrink: 0,
                transition: 'all 120ms',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'oklch(48% 0.14 150)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--ok)'; e.currentTarget.style.transform = 'translateY(0)'; }}>
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M2.5 1.5 L9 5.5 L2.5 9.5 Z" fill="currentColor"/>
              </svg>
              Spustit vývoj
            </button>
          </div>

          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--line)',
                        background: 'var(--surface-2)' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase',
                          letterSpacing: '0.06em', fontWeight: 600, marginBottom: 8 }}>Pracuje na</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', marginBottom: 8 }}>
              Conflict Detector — kontrola závislostí
            </div>
            <div style={{ height: 4, background: 'var(--line)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: '64%', height: '100%', background: 'var(--accent)',
                            borderRadius: 2, animation: 'progressPulse 2s ease-in-out infinite' }}/>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-3)', marginTop: 6 }}>
              scanned 18 / 28 epics
            </div>
          </div>

          <div ref={chatRef} style={{ flex: 1, overflowY: 'auto', padding: '18px 20px',
                                       display: 'flex', flexDirection: 'column', gap: 14 }}>
            {agentLog.map((m, i) => <AgentMessage key={i} msg={m} />)}
          </div>

          <div style={{ padding: 14, borderTop: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8,
                          background: 'var(--surface-2)', border: '1px solid var(--line)',
                          borderRadius: 10, padding: '8px 10px' }}>
              <input style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none',
                              font: 'inherit', fontSize: 13 }}
                     placeholder="Zeptej se agenta…" />
              <button className="tf-btn tf-btn-primary" style={{ padding: '5px 10px', fontSize: 12 }}>
                Odeslat
              </button>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
              {['Vygeneruj AC', 'Najdi duplicity', 'Odhadni složitost'].map(s => (
                <button key={s} style={{ fontSize: 11.5, padding: '4px 8px', borderRadius: 6,
                                         border: '1px solid var(--line)', background: 'var(--surface)',
                                         color: 'var(--ink-2)', cursor: 'pointer' }}>{s}</button>
              ))}
            </div>
          </div>
        </aside>
      </div>

      <style>{`
        @keyframes agentPulse {
          0% { box-shadow: 0 0 0 0 oklch(52% 0.18 290 / 0.4); }
          100% { box-shadow: 0 0 0 10px oklch(52% 0.18 290 / 0); }
        }
        @keyframes progressPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

window.VariationA = VariationA;
