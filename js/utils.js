// ═══ UTILS ═══
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'data' && typeof v === 'object') {
      for (const [dk, dv] of Object.entries(v)) node.dataset[dk] = dv;
    } else if (k.startsWith('on') && typeof v === 'function') {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v !== null && v !== undefined) {
      node.setAttribute(k, v);
    }
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return node;
};

const fmtCEST = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('hu-HU', { hour: '2-digit', minute: '2-digit' }) + ' CEST';
  } catch { return '—'; }
};

const fmtRelative = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 60000;
  if (diff < 1) return 'most';
  if (diff < 60) return `${Math.round(diff)}p`;
  if (diff < 1440) return `${Math.round(diff/60)}ó`;
  return `${Math.round(diff/1440)}n`;
};

const isStale = (iso, maxMinutes = 30) => {
  if (!iso) return true;
  const diff = (Date.now() - new Date(iso).getTime()) / 60000;
  return diff > maxMinutes;
};

const biasToState = (bias) => {
  if (!bias) return 'neutral';
  return bias.toLowerCase();
};

// Info tooltip
const tooltip = () => $('#tooltip');
const showTip = (evt, text) => {
  const tip = tooltip();
  tip.textContent = text;
  tip.hidden = false;
  const x = evt.clientX + 12;
  const y = evt.clientY + 12;
  tip.style.left = Math.min(x, window.innerWidth - 300) + 'px';
  tip.style.top  = Math.min(y, window.innerHeight - 100) + 'px';
};
const hideTip = () => { tooltip().hidden = true; };

const attachInfo = (host, text) => {
  const btn = el('span', { class: 'info-btn', title: text }, 'i');
  btn.addEventListener('mouseenter', (e) => showTip(e, text));
  btn.addEventListener('mousemove', (e) => showTip(e, text));
  btn.addEventListener('mouseleave', hideTip);
  host.appendChild(btn);
  return btn;
};

// Fetch data.json (cache-buster)
const fetchData = async () => {
  const res = await fetch(`data.json?t=${Date.now()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`data.json HTTP ${res.status}`);
  return res.json();
};
