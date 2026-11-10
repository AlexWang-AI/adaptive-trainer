/**
 * 浏览器端真机验收：用 CDP 驱动 Edge，走完「点知识点 → 看流式上屏 → 三道题闯关 → 侧边栏打勾」。
 *
 * 不依赖 puppeteer / playwright：Node 22+ 自带 WebSocket，直接说 CDP 协议。
 *
 *   node scripts/browser_smoke.mjs
 *
 * 产物：docs/shots/*.png
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = 9222
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
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-profile',
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

async function waitFor(expression, label, timeoutMs = 90000, interval = 400) {
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
  await sleep(800)
  await shot('01-home')

  const treeInfo = await evaluate(`(() => {
    const buttons = [...document.querySelectorAll('button')]
    const kp = buttons.filter(b => b.title && b.title.includes('考频'))
    return { kpCount: kp.length, first: kp[0]?.title || '' }
  })()`)
  check('知识树渲染出可点击知识点', treeInfo.kpCount > 0, `${treeInfo.kpCount} 个`)

  // 点第一个知识点，触发教学
  const started = Date.now()
  await evaluate(`(() => {
    const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频'))[0]
    kp.click(); return true
  })()`)

  await waitFor(`document.body.innerText.length > 400 && /老师/.test(document.body.innerText)`, '进入教学视图', 20000)
  const ttft = await waitFor(
    `typeof window.__MN_TTFT__ === 'number' ? window.__MN_TTFT__ : null`,
    '首字上屏',
    90000,
  )
  await sleep(1200)
  await shot('02-streaming')
  // 这里只验「首字能上屏」的连通性：单次样本 + 冷缓存（新进程/新知识点的前缀缓存未命中）
  // 会把 1.3s 抖到 6s，拿它当 TTFT 门禁是误报。严格门禁在 check_e2e.py（预热后取中位数）。
  check('流式首字到达（页面侧，门槛 8s）', ttft < 8000, `${ttft} ms（严格 TTFT 看 check_e2e 的中位数）`)

  const pack = await waitFor(`window.__MN_QUIZ_PACK__ && window.__MN_QUIZ_PACK__.length === 3 ? window.__MN_QUIZ_PACK__ : null`, '三张题卡', 90000)
  check('收到 3 张题卡', pack.length === 3, pack.map((q) => q.difficulty).join(' → '))

  // 题型标签：来自教材题型层（type_name），要在题卡头上真的渲染出来
  const typeTags = await evaluate(`(() => {
    const el = document.querySelector('[title^="教材题型"]')
    return el ? el.textContent.trim() : ''
  })()`)
  check('题卡显示教材题型标签', Boolean(typeTags), typeTags || '（没有 type_name）')
  await shot('03-quiz-pack')

  for (let i = 0; i < pack.length; i++) {
    const q = pack[i]
    if (q.kind === 'choice') {
      const letter = String(q.answer).trim().toUpperCase()[0]
      await waitFor(`!!document.querySelector('[data-quiz-option="${letter}"]')`, `第 ${i + 1} 题选项`, 30000)
      await evaluate(`document.querySelector('[data-quiz-option="${letter}"]').click()`)
    } else {
      await waitFor(`!!document.querySelector('[data-quiz-input]')`, `第 ${i + 1} 题输入框`, 30000)
      await evaluate(`(() => {
        const input = document.querySelector('[data-quiz-input]')
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
        setter.call(input, ${JSON.stringify(q.answer)})
        input.dispatchEvent(new Event('input', { bubbles: true }))
        return true
      })()`)
      await sleep(200)
      await evaluate(`document.querySelector('[data-quiz-submit]').click()`)
    }
    // 答对后自动推进：等题号 +1（最后一题等通关文本）
    if (i < pack.length - 1) {
      await waitFor(
        `window.__MN_QUIZ_INDEX__ === ${i + 1}`,
        `第 ${i + 1} 题判对并自动进入下一题`,
        30000,
      )
    } else {
      await waitFor(`document.body.innerText.includes('知识点通关')`, '最后一题判对并通关', 30000)
    }
    if (i === 0) await shot('04-first-correct')
    await sleep(300)
  }

  const passText = await waitFor(
    `document.body.innerText.includes('知识点通关') ? document.body.innerText : null`,
    '通关提示',
    20000,
  )
  check('三道题全部通过并出现通关提示', passText.includes('知识点通关'))
  await shot('05-mastered')

  await waitFor(
    `(() => {
      const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('已通关'))
      return kp.length > 0
    })()`,
    '侧边栏打勾',
    20000,
  )
  await shot('06-sidebar-checked')
  check('侧边栏对应节点已打勾', true)

  // 通关后应自动进入下一站（3 秒倒计时，无需点击）；也接受用户先看到 CTA
  const advanced = await waitFor(
    `document.body.innerText.includes('通关，下一站') ||
     document.body.innerText.includes('马上进入') ||
     document.body.innerText.includes('无穷小与无穷大')`,
    '自动进入下一站',
    45000,
  ).catch(() => null)
  check('通关后自动进入下一站（无需手动点击）', Boolean(advanced))
  await shot('07-next-kp')

  console.log('\n==== 结果 ====')
  for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label} ${r.detail ? '(' + r.detail + ')' : ''}`)
  const failed = results.filter((r) => !r.ok)
  await send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(failed.length ? 1 : 0)
}

main().catch(async (err) => {
  console.error('❌', err.message)
  try { await shot('99-error') } catch {}
  try { proc.kill() } catch {}
  process.exit(1)
})
