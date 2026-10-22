'use strict';
const $ = (s) => document.querySelector(s);
const state = { view: 'daily', demo: false, platform: 'all', report: null, keyword: '', busy: false };
const names = { daily: '每日热点', search: '关键词探索', settings: '数据与预算' };
function node(tag, text, className) { const el = document.createElement(tag); if (text != null) el.textContent = text; if (className) el.className = className; return el; }
function toast(text) { $('#toast').textContent = text; $('#toast').hidden = false; setTimeout(() => { $('#toast').hidden = true; }, 5000); }
function demoQuery() { return state.demo ? '?demo=1' : ''; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `请求失败 (${response.status})`);
  return result;
}
function busy(on) { state.busy = on; document.querySelectorAll('button, #demo-toggle').forEach(b => { b.disabled = on; }); $('#collect-button').textContent = on ? '处理中…' : '↻ 采集今日榜单'; }
async function operation(fn) { if (state.busy) return; busy(true); try { await fn(); } catch (err) { toast(err.message || '请求失败，请稍后重试'); } finally { busy(false); } }
async function loadStatus() {
  const status = await api('/api/status');
  $('#budget-text').textContent = `¥${status.reserved.toFixed(2)} / 30`;
  $('#budget').value = status.reserved;
  $('#today').textContent = new Date(status.now).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit' });
  const details = $('#source-details'); details.replaceChildren();
  for (const source of Object.values(status.sources)) {
    const card = node('div', null, 'source-card'); card.append(node('h3', source.name));
    for (const [label, error] of [['每日榜单', source.hot], ['关键词搜索', source.search]]) {
      const line = node('p'); line.append(node('b', `${label} · `), document.createTextNode(error || '已配置，真实可用性需实际请求验证')); card.append(line);
    }
    details.append(card);
  }
}
function render() {
  const report = state.report || { items: [], errors: [] };
  let items = report.items.filter(i => state.platform === 'all' || i.platform === state.platform);
  if ($('#repeat-filter').checked) items = items.filter(i => i.days >= 2);
  $('#stat-total').replaceChildren(document.createTextNode(report.items.length.toString()), node('small', '条'));
  $('#stat-repeat').replaceChildren(document.createTextNode(report.items.filter(i => i.days >= 2).length.toString()), node('small', '条'));
  $('#result-count').textContent = `${items.length} 条素材`;
  $('#demo-banner').hidden = !state.demo;
  $('#coverage').textContent = report.coverage || '输入关键词，探索近七天相关内容。';
  $('#results-title').replaceChildren(document.createTextNode(state.view === 'search' ? (state.keyword ? `“${state.keyword}”的近七天线索` : '关键词查询结果') : '近七天素材雷达'), node('span', state.demo ? 'DEMO' : 'LIVE', 'badge'));
  $('#notice').textContent = (report.errors || []).map(e => `${e.platform === 'douyin' ? '抖音' : '小红书'}：${e.message}`).join('\n');
  if (report.cached) $('#notice').textContent += '\n当前使用六小时内的查询缓存，未产生新请求。';
  $('#notice').hidden = !$('#notice').textContent.trim();
  $('#updated').textContent = report.generated_at ? `记录时间 ${new Date(report.generated_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}` : '等待查询';
  const tbody = $('#results'); tbody.replaceChildren();
  for (const [index, item] of items.entries()) {
    const tr = node('tr'); tr.append(node('td', String(index + 1).padStart(2, '0'), 'number'));
    const topic = node('td', null, 'topic'); topic.append(node('strong', item.title), node('p', item.content)); tr.append(topic);
    const platform = node('td'); platform.append(node('span', item.platform_name, `tag ${item.platform}`)); tr.append(platform);
    const evidence = node('td', null, 'evidence'); evidence.append(node('strong', item.days >= 2 ? `持续出现 · ${item.days} 天` : item.kind), node('small', item.reason)); tr.append(evidence);
    const hook = node('td', item.hook, 'hook'); hook.append(node('span', '开头模板 · 需人工核实')); tr.append(hook);
    const source = node('td');
    if (item.url && /^https?:\/\//i.test(item.url)) {
      const a = node('a', state.demo ? '搜索 ↗' : '查看 ↗', 'source-link'); a.href = item.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; source.append(a);
    } else source.append(node('span', '暂无链接', 'source-missing'));
    tr.append(source); tbody.append(tr);
  }
  $('#table-wrap').hidden = !items.length;
  $('#empty').hidden = !!items.length;
  $('#empty-text').textContent = report.status === 'error' ? '采集或查询未完成，请查看上方原因。不会用示例填充真实结果。' : state.view === 'search' ? '输入关键词开始查询。没有结果时，可调整关键词或检查数据接入状态。' : '尚无符合条件的记录。可体验示例，或接入数据源后采集。';
  $('#try-demo').hidden = state.demo;
}
async function loadDaily() { state.report = await api('/api/report' + demoQuery()); state.keyword = ''; render(); }
async function view(name) {
  state.view = name;
  document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('active', el.dataset.view === name));
  $('#breadcrumb').textContent = names[name];
  $('#page-title').textContent = name === 'daily' ? '捕捉热点，找到好开头。' : name === 'search' ? '你关心的话题，都有线索。' : '每一条线索，来源清楚。';
  $('#search-panel').hidden = name !== 'search'; $('#settings-panel').hidden = name !== 'settings'; $('#results-panel').hidden = name === 'settings'; $('#collect-button').hidden = name !== 'daily';
  if (name === 'daily') await loadDaily();
  if (name === 'search') { state.report = null; state.keyword = ''; render(); $('#keyword').focus(); }
  if (name === 'settings') await loadStatus();
}
document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click', () => operation(() => view(el.dataset.view))));
document.querySelectorAll('[data-platform]').forEach(el => el.addEventListener('click', () => { state.platform = el.dataset.platform; document.querySelectorAll('[data-platform]').forEach(b => b.classList.toggle('selected', b === el)); render(); }));
$('#repeat-filter').addEventListener('change', render);
$('#demo-toggle').addEventListener('change', () => operation(async () => { state.demo = $('#demo-toggle').checked; await view(state.view); }));
$('#try-demo').addEventListener('click', () => operation(async () => { state.demo = true; $('#demo-toggle').checked = true; if (state.view === 'search') { $('#keyword').value = 'KPL'; await runSearch(); } else await loadDaily(); }));
$('#collect-button').addEventListener('click', () => operation(async () => { state.report = await api('/api/collect' + demoQuery(), {}); render(); await loadStatus(); }));
async function runSearch() { const keyword = $('#keyword').value.trim(); if (!keyword) return toast('请输入关键词'); state.keyword = keyword; state.report = await api('/api/search' + demoQuery(), { keyword }); render(); await loadStatus(); }
$('#search-form').addEventListener('submit', e => { e.preventDefault(); operation(runSearch); });
document.querySelectorAll('[data-keyword]').forEach(el => el.addEventListener('click', () => { $('#keyword').value = el.dataset.keyword; operation(runSearch); }));
$('#export-button').addEventListener('click', () => operation(async () => {
  if (state.view === 'search' && !state.keyword) return toast('请先查询关键词');
  const params = new URLSearchParams(); if (state.demo) params.set('demo', '1'); if (state.view === 'search') params.set('keyword', state.keyword);
  const response = await fetch('/api/export?' + params); if (!response.ok) throw new Error((await response.json()).error || '导出失败');
  const url = URL.createObjectURL(await response.blob()); const link = node('a'); link.href = url; link.download = `热点素材-${state.demo ? '示例-' : ''}${new Date().toISOString().slice(0, 10)}.xlsx`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Excel 已导出，包含完整查询结果及采集说明。');
}));
operation(async () => { await loadStatus(); await loadDaily(); });
