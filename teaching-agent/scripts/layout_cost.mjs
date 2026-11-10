/**
 * P2-9 诊断：流式跟随期间，我们到底向浏览器要了几次布局？
 *
 * 背景：以前同一个 chunk 会走两条跟随路径 —— 打字机的 rAF 里滚一次，messages 的
 * layout effect 里又滚一次，每次都要读 scrollHeight（读它 = 向浏览器要一次布局）。
 *
 * 剧本：合成流每 25ms 吐一块正文（不花 token），期间保持在底部跟随，
 * 数 `__MN_FOLLOW__`（跟随调用）、`__MN_COMMIT__`（渲染次数）、
 * scrollHeight 读取次数与 CDP 的 LayoutCount / LayoutDuration。
 *
 *   node scripts/layout_cost.mjs
 *
 * 注意：本脚本是**诊断**，不是性能门禁。实测连跑三次 LayoutCount 213~221、
 * LayoutDuration 88~110ms，差异都在噪声内 —— 被删掉的那次重复读读到的是
 * 已经算好的布局，本来就不贵（详见 docs/ITERATION_1_2.md 第八节）。
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = Number(process.env.CDP_PORT || 9334)
const CHUNKS = 120
const INTERVAL = 25
const EDGE = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p)) || 'msedge'

mkdirSync('docs/shots', { recursive: true })

const proc = spawn(EDGE, [
  '--headless=new',
  `--remote-debugging-port=${PORT}`,
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-gpu',
  '--window-size=1440,960',
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-layout',
  APP,
], { stdio: 'ignore' })

let ws
let seq = 0
const pending = new Map()

function send(method, params = {}) {
  const id = ++seq
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
}

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
      const page = list.find((t) => t.type === 'page')
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('连不上 Edge 调试端口')
}

async function evaluate(expression) {
  const res = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true })
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text + ' ' + (res.exceptionDetails.exception?.description || ''))
  return res.result?.value
}

async function waitFor(expression, label, timeoutMs = 60000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const value = await evaluate(expression).catch(() => null)
    if (value) return value
    await sleep(200)
  }
  throw new Error(`等待超时：${label}`)
}

async function metrics() {
  const res = await send('Performance.getMetrics')
  const out = {}
  for (const m of res.metrics) out[m.name] = m.value
  return out
}

const results = []
function check(label, ok, detail = '') {
  results.push({ label, ok, detail })
  console.log(`${ok ? '✅' : '❌'} ${label}${detail ? ' — ' + detail : ''}`)
}

// 合成流：每 25ms 推一块，共 CHUNKS 块；最后补 quiz_pack + done
const STUB = `(() => {
  const chunks = ${CHUNKS};
  const interval = ${INTERVAL};
  const realFetch = window.fetch.bind(window);
  window.__MN_CHUNKS__ = 0;
  window.fetch = function (url, init) {
    const target = typeof url === 'string' ? url : (url && url.url) || '';
    if (target.indexOf('/api/teach_proxy/stream') === -1) return realFetch(url, init);
    const enc = new TextEncoder();
    const send = (obj) => 'data: ' + JSON.stringify(obj) + '\\n\\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(enc.encode(send({ type: 'meta', session_id: 'layout-cost', kp_name: '导数定义与可导性' })));
        let i = 0;
        const timer = setInterval(() => {
          i += 1;
          controller.enqueue(enc.encode(send({
            type: 'content',
            text: '第 ' + i + ' 块：把平均变化率的分子分母同时缩小到零附近，再看能不能把极限移进括号里。\\n\\n',
          })));
          window.__MN_CHUNKS__ = i;
          if (i >= chunks) {
            clearInterval(timer);
            controller.enqueue(enc.encode(send({
              type: 'quiz_pack',
              quiz_pack: ${JSON.stringify([
                { kind: 'choice', stem: '合成题 1', options: ['A', 'B', 'C', 'D'], answer: 'A', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'easy' },
                { kind: 'fill', stem: '合成题 2', options: [], answer: '1', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'medium' },
                { kind: 'fill', stem: '合成题 3', options: [], answer: '2', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'hard' },
              ])},
              kp_id: 'l03-b01-k01',
              kp_name: '导数定义与可导性',
            })));
            controller.enqueue(enc.encode(send({
              type: 'done', status: 'awaiting_answer', session_id: 'layout-cost', round: 0, max_rounds: 3, ttft_ms: 40,
            })));
            controller.close();
          }
        }, interval);
      },
    });
    return Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }));
  };
  return true;
})()`

// 埋点：数「聊天容器 scrollHeight 被读了几次」。
// 读 scrollHeight 就是向浏览器要一次布局（DOM 刚被 React 改过时，等于强制同步回流），
// 这是 P2-9 真正要压的东西；LayoutCount 只能看到「实际做了几次布局」，
// 有缓存/批处理干扰，噪声大。
const READ_PROBE = `(() => {
  window.__MN_SH_READS__ = 0;
  window.__MN_SH_STACKS__ = [];
  window.__MN_SH_BUCKETS__ = {};
  const desc = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollHeight');
  Object.defineProperty(Element.prototype, 'scrollHeight', {
    configurable: true,
    get() {
      if (this && this.classList && this.classList.contains('paper-canvas')) {
        window.__MN_SH_READS__ = (window.__MN_SH_READS__ || 0) + 1;
        const lines = (new Error().stack || '').split('\\n');
        const key = (lines[2] || '') + ' << ' + (lines[3] || '');
        window.__MN_SH_BUCKETS__[key] = (window.__MN_SH_BUCKETS__[key] || 0) + 1;
        if (window.__MN_SH_STACKS__.length < 6) {
          window.__MN_SH_STACKS__.push(lines.slice(1, 5).join(' | '));
        }
      }
      return desc.get.call(this);
    },
  });
  return true;
})()`

async function main() {
  const url = await connect()
  ws = new WebSocket(url)
  await new Promise((resolve, reject) => {
    ws.onopen = resolve
    ws.onerror = reject
  })
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result)
    }
  }

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Performance.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 960, deviceScaleFactor: 1, mobile: false })

  await send('Page.navigate', { url: APP })
  await waitFor(`[...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频')).length > 0`, '知识树', 120000)
  await sleep(600)
  await evaluate(READ_PROBE)
  await evaluate(STUB)

  // 记录起点后开课；整段期间不做任何滚动，让页面保持「跟随底部」
  const before = await metrics()
  await evaluate(`(() => {
    const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频'))[0]
    kp.click(); return true
  })()`)

  await waitFor(`window.__MN_CHUNKS__ >= 5`, '流式开始', 20000)
  const mid = await metrics()
  await waitFor(`window.__MN_CHUNKS__ >= ${CHUNKS}`, '合成流吐完', 30000)
  await sleep(600) // 让最后几帧的布局落账
  const after = await metrics()

  const chunks = await evaluate(`window.__MN_CHUNKS__ ?? 0`)
  const reads = await evaluate(`window.__MN_SH_READS__ ?? 0`)
  const follows = await evaluate(`window.__MN_FOLLOW__ ?? 0`)
  const commits = await evaluate(`window.__MN_COMMIT__ ?? 0`)
  const layouts = after.LayoutCount - mid.LayoutCount
  const layoutMs = (after.LayoutDuration - mid.LayoutDuration) * 1000
  const followPerCommit = commits ? follows / commits : 0
  const atBottom = await evaluate(`(() => {
    const el = document.querySelector('.paper-canvas')
    return el.scrollHeight - el.scrollTop - el.clientHeight
  })()`)

  console.log(
    `→ ${chunks} 个 chunk / ${commits} 次渲染期间：跟随调用 ${follows} 次（${followPerCommit.toFixed(2)} / 渲染），` +
      `scrollHeight 读取 ${reads} 次，LayoutCount +${layouts}，LayoutDuration +${layoutMs.toFixed(0)}ms，` +
      `距底 ${Math.round(atBottom)}px`,
  )
  if (process.env.DEBUG_STACKS) {
    const buckets = await evaluate(`window.__MN_SH_BUCKETS__ ?? {}`)
    const spots = await evaluate(`document.querySelectorAll('.paper-canvas').length`)
    console.log(`   容器数量=${spots}`)
    for (const [k, v] of Object.entries(buckets).sort((a, b) => b[1] - a[1])) console.log(`   ${v}× ${k}`)
  }

  // 结论先说：这里只做「诊断 + 兜底」，不拿 LayoutCount 当门禁。
  // 实测同一条合成流连跑三次，LayoutCount 都是 213~221、LayoutDuration 88~110ms，
  // 差别全在噪声里 —— 因为被删掉的那次重复读，读到的是已经算好的布局，本来就不贵。
  // 真正被改善的是「跟随路径只有一处、每帧最多读一次 scrollHeight」这件事本身。
  check('跟随调用不超过渲染次数', follows <= commits + 5, `${follows} 次跟随 / ${commits} 次渲染`)
  check('布局总耗时可控', layoutMs < 900, `${layoutMs.toFixed(0)} ms / ${commits} 次渲染`)
  check('全程跟到底部（测量前提成立）', atBottom < 40, `距底 ${Math.round(atBottom)}px`)
  check('合成流完整吐完', chunks >= CHUNKS, `${chunks} chunks`)

  const res = await send('Page.captureScreenshot', { format: 'png' })
  const { writeFileSync } = await import('node:fs')
  writeFileSync('docs/shots/p29-layout.png', Buffer.from(res.data, 'base64'))

  console.log('\n==== 结果 ====')
  for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label}${r.detail ? ' (' + r.detail + ')' : ''}`)
  await send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(results.every((r) => r.ok) ? 0 : 1)
}

main().catch(async (err) => {
  console.error('❌', err.message)
  try { proc.kill() } catch {}
  process.exit(1)
})
