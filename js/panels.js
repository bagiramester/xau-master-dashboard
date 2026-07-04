// ═══ PANELS — session countdown, makró naptár timeline, FedWatch bar ═══
const SESSION_SCHEDULE = [
  { name: 'London', startH: 9, endH: 12 },
  { name: 'Overlap', startH: 14, endH: 19 },
];

const renderSessionCountdown = () => {
  const host = $('#tb-session-countdown');
  if (!host) return;
  const now = new Date();
  const h = now.getHours() + now.getMinutes() / 60;
  let label = '';
  const active = SESSION_SCHEDULE.find(s => h >= s.startH && h < s.endH);
  if (active) {
    const mins = Math.round((active.endH - h) * 60);
    label = `${active.name} zárásig: ${Math.floor(mins/60)}ó ${mins%60}p`;
  } else {
    const next = SESSION_SCHEDULE.find(s => s.startH > h) || SESSION_SCHEDULE[0];
    let diff = (next.startH - h);
    if (diff < 0) diff += 24;
    const mins = Math.round(diff * 60);
    label = `${next.name} nyitásig: ${Math.floor(mins/60)}ó ${mins%60}p`;
  }
  host.textContent = label;
};

const renderMacroTimeline = (data) => {
  const host = $('#macro-timeline');
  if (!host) return;
  host.innerHTML = '';
  const events = (data.notrade_filters && data.notrade_filters.macro_events_today) || [];
  if (events.length === 0) { host.appendChild(el('div', { class: 'log-empty' }, 'Nincs mai high-impact esemény.')); return; }
  events.forEach(ev => {
    host.appendChild(el('div', { class: 'macro-tl-item' },
      el('span', { class: 'mono macro-tl-time' }, ev.time_cest || '—'),
      el('span', { class: 'macro-tl-event' }, ev.event || '—'),
      el('span', { class: 'macro-tl-effect' }, ev.effect || ev.note || '')
    ));
  });
};

const renderFedwatch = (data) => {
  const host = $('#fedwatch-panel');
  if (!host) return;
  host.innerHTML = '';
  const fw = data.macro && data.macro.fedwatch;
  if (!fw || fw.value == null) { host.appendChild(el('div', { class: 'log-empty' }, 'Nincs FedWatch adat.')); return; }
  host.appendChild(el('div', { class: 'fedwatch-summary' }, fw.display || String(fw.value)));
  if (fw.bias_note) host.appendChild(el('div', { class: 'fedwatch-note' }, fw.bias_note));
};

const renderPanels = (data) => {
  renderSessionCountdown();
  renderMacroTimeline(data);
  renderFedwatch(data);
};

// countdown él magától is
setInterval(renderSessionCountdown, 30000);
