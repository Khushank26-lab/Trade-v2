const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n, d = 2) => (n == null || isNaN(n)) ? '–' : Number(n).toLocaleString('en-IN', {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = x => x == null ? '–' : (x * 100).toFixed(0) + '%';
const INDICES = {'^NSEI': 'Nifty 50', '^BSESN': 'Sensex', '^INDIAVIX': 'India VIX'};
let shown = [];

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(m); }
  return r.json();
}

async function loadStatus() {
  try {
    const s = await api('/api/status');
    $('#status').textContent = s.ready
      ? `Data as of ${s.asof} · ${s.stocks_loaded.toLocaleString('en-IN')} stocks analysed from ${s.universe.toLocaleString('en-IN')} NSE/BSE listings · Market ${s.market.open ? 'OPEN' : 'CLOSED'} (${s.market.ist} IST)`
      : 'Initial data load in progress (first run takes 30-60+ minutes). Please check back soon.';
  } catch (e) { $('#status').textContent = 'Server unavailable.'; }
}

$('#f').addEventListener('submit', async ev => {
  ev.preventDefault();
  const n = +$('#tf').value, days = $('#unit').value === 'weeks' ? n * 5 : n;
  const q = new URLSearchParams({target: $('#target').value, days, stop: $('#stop').value, mode: $('#mode').value,
    min_hit: $('#min_hit').value || 0, exchange: $('#exchange').value, capital: $('#capital').value, risk: $('#risk').value,
    require_fund: $('#require_fund').checked, limit: 15});
  $('#go').disabled = true; $('#go').textContent = 'Scanning thousands of stocks...';
  $('#results').innerHTML = ''; $('#banner').innerHTML = ''; $('#funnel').innerHTML = '';
  try { render(await api('/api/screen?' + q), days); }
  catch (e) { $('#banner').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; }
  $('#go').disabled = false; $('#go').textContent = 'Find best bullish stocks';
});

function render(r, days) {
  const f = r.funnel, p = r.params, rm = r.removed || {};
  $('#funnel').innerHTML = `<div class="funnel"><span>Listings ${f.universe.toLocaleString('en-IN')}</span><span>With history ${f.with_history.toLocaleString('en-IN')}</span>
    <span>Liquid ${f.liquid.toLocaleString('en-IN')}</span><span>Score pass ${f.score_pass}</span><span>Feasible for ${p.target}% in ${days}d ${f.feasible}</span>
    <span>Removed: weak fundamentals ${rm.weak_fundamentals || 0}, red-flag news ${rm.red_flag_news || 0}</span></div>`;
  const best = r.best_p_est, pool = r.pool;
  let msg = `Across all liquid stocks, this setup type reached <b>+${p.target}%</b> within <b>${days} trading days</b> (before a -${p.stop}% stop) in <b>${pct(pool.p)}</b> of ${pool.n.toLocaleString('en-IN')} past signals.`;
  if (best != null) msg += ` Best current estimate: <b>${pct(best)}</b>.`;
  let cls = 'banner';
  if (!r.met_min_hit) { cls += ' warn'; msg = `<b>No stock meets your ${p.min_hit}% minimum.</b> Historical data shows hit rates this high are essentially never achieved for these targets. Showing the closest matches instead.<br>` + msg; }
  else if (!r.ranked.length) { cls += ' warn'; msg = '<b>No stock qualifies today.</b> That is a valid result: waiting is a position. Try Relaxed mode, a lower target or a longer time frame.<br>' + msg; }
  $('#banner').innerHTML = `<div class="${cls}">${msg}</div>`;
  shown = r.ranked.map(c => c.ticker);
  $('#results').innerHTML = r.ranked.map((c, i) => card(c, i + 1, days)).join('');
  document.querySelectorAll('details[data-t]').forEach(d => d.addEventListener('toggle', () => d.open && spark(d)));
  pollLive();
}

function chips(c) {
  const out = [];
  const fv = c.fund && c.fund.verdict;
  out.push(fv === 'strong' ? `<span class="b ok">Fundamentals strong (${c.fund.passed}/${c.fund.available})</span>` :
           fv === 'weak' ? `<span class="b bad">Fundamentals weak</span>` : `<span class="b warn">Fundamentals unverified</span>`);
  if (c.news) out.push(c.news.count ? `<span class="b ${c.news.red_flag ? 'bad' : (c.news.net ?? 0) >= 0 ? 'ok' : 'warn'}">News ${c.news.red_flag ? 'RED FLAG' : 'net ' + (c.news.net ?? '–')} (${c.news.count})</span>` : `<span class="b warn">No news data</span>`);
  c.setups.forEach(s => out.push(`<span class="b ok">${esc(s)}</span>`));
  return out.join('');
}

