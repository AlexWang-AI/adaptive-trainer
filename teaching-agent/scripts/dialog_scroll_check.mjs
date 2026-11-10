/**
 * P2-3 回归：诊断弹窗在窄屏 + 长结果下还能不能用。
 *
 * 以前弹窗没有高度上限、内部也不滚动：诊断一旦给出十几步，面板会顶出屏幕，
 * 底部的「诊断」按钮和后半段结论都够不着。
 *
 * 剧本：390×844（手机竖屏）视口，合成流拉起题卡，点「说说我的思路」，
 * 用桩数据返回 12 步诊断（不花 token），然后量三件事：
 *   1. 面板整体在视口内（不越界）；
 *   2. 正文区可滚动（overflow-y-auto 且 scrollHeight > clientHeight）；
 *   3. 滚到底之后最后一步可见，而头部（标题栏）没被滚走。
 *
 *   node scripts/dialog_scroll_check.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const APP = process.env.APP_URL || 'http://localhost:3000'
const PORT = Number(process.env.CDP_PORT || 9335)
const VIEW = { width: 390, height: 844 }
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
  `--window-size=${VIEW.width},${VIEW.height}`,
  '--user-data-dir=' + process.env.TEMP + '/edge-mn-dialog',
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

async function waitFor(expression, label, timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const value = await evaluate(expression).catch(() => null)
    if (value) return value
    await sleep(200)
  }
  throw new Error(`等待超时：${label}`)
}

const results = []
function check(label, ok, detail = '') {
  results.push({ label, ok, detail })
  console.log(`${ok ? '✅' : '❌'} ${label}${detail ? ' — ' + detail : ''}`)
}

// 12 步诊断 + 长结论：足够把 88vh 撑爆
const DIAG_STEPS = Array.from({ length: 12 }, (_, i) => ({
  step: `第 ${i + 1} 步：这一步在判断适用条件，公式本身没写错，但没有确认 0/0 型是否成立`,
  ok: i < 4,
  issue: i < 4 ? '' : '跳过了条件检查，直接套用结论',
}))
const DIAG_RESULT = {
  steps: DIAG_STEPS,
  first_break: '第 5 步：没确认 0/0 型就直接用了洛必达，条件不成立时结论完全不成立',
  misconception: '把「公式能用」当成「条件已满足」，先算再说前提',
  fix: '每写一个等号之前先念一句：现在的形状满足哪个定理的条件？不满足就换路。',
  severity: 'concept',
}

const STUB = `(() => {
  const realFetch = window.fetch.bind(window);
  const enc = new TextEncoder();
  const sse = (obj) => 'data: ' + JSON.stringify(obj) + '\\n\\n';
  window.fetch = function (url, init) {
    const target = typeof url === 'string' ? url : (url && url.url) || '';
    if (target.indexOf('/api/diagnose') !== -1) {
      return Promise.resolve(new Response(JSON.stringify(${JSON.stringify(DIAG_RESULT)}), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }));
    }
    if (target.indexOf('/api/teach_proxy/stream') === -1) return realFetch(url, init);
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(enc.encode(sse({ type: 'meta', session_id: 'dialog', kp_id: 'l03-b01-k01', kp_name: '导数定义与可导性' })));
        controller.enqueue(enc.encode(sse({ type: 'content', text: '## 合成讲义\\n\\n这一层只做一件事：把条件写在等号前面。\\n\\n检查问题：你写的第一步，条件成立吗？' })));
        controller.enqueue(enc.encode(sse({
          type: 'quiz_pack',
          quiz_pack: ${JSON.stringify([
            { kind: 'choice', stem: '合成题 1', options: ['A', 'B', 'C', 'D'], answer: 'A', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'easy' },
            { kind: 'fill', stem: '合成题 2', options: [], answer: '1', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'medium' },
            { kind: 'fill', stem: '合成题 3', options: [], answer: '2', explanation: 'x', tested_points: ['l03-b01-k01'], difficulty: 'hard' },
          ])},
          kp_id: 'l03-b01-k01', kp_name: '导数定义与可导性',
        })));
        controller.enqueue(enc.encode(sse({ type: 'done', status: 'awaiting_answer', session_id: 'dialog', round: 0, max_rounds: 3, ttft_ms: 30 })));
        controller.close();
      },
    });
    return Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }));
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
  // 先把视口定成手机尺寸，再导航，避免应用按桌面宽度布局
  await send('Emulation.setDeviceMetricsOverride', {
    width: VIEW.width, height: VIEW.height, deviceScaleFactor: 2, mobile: true,
  })

  await send('Page.navigate', { url: APP })
  await waitFor(`[...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频')).length > 0`, '知识树', 120000)
  await sleep(500)
  await evaluate(STUB)

  await evaluate(`(() => {
    const kp = [...document.querySelectorAll('button')].filter(b => b.title && b.title.includes('考频'))[0]
    kp.click(); return true
  })()`)
  await waitFor(`!!document.querySelector('[data-quiz-diagnose]')`, '题卡出现', 30000)
  await evaluate(`document.querySelector('[data-quiz-diagnose]').click()`)
  await waitFor(`!!document.querySelector('[data-diag-input]')`, '诊断弹窗打开', 10000)

  // 填一段长思路（1500 字上限内）
  await evaluate(`(() => {
    const input = document.querySelector('[data-diag-input]')
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
    setter.call(input, ${JSON.stringify('我先看到 0/0，就直接用了洛必达，没检查条件。'.repeat(8))})
    input.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  })()`)
  await sleep(150)
  await evaluate(`document.querySelector('[data-diag-submit]').click()`)

  const steps = await waitFor(
    `(() => {
      const body = document.querySelector('[data-diag-body]')
      if (!body) return null
      const lis = body.querySelectorAll('li').length
      return lis >= ${DIAG_STEPS.length} ? lis : null
    })()`,
    '诊断结果渲染',
    20000,
  )
  check('诊断结果渲染出 12 步', steps >= DIAG_STEPS.length, `${steps} 步`)

  const geo = await evaluate(`(() => {
    const body = document.querySelector('[data-diag-body]')
    const panel = body.parentElement
    const rect = panel.getBoundingClientRect()
    const style = getComputedStyle(body)
    const header = panel.firstElementChild
    return {
      vw: window.innerWidth, vh: window.innerHeight,
      top: rect.top, bottom: rect.bottom, height: rect.height,
      overflowY: style.overflowY,
      scrollable: body.scrollHeight > body.clientHeight + 1,
      scrollSpan: body.scrollHeight, clientSpan: body.clientHeight,
      headerText: header ? header.innerText.trim().slice(0, 12) : '',
    }
  })()`)

  check('弹窗不越出视口', geo.top >= -1 && geo.bottom <= geo.vh + 1,
    `top=${Math.round(geo.top)} bottom=${Math.round(geo.bottom)} 视口高=${geo.vh}`)
  check('正文区可以滚动', geo.overflowY === 'auto' && geo.scrollable,
    `overflow=${geo.overflowY} 内容 ${Math.round(geo.scrollSpan)}px / 视口 ${Math.round(geo.clientSpan)}px`)

  const scrolled = await evaluate(`(() => {
    const body = document.querySelector('[data-diag-body]')
    body.scrollTop = body.scrollHeight
    const lis = body.querySelectorAll('li')
    const last = lis[lis.length - 1].getBoundingClientRect()
    const panel = body.parentElement.getBoundingClientRect()
    const header = body.parentElement.firstElementChild.getBoundingClientRect()
    return {
      scrollTop: body.scrollTop,
      lastVisible: last.top >= panel.top - 1 && last.bottom <= panel.bottom + 1,
      headerVisible: header.top >= panel.top - 1 && header.bottom > panel.top,
    }
  })()`)
  check('滚到底能看到最后一步', scrolled.scrollTop > 0 && scrolled.lastVisible, `scrollTop=${Math.round(scrolled.scrollTop)}`)
  check('滚动时标题栏固定在顶部', scrolled.headerVisible)

  // 弹窗必须挂在 body 上（portal）：题卡在 .paper-canvas 的层叠上下文里，
  // 嵌着渲染时 z-50 压不过外层 z-30/z-40 的浮动控件
  const stacking = await evaluate(`(() => {
    const body = document.querySelector('[data-diag-body]')
    const panel = body.parentElement
    const rect = panel.getBoundingClientRect()
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.bottom - 24)
    return {
      chain: (() => { const out = []; let el = panel; for (let i = 0; i < 5 && el; i++) { out.push(el.tagName + (el.id ? '#' + el.id : '')); el = el.parentElement } return out.join(' < ') })(),
      portal: panel.parentElement && panel.parentElement.parentElement === document.body,
      inside: !!hit && panel.contains(hit),
      tag: hit ? hit.tagName : 'null',
    }
  })()`)
  check('弹窗通过 portal 挂在 body 上', stacking.portal, stacking.chain)
  check('弹窗区域命中自己（不被其它浮层压住）', stacking.inside, stacking.tag)

  const res = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync('docs/shots/p23-dialog.png', Buffer.from(res.data, 'base64'))
  console.log('  📸 docs/shots/p23-dialog.png')

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
