/**
 * P1-7 回归：`done` 到达时打字机队列非空，气泡会不会永远停在「老师正在写…」。
 *
 * 为什么必须用合成流：真实模型的 SSE 分片时机不可控，「最后一包内容 + done 挤在同一个
 * TCP 段里」这件事只能偶发触发。这里把整段讲义、三张题卡、done 一次性塞进**同一个
 * 网络包里**，让「done 到达时队列一定非空」变成确定性事件。
 *
 *   node scripts/typing_done_regression.mjs
 *
 * 修复前预期：❌ 卡在「老师正在写…」（退出码 1）
 * 修复后预期：✅ 三张题卡可交互、老师状态回到「等待作答」
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = Number(process.env.CDP_PORT || 9333)
const SHOTS = 'docs/shots'
const EDGE = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p)) || 'msedge'

mkdirSync(SHOTS, { recursive: true })

const proc = spawn(EDGE, [
  '--headless=new',
  `--remote-debugging-port=${PORT}`,
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-gpu',
  '--window-size=1440,960',
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-typing-profile',
  APP,
], { stdio: 'ignore', detached: false })

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

async function evaluate(expression, awaitPromise = false) {
  const res = await send('Runtime.evaluate', {
    expression,
    awaitPromise,
    returnByValue: true,
    userGesture: true,
  })
  if (res.exceptionDetails) {
    throw new Error(res.exceptionDetails.text + ' :: ' + (res.exceptionDetails.exception?.description || ''))
  }
  return res.result?.value
}

async function waitFor(expression, label, timeoutMs = 30000, interval = 250) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const value = await evaluate(expression).catch(() => null)
    if (value) return value
    await sleep(interval)
  }
  throw new Error(`等待超时：${label}`)
}

async function shot(name) {
  const res = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`${SHOTS}/${name}.png`, Buffer.from(res.data, 'base64'))
  console.log(`  📸 ${SHOTS}/${name}.png`)
}

const results = []
function check(label, ok, detail = '') {
  results.push({ label, ok, detail })
  console.log(`${ok ? '✅' : '❌'} ${label}${detail ? ' — ' + detail : ''}`)
}

// 合成讲义：足够长，保证 done 到达时队列里还有几百字没吐
const LESSON = [
  '## 合成讲义：导数定义的第二层',
  '',
  '先看一个动作：把「平均变化率」的分子分母同时缩小到零附近。',
  '这一步不是背公式，而是判断「能不能把极限移进括号里」。'.repeat(12),
  '',
  '检查问题：如果把分母换成零，你还能按原来的顺序动手吗？',
  '',
  '最后一行：SYNTH-END',
].join('\n')

const PACK = [
  {
    kind: 'choice',
    stem: '合成流里的第一题（单选）',
    options: ['A 选项', 'B 选项', 'C 选项', 'D 选项'],
    answer: 'A',
    explanation: '合成数据，用于验证题卡渲染。',
    tested_points: ['l03-b01-k01'],
    difficulty: 'easy',
  },
  {
    kind: 'fill',
    stem: '合成流里的第二题（填空）',
    options: [],
    answer: '1',
    explanation: '合成数据。',
    tested_points: ['l03-b01-k01'],
    difficulty: 'medium',
  },
  {
    kind: 'fill',
    stem: '合成流里的第三题（填空）',
    options: [],
    answer: '2',
    explanation: '合成数据。',
    tested_points: ['l03-b01-k01'],
    difficulty: 'hard',
  },
]

const EVENTS = [
  { type: 'meta', session_id: 'synthetic-p17', kp_id: 'l03-b01-k01', kp_name: '导数的定义', topic: '导数的定义' },
  { type: 'content', text: LESSON },
  { type: 'quiz_pack', quiz_pack: PACK, kp_id: 'l03-b01-k01', kp_name: '导数的定义', score: null, ttft_ms: 120 },
  {
    type: 'done',
    status: 'awaiting_answer',
    session_id: 'synthetic-p17',
    round: 0,
    max_rounds: 3,
    ttft_ms: 120,
    elapsed_ms: 800,
    tokens: 0,
  },
]

const INSTALL_STUB = `(() => {
  const events = ${JSON.stringify(EVENTS)};
  const body = events.map((e) => 'data: ' + JSON.stringify(e) + '\\n\\n').join('');
  const realFetch = window.fetch.bind(window);
  window.__MN_STUB_HITS__ = 0;
  window.fetch = function (url, init) {
    const target = typeof url === 'string' ? url : (url && url.url) || '';
    if (target.indexOf('/api/teach_proxy/stream') === -1) return realFetch(url, init);
    window.__MN_STUB_HITS__ += 1;
    // 整个讲义 + 题卡 + done 一次性入队：done 到达时打字机队列一定非空
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.close();
      },
    });
    return Promise.resolve(new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }));
  };
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
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 960, deviceScaleFactor: 1, mobile: false })

  console.log('→ 打开应用', APP)
  await send('Page.navigate', { url: APP })
  await waitFor(`document.body && document.body.innerText.includes('知识树')`, '页面渲染', 120000)
  await waitFor(
    `[...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频')).length > 0`,
    '知识树加载完成',
    90000,
  )
  await sleep(600)

  await evaluate(INSTALL_STUB)
  check('合成流已注入（只拦 /api/teach_proxy/stream）', true)

  // 点第一个知识点 → 走真实 start() 流程，只是网络层被换成合成流
  await evaluate(`(() => {
    const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频'))[0]
    kp.click(); return true
  })()`)

  const hits = await waitFor(`window.__MN_STUB_HITS__ > 0 ? window.__MN_STUB_HITS__ : null`, '合成流被调用', 20000)
  check('合成流被教学视图调用', hits >= 1, `${hits} 次`)

  // 1) 打字机必须把整段吐完（尾标出现 = 队列排空）
  const drained = await waitFor(
    `document.body.innerText.includes('SYNTH-END') ? true : null`,
    '打字机吐完合成讲义',
    15000,
  )
  check('打字机把队列吐完', Boolean(drained))

  // 2) 关键断言：done 已到 + 队列已空 → 必须离开 loading 态
  await sleep(1200)
  const state = await evaluate(`(() => {
    const text = document.body.innerText
    const status = (text.match(/等待作答|老师正在写…|已完成/) || [''])[0]
    const carets = document.querySelectorAll('article span.animate-pulse').length
    const options = document.querySelectorAll('[data-quiz-option]').length
    const pack = window.__MN_QUIZ_PACK__ ? window.__MN_QUIZ_PACK__.length : 0
    return { stuck: text.includes('老师正在写…'), status, carets, options, pack }
  })()`)
  await shot('p17-after-done')

  check('不再显示「老师正在写…」', !state.stuck, `状态=「${state.status}」`)
  check('气泡退出流式态（无打字机光标）', state.carets === 0, `${state.carets} 个光标`)
  check('三张题卡已可交互', state.pack === 3 && state.options >= 4, `pack=${state.pack} options=${state.options}`)

  // 3) 题卡真能点（说明 phase 不是 loading，交互没被锁死）
  const clicked = await evaluate(`(() => {
    const btn = document.querySelector('[data-quiz-option="A"]')
    if (!btn) return false
    const disabled = btn.disabled || btn.getAttribute('aria-disabled') === 'true'
    btn.click()
    return !disabled
  })()`)
  await sleep(600)
  check('题卡可点击（未被 loading 锁死）', Boolean(clicked))

  console.log('\n==== 结果 ====')
  for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label} ${r.detail ? '(' + r.detail + ')' : ''}`)
  const failed = results.filter((r) => !r.ok)
  await send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(failed.length ? 1 : 0)
}

main().catch(async (err) => {
  console.error('❌', err.message)
  try { await shot('99-p17-error') } catch {}
  try { proc.kill() } catch {}
  process.exit(1)
})
