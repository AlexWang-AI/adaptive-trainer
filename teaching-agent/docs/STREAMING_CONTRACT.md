# 流式体验契约（Streaming Contract）

> 这份文件是「不许再退化」的护栏。改 `teaching-chat.tsx` / `markdown.tsx` 前先读它，
> 改完跑 `node scripts/stream_quality.mjs`，6 项必须全过。

## 四条硬规则

### 1. 绝不强制滚动
**唯一允许滚动视口的时机**：用户自己就在底部（`stickToBottomRef.current === true`）。

- `drainTyping` 里滚动必须判 `stickToBottomRef`；
- 任何 `scrollTop = scrollHeight` 都要经过 `scrollToBottom()`，它只被「贴底」路径调用；
- 用户一旦向上滚（`handleWheel` deltaY<0 或 scrollTop 变小），立刻 `stick=false` 并显示「回到底部」；
- 只有滚回距底 <48px 才恢复跟随。

历史 bug：`drainTyping` 每吐一块就无条件 `scrollToBottom()`，用户往上翻会被拽回底部。

### 2. 不要提前结束 streaming 状态
队列吐空 ≠ 流结束。`done` 事件到达前，`message.streaming` 必须保持 true。

历史 bug：吐空就 `finishTyping()` → 气泡闪回「老师正在组织这一层」→ `StreamingMarkdown` 卸载重挂 →
整篇 markdown 重新解析，既闪又卡。

### 3. Markdown/KaTeX 按段落增量解析，不每帧全量重解析
`StreamingMarkdown` 的三段结构：

```
[已稳定段落]  MarkdownMessage(stable)   ← 只在段落完成时变化，memo 命中
[当前段落]    MarkdownMessage(active)   ← 每 190ms 最多重解析一次
[未解析尾巴]  纯文本 span               ← 每帧增长，保证吐字连续
```

历史 bug：每 16ms 把所有消息重新 map + 整篇 `rehype-katex`，主线程被打满 → 「很卡、不丝滑」。

### 4. 解析是低优先级更新
`setParsed` 包在 `startTransition` 里，不能挡住滚动与输入。

## 验收（任何一条不过就是回归）

```powershell
node scripts/stream_quality.mjs     # 滚动 + 节流 + 长任务 + 回到底部
node scripts/browser_smoke.mjs      # 主流程 6 项
```

`stream_quality.mjs` 的判定口径：

| 指标 | 门槛 | 最近一次 |
|---|---|---|
| 上滑后 4 秒内滚动位置漂移 | ≤ 8px | 0px |
| 流式期间文字增长 | > 400 字 | 1338 字 |
| 4 秒内 Markdown 解析次数 | < 80（60fps 是 240） | 16 |
| 4 秒内长任务（>50ms） | ≤ 6 个且合计 < 900ms | 4 个 / 415ms |
| 未贴底时出现「回到底部」 | 必须出现 | 出现 |
| 点击后距底 | < 40px | 0px |

## 还欠的一步

`docs/RECOVERY.md` 里的 CSS 预编译说明仍然有效：**新增 Tailwind 类后必须重跑**
`node scripts/build_css.mjs`（约 6 分钟），否则新按钮会丢失定位类（本轮就踩过一次：
「回到底部」和「问老师」曾跑到页面顶部）。