function card(c, rank, days) {
  const checks = c.flags.map(x => `<li class="${x.ok ? 'y' : 'n'}">${esc(x.name)}</li>`).join('');
  const fchecks = (c.fund && c.fund.checks || []).map(x => `<li class="${x.ok === null ? 'u' : x.ok ? 'y' : 'n'}">${esc(x.name)}${x.value ? ' – ' + esc(x.value) : ''}</li>`).join('');
  const heads = (c.news && c.news.headlines || []).map(h => `<li class="u">${esc(h)}</li>`).join('');
  return `<div class="card" data-ticker="${esc(c.ticker)}" data-entry="${c.entry}" data-t2="${c.t2}" data-stop="${c.stop}">
    <div class="top"><div><div class="sym">#${rank} ${esc(c.symbol)} <span class="b">${esc(c.exchange)}</span></div><div class="nm">${esc(c.name)}</div></div>
      <div class="px"><b class="lp">${fmt(c.price)}</b><div class="lc muted">last close</div></div></div>
    <div class="badges">${chips(c)}</div>
    <div class="stats">
      <div class="stat"><small>Past hit rate (est.)</small><b>${pct(c.p_est)}</b><div class="bar"><i style="width:${c.p_est * 100}%"></i></div></div>
      <div class="stat"><small>Conservative (80% low)</small><b>${pct(c.p_low)}</b></div>
      <div class="stat"><small>This stock: ${c.k}/${c.n} signals</small><b>${c.p_stock == null ? '–' : pct(c.p_stock)}</b></div>
      <div class="stat"><small>Tech score</small><b>${c.score}/${c.npts}</b></div>
    </div>
    <div class="stats">
      <div class="stat"><small>Entry</small><b>${fmt(c.entry)}</b></div>
      <div class="stat"><small>Stop</small><b>${fmt(c.stop)}</b></div>
      <div class="stat"><small>Target 1 / 2</small><b>${fmt(c.t1)} / ${fmt(c.t2)}</b></div>
      <div class="stat"><small>Qty (risk-sized)</small><b>${c.qty.toLocaleString('en-IN')}</b></div>
      <div class="stat"><small>Position / Risk</small><b>${fmt(c.position_value, 0)} / ${fmt(c.risk_amount, 0)}</b></div>
      <div class="stat"><small>Reward:Risk</small><b>${c.rr}</b></div>
    </div>
    <details data-t="${esc(c.ticker)}"><summary>Chart, checks &amp; details</summary>
      <svg class="spark" viewBox="0 0 300 90" preserveAspectRatio="none"></svg>
      <div class="muted">RSI ${c.rsi} · ADX ${c.adx} · ATR ${c.atr_pct}% · 3M return ${c.ret3}% (vs index ${c.rs >= 0 ? '+' : ''}${c.rs}%) · ${c.dist52}% below 52W high</div>
      <ul class="fl">${checks}</ul>
      ${fchecks ? '<b>Fundamentals &amp; growth</b><ul class="fl">' + fchecks + '</ul>' : ''}
      ${heads ? '<b>Latest headlines</b><ul class="fl">' + heads + '</ul>' : ''}
      <div class="muted">Hit rate = share of past setups of this kind that touched +target before the stop within the time frame, blended with the all-stock average (more history = less blending). Fundamentals/news are not part of the past hit rate (no point-in-time data).</div>
    </details></div>`;
}

async function spark(d) {
  const svg = d.querySelector('svg'); if (svg.dataset.done) return;
  try {
    const s = await api('/api/stock/' + encodeURIComponent(d.dataset.t));
    const all = [...s.close, ...s.ema20, ...s.ema50], lo = Math.min(...all), hi = Math.max(...all), n = s.close.length;
    const pts = a => a.map((v, i) => `${(i / (n - 1) * 300).toFixed(1)},${(88 - (v - lo) / (hi - lo || 1) * 84).toFixed(1)}`).join(' ');
    svg.innerHTML = `<polyline fill="none" stroke="#4c8dff" stroke-width="1.6" points="${pts(s.close)}"/><polyline fill="none" stroke="#e3b341" stroke-width="1" points="${pts(s.ema20)}"/><polyline fill="none" stroke="#9aa6bd" stroke-width="1" points="${pts(s.ema50)}"/>`;
    svg.dataset.done = 1;
  } catch (e) {}
}

async function pollLive() {
  const list = [...new Set([...Object.keys(INDICES), ...shown])];
  try {
    const r = await api('/api/live?tickers=' + encodeURIComponent(list.join(',')));
    const q = r.quotes;
    $('#ticker').innerHTML = Object.entries(INDICES).map(([t, n]) => q[t] && q[t].price ? `<span>${n} <b>${fmt(q[t].price)}</b> <span class="${q[t].chg >= 0 ? 'up' : 'dn'}">${q[t].chg >= 0 ? '+' : ''}${fmt(q[t].chg)}%</span></span>` : '').join('') + `<span>${r.market.open ? 'Market OPEN' : 'Market CLOSED'}</span>`;
    document.querySelectorAll('.card').forEach(el => {
      const x = q[el.dataset.ticker]; if (!x || !x.price) return;
      el.querySelector('.lp').textContent = fmt(x.price);
      const lc = el.querySelector('.lc'); lc.className = 'lc ' + (x.chg >= 0 ? 'up' : 'dn');
      const prog = (x.price - +el.dataset.entry) / (+el.dataset.t2 - +el.dataset.entry) * 100;
      lc.textContent = `${x.chg >= 0 ? '+' : ''}${fmt(x.chg)}% today · ${prog.toFixed(0)}% of way to target` + (x.price <= +el.dataset.stop ? ' · BELOW STOP' : '');
    });
  } catch (e) {}
}

loadStatus(); pollLive(); setInterval(pollLive, 30000); setInterval(loadStatus, 300000);
