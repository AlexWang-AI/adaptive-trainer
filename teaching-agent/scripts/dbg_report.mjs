import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = 'http://localhost:3000'
const PORT = 9455
const EDGE = ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find((p) => existsSync(p))
const proc = spawn(EDGE, ['--headless=new', `--remote-debugging-port=${PORT}`, '--no-first-run', '--disable-gpu',
  '--window-size=1440,960', '--user-data-dir=' + process.env.TEMP + '/edge-mn-dbg', APP], { stdio: 'ignore' })

let ws, seq = 0
const pending = new Map()
const send = (m, p = {}) => new Promise((res, rej) => { const id = ++seq; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method: m, params: p })) })

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
      const page = list.find((t) => t.type === 'page')
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('no cdp')
}

const evaluate = async (e) => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) return { error: r.exceptionDetails.text + ' ' + (r.exceptionDetails.exception?.description || '') }
  return r.result?.value
}

const url = await connect()
ws = new WebSocket(url)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(m.error.message)) : res(m.result) }
  if (m.method === 'Runtime.exceptionThrown') console.log('PAGE EXC:', m.params?.exceptionDetails?.exception?.description?.slice(0, 300))
  if (m.method === 'Runtime.consoleAPICalled' && m.params?.type === 'error') console.log('CONSOLE ERR:', JSON.stringify(m.params.args?.[0]?.value ?? '').slice(0, 300))
}
await send('Runtime.enable')
await send('Page.enable')
for (let i = 0; i < 40; i++) {
  if (await evaluate(`!!document.querySelector('[data-open-report]')`)) break
  await sleep(500)
}
console.log('click ->', await evaluate(`document.querySelector('[data-open-report]').click(), 'ok'`))
await sleep(3000)
console.log('has 能力雷达:', await evaluate(`document.body.innerText.includes('能力雷达')`))
console.log('body head:', (await evaluate(`document.body.innerText.slice(0,160)`))?.replace(/\n/g, ' | '))
console.log('overlay count:', await evaluate(`document.querySelectorAll('.fixed.inset-0').length`))
await send('Browser.close').catch(() => {})
proc.kill()
process.exit(0)
