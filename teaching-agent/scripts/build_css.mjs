// 用 in-process PostCSS 预编译 Tailwind，绕开 Next 的 PostCSS 子进程
// 背景：本机 Turbopack/webpack 的 postcss loader 子进程会 timeout，导致 build/dev 卡死。
// 一次性生成 app/prebuilt.css 后，删掉 postcss.config.mjs 即可让 Next 不再 spawn 该 worker。
import { readFile, writeFile } from 'node:fs/promises'
import postcss from 'postcss'
import tailwind from '@tailwindcss/postcss'

const source = await readFile('app/globals.css', 'utf8')
const started = Date.now()
const result = await postcss([tailwind()]).process(source, { from: 'app/globals.css' })
await writeFile('app/prebuilt.css', result.css)
console.log(`prebuilt.css written: ${result.css.length} chars in ${Date.now() - started}ms`)
