'use strict';
const $ = (s) => document.querySelector(s);
const state = { view: 'daily', demo: false, platform: 'all', report: null, keyword: '', busy: false };
const names = { daily: '每日精选', search: '关键词探索', settings: '账户与预算' };
const platformNames = { douyin: '抖音', xiaohongshu: '小红书', news: '大众事件', openai: 'GPT-5.1', research: '信息检索', system: '系统' };
function node(tag, text, className) { const el = document.createElement(tag); if (text != null) el.textContent = text; if (className) el.className = className; return el; }
function toast(text) { $('#toast').textContent = text; $('#toast').hidden = false; setTimeout(() => { $('#toast').hidden = true; }, 5000); }
function demoQuery() { return state.demo ? '?demo=1' : ''; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `请求失败 (${response.status})`);
  return result;
}
function busy(on) { state.busy = on; document.querySelectorAll('button, #demo-toggle').forEach(b => { b.disabled = on; }); $('#collect-button').textContent = on ? '处理中，请稍候…' : '✦ 生成今日精选'; }
async function operation(fn) { if (state.busy) return; busy(true); try { await fn(); } catch (err) { toast(err.message || '请求失败，请稍后重试'); } finally { busy(false); } }
async function loadStatus() {
  const status = await api('/api/status');
  $('#budget-text').textContent = `¥${status.reserved.toFixed(2)} / 30`;
  $('#budget').value = status.reserved;
  $('#today').textContent = new Date(status.now).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit' });
  $('#openai-state').textContent = `${status.openai.configured ? 'API key 已配置' : '尚未连接 OpenAI API'} · 模型 GPT-5.1${status.research_error ? ' · ' + status.research_error : ' · 生成今日精选可验证实际联网调用'}`;
  $('#gpt-cost').value = status.openai.cost;
  const subscription = status.openai.engine === 'codex';
  $('#engine-select').value = status.openai.engine;
  $('#api-config').hidden = subscription; $('#codex-panel').hidden = !subscription;
  $('#subscription-state').textContent = status.research_error || '本机 Codex 已以 ChatGPT 登录；生成精选后才能确认实际联网效果。';
  $('#codex-usage').textContent = `今日联网任务 ${status.codex_calls} / 8；订阅剩余额度需在 Codex 中查看。`;
  $('#stat-model').textContent = subscription ? 'Codex' : 'GPT-5.1';
  $('#model-description').textContent = subscription ? 'ChatGPT 订阅 · 默认可用模型' : '独立计费的 OpenAI API';
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
  $('#stat-total').replaceChildren(document.createTextNode(report.items.length.toString()), node('small', '条'));
  $('#stat-description').textContent = state.view === 'search' ? '当前关键词查询结果' : '今日最多 9 条，不满意单条替换';
  $('#result-count').textContent = `${items.length} 条素材`;
  $('#demo-banner').hidden = !state.demo;
  $('#coverage').textContent = report.coverage || '输入关键词，探索近七天相关内容。';
  $('#results-title').replaceChildren(document.createTextNode(state.view === 'search' ? (state.keyword ? `“${state.keyword}”的近七天线索` : '关键词查询结果') : '今日精选 · 4 + 3 + 2'), node('span', state.demo ? 'DEMO' : 'LIVE', 'badge'));
  $('#notice').textContent = (report.errors || []).map(e => `${platformNames[e.platform] || e.platform}：${e.message}`).join('\n');
  if (report.missing) { const missing = Object.entries(report.missing).filter(([, count]) => count > 0); if (missing.length) $('#notice').textContent += '\n当前缺额：' + missing.map(([p, count]) => `${platformNames[p]} ${count} 条`).join('、') + '；不使用无来源内容凑数。'; }
  if (report.cached) $('#notice').textContent += '\n当前使用六小时内的查询缓存，未产生新请求。';
  $('#notice').hidden = !$('#notice').textContent.trim();
  $('#updated').textContent = report.generated_at ? `记录时间 ${new Date(report.generated_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}` : '等待查询';
  const tbody = $('#results'); tbody.replaceChildren();
  for (const [index, item] of items.entries()) {
    const tr = node('tr'); tr.append(node('td', String(index + 1).padStart(2, '0'), 'number'));
    const topic = node('td', null, 'topic'); topic.append(node('strong', item.title), node('p', item.content)); tr.append(topic);
    const platform = node('td'); platform.append(node('span', item.platform_name, `tag ${item.platform}`)); tr.append(platform);
    const evidence = node('td', null, 'evidence'); evidence.append(node('strong', item.days >= 2 ? `持续出现 · ${item.days} 天` : item.kind), node('small', item.reason)); tr.append(evidence);
    const hook = node('td', item.hook, 'hook'); hook.append(node('span', state.view === 'daily' ? (state.demo ? '示例建议 · 需人工核实' : `${report.engine || '模型'}建议 · 需人工核实`) : '开头模板 · 需人工核实')); tr.append(hook);
    const source = node('td');
    if (item.url && /^https?:\/\//i.test(item.url)) {
      const a = node('a', state.demo ? '搜索 ↗' : '查看 ↗', 'source-link'); a.href = item.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; source.append(a);
    } else source.append(node('span', '暂无链接', 'source-missing'));
    if (state.view === 'daily' && item.slot) { const replace = node('button', '不满意 · 换一条', 'replace-button'); replace.addEventListener('click', () => operation(async () => { state.report = await api('/api/brief/replace' + demoQuery(), { slot: item.slot, expected_id: item.id }); render(); await loadStatus(); if (!state.report.errors.length) toast('已替换这一条，其他素材保持原样。'); })); source.append(replace); }
    tr.append(source); tbody.append(tr);
  }
  $('#table-wrap').hidden = !items.length;
  $('#empty').hidden = !!items.length;
  $('#empty-text').textContent = report.errors?.length ? '生成或查询未完成，请查看上方原因。不会用示例填充真实结果。' : state.view === 'search' ? '输入关键词开始查询。没有结果时，可调整关键词或检查数据接入状态。' : '先在账户与预算中连接 ChatGPT 订阅，再点击生成今日精选。';
  $('#try-demo').hidden = state.demo;
  $('#configure-account').hidden = state.demo || state.view !== 'daily';
}
async function loadDaily() { state.report = await api('/api/brief' + demoQuery()); state.keyword = ''; render(); }
async function view(name) {
  state.view = name;
  state.platform = 'all'; document.querySelectorAll('[data-platform]').forEach(b => b.classList.toggle('selected', b.dataset.platform === 'all'));
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
$('#demo-toggle').addEventListener('change', () => operation(async () => { state.demo = $('#demo-toggle').checked; await view(state.view); }));
$('#try-demo').addEventListener('click', () => operation(async () => { state.demo = true; $('#demo-toggle').checked = true; if (state.view === 'search') { $('#keyword').value = 'KPL'; await runSearch(); } else await loadDaily(); }));
$('#collect-button').addEventListener('click', () => operation(async () => { toast('正在联网搜找并整理，可能需要几分钟，请保留页面。'); state.report = await api('/api/brief/generate' + demoQuery(), {}); render(); await loadStatus(); }));
$('#configure-account').addEventListener('click', () => operation(() => view('settings')));
async function runSearch() { const keyword = $('#keyword').value.trim(); if (!keyword) return toast('请输入关键词'); state.keyword = keyword; state.report = await api('/api/search' + demoQuery(), { keyword }); render(); await loadStatus(); }
$('#search-form').addEventListener('submit', e => { e.preventDefault(); operation(runSearch); });
document.querySelectorAll('[data-keyword]').forEach(el => el.addEventListener('click', () => { $('#keyword').value = el.dataset.keyword; operation(runSearch); }));
$('#export-button').addEventListener('click', () => operation(async () => {
  if (state.view === 'search' && !state.keyword) return toast('请先查询关键词');
  const params = new URLSearchParams(); if (state.demo) params.set('demo', '1'); if (state.view === 'search') params.set('keyword', state.keyword);
  const response = await fetch((state.view === 'daily' ? '/api/brief/export?' : '/api/export?') + params); if (!response.ok) throw new Error((await response.json()).error || '导出失败');
  const url = URL.createObjectURL(await response.blob()); const link = node('a'); link.href = url; link.download = `热点素材-${state.demo ? '示例-' : ''}${new Date().toISOString().slice(0, 10)}.xlsx`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(state.view === 'daily' ? '已导出当前入选素材及采集说明。' : '已导出完整查询结果及采集说明。');
}));
$('#account-form').addEventListener('submit', e => { e.preventDefault(); operation(async () => { try { await api('/api/settings/openai', { api_key: $('#openai-key').value.trim(), cost: $('#gpt-cost').value }); toast('本机配置已保存；可检查 API 连接，再生成今日精选。'); await loadStatus(); } finally { $('#openai-key').value = ''; } }); });
$('#check-openai').addEventListener('click', () => operation(async () => { const result = await api('/api/openai/check', {}); toast(result.message); }));
$('#clear-openai').addEventListener('click', () => operation(async () => { await api('/api/settings/openai', { clear: true }); $('#openai-key').value = ''; await loadStatus(); toast('已移除本机保存的密钥；环境变量配置仍需从系统中移除。'); }));
$('#engine-select').addEventListener('change', () => operation(async () => { await api('/api/settings/openai', { engine: $('#engine-select').value }); await loadStatus(); }));
$('#connect-codex').addEventListener('click', () => operation(async () => { const result = await api('/api/codex/connect', {}); toast(result.message); }));
$('#check-codex').addEventListener('click', () => operation(async () => { const result = await api('/api/research/check', {}); toast(result.message); await loadStatus(); }));
$('#refresh-account').addEventListener('click', () => operation(loadStatus));
operation(async () => { await loadStatus(); await loadDaily(); });
setInterval(() => { if (!state.busy && !state.demo && state.view === 'daily') operation(loadDaily); }, 60000);
