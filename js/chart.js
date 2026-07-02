// ═══ CHART MODULE — TradingView OANDA:XAUUSD embed ═══
const renderChart = () => {
  const frame = $('#chart-frame');
  if (!frame || frame.dataset.rendered === '1') return;
  frame.dataset.rendered = '1';
  const iframe = document.createElement('iframe');
  iframe.src = 'https://s.tradingview.com/widgetembed/?frameElementId=xau-chart&symbol=OANDA%3AXAUUSD&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=0f0f13&studies=[]&theme=dark&style=1&timezone=Europe%2FBudapest&withdateranges=1&hide_volume=0&locale=hu';
  iframe.style.width = '100%';
  iframe.style.height = '100%';
  iframe.style.minHeight = '480px';
  iframe.style.border = '0';
  iframe.setAttribute('allowfullscreen', '');
  iframe.setAttribute('allowtransparency', 'true');
  frame.appendChild(iframe);
};

const renderChartLevels = (levels) => {
  const host = $('#chart-levels');
  host.innerHTML = '';
  const mk = (label, field) => {
    if (!field || field.value == null) return null;
    return el('span', { class: 'level-chip', title: field.source_label || '' },
      el('strong', {}, label),
      String(field.value));
  };
  const chips = [
    mk('PDH', levels.pdh),
    mk('PDL', levels.pdl),
    mk('Open', levels.daily_open),
    mk('AsiaH', levels.asia_high),
    mk('AsiaL', levels.asia_low),
    mk('Psych', levels.psych_level),
  ].filter(Boolean);
  chips.forEach(c => host.appendChild(c));
};
