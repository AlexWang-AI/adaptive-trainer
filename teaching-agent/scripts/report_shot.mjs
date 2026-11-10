/** 打开「学习报告」抽屉并截图：node scripts/report_shot.mjs */
import { spawn } from 'node:child_process'
import { existsSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = 9444
const EDGE = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p)) || 'msedge'

const proc = spawn(EDGE, [
  '--headless=new', `--remote-debugging-port=${PORT}`, '--no-first-run', '--disable-gpu',
  '--window-size=1440,960', '--user-data-dir=' + process.env.TEMP + '/edge-mn-report', APP,
], { stdio: 'ignore' })

let ws, seq = 0
const pending = new Map()
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })

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

const evaluate = async (expression) => {
  const res = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text)
  return res.result?.value
}

async function waitFor(expr, label, timeout = 90000) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    if (await evaluate(expr).catch(() => false)) return true
    await sleep(400)
  }
  throw new Error('等待超时：' + label)
}

async function main() {
  const url = await connect()
  ws = new WebSocket(url)
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result)
    }
  }
  await send('Page.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 960, deviceScaleFactor: 1, mobile: false })
  await waitFor(`!!document.querySelector('[data-open-report]')`, '页面加载', 120000)
  // 等 hydration：SSR 出来的按钮在 hydration 前点了没反应，所以点完没开就重试
  let opened = false
  for (let i = 0; i < 8 && !opened; i++) {
    await evaluate(`document.querySelector('[data-open-report]')?.click()`)
    await sleep(1500)
    opened = await evaluate(`document.body.innerText.includes('能力雷达')`)
  }
  if (!opened) throw new Error('报告打不开')
  await sleep(1500)
  const shot = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync('docs/shots/study-report.png', Buffer.from(shot.data, 'base64'))

  // 小屏检查：380px 宽时是否横向溢出
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await sleep(800)
  const overflow = await evaluate(`document.documentElement.scrollWidth > document.documentElement.clientWidth + 1`)
  const shot2 = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync('docs/shots/study-report-mobile.png', Buffer.from(shot2.data, 'base64'))
  console.log(overflow ? '❌ 小屏横向溢出' : '✅ 小屏无横向溢出')
  await send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(overflow ? 1 : 0)
}

main().catch((err) => { console.error('❌', err.message); try { proc.kill() } catch {}; process.exit(1) })
