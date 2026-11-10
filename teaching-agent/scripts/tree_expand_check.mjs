/**
 * 知识树「层级完整性」验收：树上有的层，界面上必须点得到。
 *
 * 背景：用户指出「七种未定式的计算」在侧栏只剩一个点，而知识树里它有 7 种未定式。
 * 这条 e2e 就是拿它当靶子：展开 → 必须出现 7 条子项 → 点「0/0 型」→ 讲课只讲这一条。
 *
 *   node scripts/tree_expand_check.mjs
 *
 * 断言：
 *   1. 侧栏能展开知识点，出现 ≥7 条「只讲这一条」子项；
 *   2. 七种未定式（0/0、∞/∞、0·∞、∞-∞、0⁰、1^∞、∞⁰）一个不少；
 *   3. 点子项后，学生气泡带着「知识点｜子项」发出请求，老师开始流式讲解。
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = Number(process.env.CDP_PORT || 9336)
const KP_NAME = '七种未定式的计算'
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
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-treeexpand',
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

async function waitFor(expression, label, timeoutMs = 60000, interval = 250) {
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
  writeFileSync(`docs/shots/${name}.png`, Buffer.from(res.data, 'base64'))
  console.log(`  📸 docs/shots/${name}.png`)
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

  await send('Page.navigate', { url: APP })
  await waitFor(`[...document.querySelectorAll('button')].filter(b => (b.title||'').includes('考频')).length > 0`, '知识树加载', 120000)
  await sleep(500)

  // 找到目标知识点的行，点它左边的小箭头
  const opened = await evaluate(`(() => {
    const target = [...document.querySelectorAll('button')].find(b => (b.title||'').startsWith('${KP_NAME}'))
    if (!target) return 'no-kp'
    const row = target.parentElement
    const chevron = row && row.querySelector('button[title*="展开教材要点"]')
    if (!chevron) return 'no-chevron'
    chevron.click()
    return 'ok'
  })()`)
  check('侧栏能找到并展开该知识点', opened === 'ok', opened)

  const count = await waitFor(
    `(() => { const n = document.querySelectorAll('button[title^="只讲这一条"]').length; return n >= 7 ? n : null })()`,
    '子项渲染',
    30000,
  )
  check('展开后出现教材子项（≥7 条）', count >= 7, `${count} 条`)

  const texts = await evaluate(
    `[...document.querySelectorAll('button[title^="只讲这一条"]')].map(b => b.textContent.trim())`,
  )
  const wanted = ['0/0', '∞/∞', '0·∞', '∞-∞', '0⁰', '1^∞', '∞⁰']
  const missing = wanted.filter((w) => !texts.some((t) => t.includes(w)))
  check('七种未定式一个不少', missing.length === 0, missing.length ? `缺 ${missing.join('、')}` : texts.slice(0, 3).join(' / '))
  await shot('tree-expanded')

  // 结论层也要能看（375 条结论在界面上不能是隐形的）
  const conc = await evaluate(`(() => {
    const btn = [...document.querySelectorAll('button')].find(b => (b.textContent || '').includes('本分支结论'))
    if (!btn) return 'no-toggle'
    btn.click()
    return 'ok'
  })()`)
  check('分支结论可展开', conc === 'ok', conc)
  const concVisible = await waitFor(
    `(() => (document.body.innerText.includes('极限的四则运算法则') ? true : null))()`,
    '结论原文',
    15000,
  )
  check('结论原文在侧栏可见', Boolean(concVisible))
  await shot('tree-conclusions')

  // 点「0/0 型」→ 只讲这一条
  await evaluate(`(() => {
    const row = [...document.querySelectorAll('button[title^="只讲这一条"]')].find(b => b.textContent.includes('0/0'))
    if (row) row.click()
    return true
  })()`)
  const bubble = await waitFor(
    `(() => {
      const t = document.body.innerText
      return t.includes('${KP_NAME}｜0/0') ? t.slice(0, 400) : null
    })()`,
    '子项授课请求',
    30000,
  )
  check('点击子项后以「知识点｜子项」开讲', true, bubble.split('\n').find((l) => l.includes('｜')) || '')

  await waitFor(`document.body.innerText.includes('老师')`, '进入教学视图', 30000)
  const grew = await waitFor(
    `(() => { const t = document.body.innerText; return t.length > 1200 ? t.length : null })()`,
    '讲义开始上屏',
    90000,
  )
  check('讲义开始流式上屏', Boolean(grew), `${grew} 字`)
  await shot('tree-focus-lesson')

  console.log('\n==== 结果 ====')
  for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label}${r.detail ? ' (' + r.detail + ')' : ''}`)
  await send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(results.every((r) => r.ok) ? 0 : 1)
}

main().catch(async (err) => {
  console.error('❌', err.message)
  try { await shot('99-tree-error') } catch {}
  try { proc.kill() } catch {}
  process.exit(1)
})
