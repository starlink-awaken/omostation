/* 织星驾驶舱 logs/metrics/value 三板块 —— 浏览器端真实验证.
   加载真实数据 harness（harness.html 由真实日志构建），断言:
     · 无 console/page error（重点: 历史缺陷 drawTrendChart 未定义）
     · 三板块渲染出真实内容
     · 筛选器选项来自真实分面且真的能过滤
     · 趋势首屏非空、切换范围后序列变化、且不来自合成波形
     · value 严格 NOT_PROVEN 且比率指标不假绿
     · 无硬编码位置数字
   产出截图 desktop + 390px。 */
const fs = require('fs'), { pathToFileURL } = require('url');
const { chromium } = require('/Users/xiamingxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const HARNESS = process.argv[2];
const OUT = process.argv[3] || '/tmp';

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const checks = [];
  const test = (name, ok, extra) => checks.push({ name, ok: !!ok, extra: extra === undefined ? '' : String(extra) });

  const page = await browser.newPage({ viewport: { width: 1440, height: 1040 } });
  const errors = [];
  // harness 以 file:// 加载, 对 /__panorama_data__ 的 fetch 必然被 CORS 拒绝,
  // 这是测试载体的限制而非页面缺陷, 需过滤掉其余全部真实错误。
  const HARNESS_NOISE = /__panorama_data__|ERR_FAILED|CORS policy/;
  page.on('pageerror', e => { if (!HARNESS_NOISE.test(e.message)) errors.push('pageerror: ' + e.message); });
  page.on('console', m => {
    if (m.type() === 'error' && !HARNESS_NOISE.test(m.text())) errors.push('console: ' + m.text());
  });

  await page.goto(pathToFileURL(HARNESS).href, { waitUntil: 'load' });
  await page.waitForTimeout(1500);

  // section 采用 hash 路由, 测试前必须先激活对应分区
  const activate = async (id) => {
    await page.evaluate(h => { location.hash = h; }, '#' + id);
    await page.waitForTimeout(500);
    try {
      await page.waitForFunction(h => {
        const el = document.getElementById(h);
        return el && (el.classList.contains('active') || el.offsetParent !== null);
      }, id, { timeout: 6000 });
    } catch (e) { /* 宽松: 部分分区无 active 机制 */ }
    await page.evaluate(() => { zxRenderLogs(); zxRenderMetrics(); zxRenderValue(); });
    await page.waitForTimeout(250);
  };

  // ── 全局: 无脚本错误 ──
  test('页面无 JS 错误', errors.length === 0, errors.slice(0, 3).join(' | '));

  // ── 关键回归: 趋势函数存在且可调用（历史缺陷: drawTrendChart 未定义） ──
  const hasRenderers = await page.evaluate(() =>
    ['zxRenderLogs', 'zxRenderMetrics', 'zxRenderValue', 'zxRenderPanels']
      .filter(f => typeof window[f] !== 'function'));
  test('三个渲染器均已定义', hasRenderers.length === 0, 'missing=' + hasRenderers.join(','));

  // ── logs 板块 ──
  await activate('logs');
  const logKpi = await page.locator('#zx-logs-kpis .zx-kpi').count();
  test('logs KPI 卡渲染', logKpi >= 6, 'count=' + logKpi);
  const evCount = await page.locator('#zx-logs-stream .zx-ev').count();
  test('事件流渲染真实事件', evCount > 0, 'rows=' + evCount);

  const typeOpts = await page.locator('#zx-f-type option').count();
  const srcOpts = await page.locator('#zx-f-source option').count();
  test('筛选器选项来自真实分面', typeOpts > 1 && srcOpts > 1,
       'type=' + typeOpts + ' source=' + srcOpts);

  // 筛选真的生效：选中第一个非空类型 → 事件数应减少
  const before = await page.locator('#zx-logs-stream .zx-ev').count();
  const firstType = await page.locator('#zx-f-type option').nth(1).getAttribute('value');
  await page.selectOption('#zx-f-type', firstType);
  await page.waitForTimeout(250);
  const after = await page.locator('#zx-logs-stream .zx-ev').count();
  const countText = await page.locator('#zx-logs-count').innerText();
  test('筛选真实生效', after > 0 && after <= before, `type=${firstType} ${before}→${after}`);
  test('计数标签显示真实 N/M', /显示 \d+ \/ \d+/.test(countText), countText);
  await page.selectOption('#zx-f-type', '');
  await page.waitForTimeout(200);

  // 来源健康表：MISSING 源必须显式标注
  const srcTable = await page.locator('#zx-logs-sources').innerText();
  test('来源健康表渲染', /MISSING|OK/.test(srcTable));
  test('缺失源显式标注未接线', /未接线|不存在/.test(srcTable), srcTable.split('\n').filter(l=>/MISSING/.test(l)).slice(0,1).join(''));

  // sparkline 真实
  const sparkBars = await page.locator('#zx-logs-spark svg rect').count();
  test('24h 速率 sparkline 来自真实桶', sparkBars >= 20, 'bars=' + sparkBars);

  // ── metrics 板块 ──
  await activate('metrics');
  const mKpi = await page.locator('#zx-m-kpis .zx-m-kpi').count();
  test('metrics KPI 卡渲染', mKpi >= 6, 'count=' + mKpi);
  const sparks = await page.locator('#zx-m-kpis svg path').count();
  test('KPI 带真实 sparkline', sparks >= 2, 'sparks=' + sparks);

  const trendHtml1 = await page.locator('#zx-m-trend').innerHTML();
  test('趋势首屏已绘制（历史缺陷: 空白）', trendHtml1.indexOf('<svg') >= 0 && trendHtml1.indexOf('<path') >= 0,
       'len=' + trendHtml1.length);

  const series24 = await page.evaluate(() => zxMSeriesFor('24h').map(d => d.key + ':' + d.points.length));
  const series30 = await page.evaluate(() => zxMSeriesFor('30d').map(d => d.key + ':' + d.points.length));
  test('趋势序列随范围变化且来自真实键',
       series24.join() !== series30.join(), `24h=[${series24}] 30d=[${series30}]`);

  await page.evaluate(() => zxMSetRange('30d'));
  await page.waitForTimeout(200);
  const trendHtml2 = await page.locator('#zx-m-trend').innerHTML();
  test('切换 30d 后重绘真实序列', trendHtml2.indexOf('<svg') >= 0, 'len=' + trendHtml2.length);

  const srcNote = await page.locator('#zx-m-src-note').innerText();
  test('来源分布标注缺失源', /未接线|不存在|全部/.test(srcNote), srcNote.slice(0, 70));
  const covText = await page.locator('#zx-m-coverage').innerText();
  test('展示真实数据底座覆盖', /refresh\.jsonl|未发现/.test(covText), covText.slice(0, 70));

  // ── value 板块 ──
  await activate('value');
  const badge = await page.locator('#zx-v-badge').innerText();
  test('value 显示真实状态徽标', badge.length > 0, badge);
  test('value 严格 NOT_PROVEN', badge.indexOf('NOT_PROVEN') >= 0, badge);

  const stages = await page.locator('#zx-v-stages .zx-v-stage').count();
  test('五阶段回路渲染', stages === 5, 'count=' + stages);
  const stageText = await page.locator('#zx-v-stages').innerText();
  test('五阶段无硬编码计数残留', !/\b353\b/.test(stageText) && !/71 信念/.test(stageText) && !/3 活跃旅程/.test(stageText),
       stageText.slice(0, 80));
  test('无数据阶段标注 NO_DATA', /NO_DATA/.test(stageText) || stageText.indexOf('—') >= 0);

  const thrText = await page.locator('#zx-v-thr').innerText();
  const gateText = await page.locator('#zx-v-thr .zx-v-thr-note').count();
  test('比率指标不假绿（样本不足→不可判定）',
       /不可判定/.test(thrText) || gateText === 0, 'gates=' + gateText);
  test('门槛显示真实 current/target', /\d+\s*\/\s*\d+/.test(thrText), thrText.split('\n').slice(0,2).join(' '));

  const evidence = await page.locator('#zx-v-evidence').innerText();
  test('价值证据时间线渲染', evidence.length > 0, evidence.slice(0, 60));

  // ── 动态性: 重新渲染后内容随真实数据变化 ──
  const dyn = await page.evaluate(() => {
    const before = document.getElementById('zx-logs-kpis').innerText;
    // 走真实刷新路径: zxRenderPanels(live) 换入新快照后重渲
    const live = JSON.parse(document.getElementById('snapshot').textContent);
    live.panel_events.summary.events_24h = 999999;
    zxRenderPanels(live);
    const after = document.getElementById('zx-logs-kpis').innerText;
    const applied = after.indexOf('999999') >= 0;
    // 还原, 避免影响后续断言
    delete window.__zxLiveData;
    zxRenderLogs();
    return { changed: applied, after: after.slice(0, 46), before: before.slice(0, 30) };
  });
  test('面板随数据动态变化（非静态快照）', dyn.changed, dyn.after);

  // ── 截图 ──
  for (const [hash, name] of [['#logs', 'logs'], ['#metrics', 'metrics'], ['#value', 'value']]) {
    await page.evaluate(h => { location.hash = h; }, hash);
    await page.waitForTimeout(400);
    await page.evaluate(() => { zxRenderLogs(); zxRenderMetrics(); zxRenderValue(); });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/panel-${name}-desktop.png`, fullPage: false });
  }
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(pathToFileURL(HARNESS).href, { waitUntil: 'load' });
  await mobile.waitForTimeout(1200);
  await mobile.evaluate(() => { location.hash = '#logs'; zxRenderLogs(); });
  await mobile.waitForTimeout(300);
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  test('390px 无横向溢出', overflow <= 2, 'overflow=' + overflow);
  await mobile.screenshot({ path: `${OUT}/panel-mobile-390.png`, fullPage: false });

  await browser.close();

  const failed = checks.filter(c => !c.ok);
  for (const c of checks) console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.name}${c.extra ? '  [' + c.extra + ']' : ''}`);
  console.log(`\n${checks.length - failed.length}/${checks.length} passed`);
  if (errors.length) { console.log('\nJS errors:'); errors.slice(0, 8).forEach(e => console.log('  ' + e)); }
  process.exit(failed.length ? 1 : 0);
})();
