/**
 * 流式体验质量验收（CDP）：
 *   1) 用户上滑后，页面不许被自动拽回底部；
 *   2) 文字持续增长（typen 不中断）；
 *   3) Markdown/KaTeX 解析次数被节流（不是每帧重解析）；
 *   4) 长任务（>50ms）占比低。
 *
 *   node scripts/stream_quality.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = 9333
const EDGE = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p)) || 'msedge'

mkdirSync('docs/shots', { recursive: true })

const proc = spawn(EDGE, [
  '--headless=new',
  `--remote-debugging-port=${PORT}`,
  '--no-first-run',
  '--disable-gpu',
  '--window-size=1440,960',
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-quality',
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
  throw new Error('连不上调试端口')
}

async function evaluate(expression) {
  const res = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text)
  return res.result?.value
}

async function waitFor(expression, label, timeoutMs = 90000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const value = await evaluate(expression).catch(() => null)
    if (value) return value
    await sleep(300)
  }
  throw new Error(`等待超时：${label}`)
}

async function shot(name) {
  const res = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`docs/shots/${name}.png`, Buffer.from(res.data, 'base64'))
}

const results = []
function check(label, ok, detail = '') {
  results.push({ label, ok, detail })
  console.log(`${ok ? '✅' : '❌'} ${label}${detail ? ' — ' + detail : ''}`)
}

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
  // 视口压到 640 高：一节讲义 350~600 字，960 高时根本撑不满，上滑测试会变成「原地不动」的假通过
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 640, deviceScaleFactor: 1, mobile: false })

  // 埋点：长任务
  await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `
      window.__MN_LONG__ = [];
      try {
        new PerformanceObserver((list) => {
          for (const e of list.getEntries()) window.__MN_LONG__.push(Math.round(e.duration));
        }).observe({ type: 'longtask', buffered: true });
      } catch (e) {}
    `,
  })

  await send('Page.navigate', { url: APP })
  await waitFor(`[...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频')).length > 0`, '知识树', 120000)
  await sleep(800)

  console.log('→ 开始一课，进入流式…')
  await evaluate(`(() => {
    const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频'))[0]
    kp.click(); return true
  })()`)

  await waitFor(`typeof window.__MN_TTFT__ === 'number'`, '首字上屏', 90000)
  // 等到内容真的超出视口，上滑才有意义（否则 scrollTop 永远是 0，测了个寂寞）
  await waitFor(
    `(() => {
      const el = document.querySelector('.paper-canvas')
      return el && el.scrollHeight - el.clientHeight > 200 ? true : null
    })()`,
    '内容超出视口',
    60000,
  )
  await sleep(300)

  const t0 = await evaluate(`(() => {
    const el = document.querySelector('.paper-canvas')
    return { top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight }
  })()`)

  // 用户往上滑：3 次滚轮
  for (let i = 0; i < 3; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseWheel', x: 720, y: 500, deltaX: 0, deltaY: -420, pointerType: 'mouse',
    })
    await sleep(120)
  }
  await sleep(400)
  const afterWheel = await evaluate(`document.querySelector('.paper-canvas').scrollTop`)

  // 流式继续 4 秒，看会不会被拽回去
  await sleep(4000)
  const afterStream = await evaluate(`(() => {
    const el = document.querySelector('.paper-canvas')
    return { top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight,
             parses: window.__MN_MD_PARSE__ ?? 0, long: window.__MN_LONG__ ?? [] }
  })()`)

  const grew = await evaluate(`document.body.innerText.length`)

  // 1) 上滑后不被拽回：滚动位置应保持在用户停下的地方（允许 ±8px 抖动）
  check(
    '上滑后不被强制拉回底部',
    Math.abs(afterStream.top - afterWheel) <= 8,
    `滑动后 ${Math.round(afterWheel)} → 4 秒后 ${Math.round(afterStream.top)}（文档总高 ${afterStream.height}）`,
  )

  // 2) 内容仍在增长（流式没有因为改滚动而中断）
  check('流式文字持续增长', grew > 400, `${grew} 字`)

  // 3) Markdown 解析节流：4 秒内解析次数应远小于帧数（60fps × 4s = 240）
  check('Markdown 解析被节流', afterStream.parses < 80, `4 秒内解析 ${afterStream.parses} 次`)

  // 4) 长任务：4 秒内不应有大量 >50ms 的卡顿
  const longTasks = afterStream.long || []
  const longTotal = longTasks.reduce((a, b) => a + b, 0)
  check(
    '主线程无明显长卡顿',
    longTasks.length <= 6 && longTotal < 900,
    `${longTasks.length} 个长任务，合计 ${longTotal}ms（${longTasks.slice(0, 6).join('/')}）`,
  )

  await shot('quality-scrolled')

  // 5) 点「回到底部」能回去
  const hasBtn = await evaluate(`!!document.querySelector('[data-jump-bottom]')`)
  check('出现「回到底部」按钮', hasBtn)
  if (hasBtn) {
    await evaluate(`document.querySelector('[data-jump-bottom]').click()`)
    await sleep(600)
    const bottom = await evaluate(`(() => {
      const el = document.querySelector('.paper-canvas')
      return el.scrollHeight - el.scrollTop - el.clientHeight
    })()`)
    check('点击后回到底部', bottom < 40, `距底 ${Math.round(bottom)}px`)
  }

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
