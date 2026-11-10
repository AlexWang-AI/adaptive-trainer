# 状态说明（2026-11-09 20:10 更新：已恢复）

## 现在可以直接用

| 服务 | 地址 | 状态 |
|---|---|---|
| 前端 | http://localhost:3000 | ✅ 200，页面编译 6 s，首字 ~2 s |
| 后端 | http://127.0.0.1:8008/api/health_v3 | ✅ 200 |
| 知识树 | http://localhost:3000/api/knowledge | ✅ 200 |

验收（本轮实测）：
- `python scripts/check_e2e.py --samples 4` → **PASS**，TTFT 中位数 **1959 ms**（2605/1768/2053/1865）
- `node scripts/browser_smoke.mjs` → **6/6 PASS**，页面侧首字 **1970 ms**，三道题全对、侧边栏打勾、出现「进入下一知识点」

## 上一轮「打不开」的真因：不是内存，是 Tailwind 编译

本机 Tailwind v4 单次编译约 **5~6 分钟**；Next 的 postcss loader 在 Turbopack 下跑子进程，
超时后直接崩：

```
Error: Node.js subprocess crashed while evaluating loaders [postcss]: failed to receive message
```

表现就是：`npm run dev` 卡在 `Compiling / ...`、访问 500、`next build` 超时。

## 已采用的修法：CSS 预编译

1. `node scripts/build_css.mjs` → 生成 `app/prebuilt.css`（约 6 分钟，一次性）
2. `app/layout.tsx` 改为 `import './prebuilt.css'`
3. `postcss.config.mjs` 改名为 `postcss.config.mjs.disabled`

之后 Turbopack 不再需要跑 PostCSS，页面编译 **6 秒**。

### 什么时候需要重新生成 CSS

只有**改了样式**（`app/globals.css`、Tailwind 类名大改、主题变量）才需要：

```powershell
node scripts/build_css.mjs          # 约 6 分钟
# 然后重启 npm run dev
```

纯业务代码改动（组件、接口、提示词）不需要。

## 日常启动

```powershell
# 窗口 1：后端
cd C:\Users\明\Desktop\第一版UI_ex_v2\backend
C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8008

# 窗口 2：前端
cd C:\Users\明\Desktop\第一版UI_ex_v2
npm run dev
```

或双击 `start_all.bat`。

## 已知限制

- 讲义实际长度常超过提示词要求的 600 字（1200+ 字），偶尔触发 JSON 截断重生成（首字会到 6~8 s）。
- 生产构建 `npm run build` 本轮未重新验证（Taskkill 过 `.next`）；dev 模式已验证可用。
