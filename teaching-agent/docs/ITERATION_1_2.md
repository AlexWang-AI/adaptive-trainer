# 第一、二轮迭代交付 · 含红队评审结果

> 2026-11-10 ｜ 目标：把「诊断 → 讲 → 练 → 改 → 验收」做成可量化的闭环

## 一、这一轮真正打通了什么

| 能力 | 落点 | 状态 |
|---|---|---|
| 错题按 1/3/7 天回流 | `v3core/learning.py` `review_queue` + `/api/review/*` | ✅ 到期才计分，同一场连点不能「毕业」 |
| 思路诊断反向约束出题 | `/api/diagnose` 写 `misconception_log` → 讲课的 `learner_note` 与「再练一组」都会带上 | ✅ |
| 每轮账本 | `/api/ledger` + 聊天里的账本卡（作答/掌握度/断点/认知偏差/下次复习） | ✅ |
| 再练一组（只出题不重讲） | `/api/practice_more` + 账本卡按钮 | ✅ 接口实测 3 题；浏览器未逐点回归 |
| 掌握度模型 | `kp_mastery = (correct+1)/(attempts+2) × (0.7+0.3×新鲜度)` | ✅ 可解释，前端脚注同口径 |
| 能力雷达 / 提分曲线 / 热力图 | `/api/analytics` + `components/workspace/study-report.tsx` | ✅ 雷达按考频取前 6 章 |
| 通关口径 | `/api/mastery` 改为**服务端按作答推导**，少于 3 题拒绝通关 | ✅ 堵住「客户端传 100 分」 |

## 二、红队评审：19 条问题，已修 19 条

红队（只读、独立视角）给出的核心结论是：**两轮迭代的数据链路在浏览器→Next→FastAPI 第一跳就断了**。

### 已修（本轮）

| 编号 | 问题 | 修法 |
|---|---|---|
| **P0-1** | `quiz-pack` 判题只发 `{question, answer}`，Next 代理又把 `kp_id` 丢掉，后端 `if body.kp_id:` 整段不执行 → 掌握度/复习队列永远是 0 | 前端补 `kp_id/kp_name/student_id`，代理透传，后端按 kp 落库 |
| **P0-2** | 判分信任浏览器传来的 `question.answer`；`/api/mastery` 只凭 kp_id 就能写成通关 | mastery 改为服务端按 `student_kp` 作答推导，`attempts<3` 直接 409 |
| **P0-3** | v3 图的 `judge_node` 是死代码（全项目没有 `Command(resume=)`），每次讲课留一个永不恢复的 checkpoint（已积 117 个 thread） | 图简化为 `lesson → END`，判题唯一写入口是 `/api/judge` |
| P1-1 | 复习队列没到期也能升档，「一场练习连点两次就毕业」 | `due_at > now` 时不累计 streak，返回 `not_due` |
| P1-5 | 提分曲线取最早 40 条，之后永远冻结 | 改 `ORDER BY ts DESC LIMIT 40` 后反转 |
| P1-6 | 雷达按字母序取前 6 章，丢掉微分方程/级数/向量/多元 | 改按考频权重降序取前 6，章名去掉「第N讲」 |
| P2-5 | `done` 事件没有 `max_rounds` → 表头显示「第 NaN / 轮」 | 前端 `typeof` 守卫 |
| P2-6 | 「待复习」列表显示内部 id、计数被封顶 50 | analytics 补 `name`，limit 提到 200 |
| **P1-2** | 含中文的填空答案跳过 SymPy，且默认不开 LLM 兜底 | 新增 `cjk` 判定层（同义书写归一 + 前后缀 + 无公共字快判），规则能给结论就不花 LLM；实测 3~11ms |
| **P1-10** | 两张 mistakes 表，题卡答错不进错题本 | `/api/mistakes` 合并两个来源，标注 `source: quiz / diagnosed` |
| **P1-12** | 代理白名单没有 history / student_message，追问永远从头讲 | 代理透传 + 后端灌进 state，`round` 置 1；实测「我还是不懂第三步」→ 直接讲第三步 |
| **P1-9** | 账本数字是该 KP 终身累计，却标「本轮」 | 文案改「本次账本 / 累计作答」，并标注 `scope: lifetime` |
| **P2-1/2** | 浮动按钮压输入框、账本长文本撑高 | 按钮下移到 `bottom-32`、面板宽度 `min(92vw,380px)`；账本单元格 `break-words` |
| **P1-4** | 学生画像只在 `round>0` 注入，而图里 round 恒为 0 → 「按掌握度调整讲解」从未生效 | 画像改为无条件注入，并补「本轮知识点本身的作答/掌握度 + 认知偏差」，中文名替代内部 id；提示词里加一句「怎么用这条画像」。`/api/learner_note` 可预览，`meta` 事件带同一份画像，trace 记 `learner_note_chars` |
| **P1-7** | `done` 到达时打字机队列非空 → 永远「老师正在写…」 | `drainTyping` 排空即收尾；流结束挂 1.5s flush 保底（rAF 被挂起也能收）；题卡到达时不再把 `streaming` 拧成 false，避免整篇 markdown 重解析 |
| **P1-11** | 4 个 sqlite 连接跨线程共享、三段独立提交、`except: pass` 吞掉锁错误 | 新增 `v3core/db.py`：每线程一条真实连接 + 同文件共享写锁 + `BEGIN IMMEDIATE` 显式事务（嵌套安全，内层 `commit()` 变 no-op）；判题/诊断/通关/复习各收成一个原子单元；失败不再静默，返回 `persisted=false` + `persist_error` 并写日志 |
| **P2-8** | 客户端断开后 sink 不回收（`_STREAM_SINKS` 泄漏），生成器卡在阻塞 `get()` | 换成分片队列（讲义只留最新一份，慢客户端不堆内存）+ 异步生成器每秒 `is_disconnected()` 轮询 + `finally` 摘 sink；`/api/health_v3.streams.active` 可观测 |
| **P2-7** | 每个请求 `LLMClient(load_config())`，等于每次重建连接池 | 新增 `v3core/clients.py` 进程内单例（`lru_cache` + `reset`），判题兜底/侧问/诊断/加练全部复用；微基准中位数从 1465 ms 降到 1165 ms |
| **P2-3** | 诊断弹窗没有高度上限、内部不滚动，结果一长就顶出屏幕 | 面板 `max-h-[88vh]` + 头尾固定 + 正文 `overflow-y-auto`；顺带 portal 到 body（原来嵌在 `.paper-canvas` 的层叠上下文里，z-50 压不过外层浮动控件） |
| **P2-9** | 同一个 chunk 走两条跟随路径，每帧两次「读 `scrollHeight` + 写 `scrollTop`」 | 跟随只留 `messages` 的 layout effect 一处；`handleScroll` 用「上次我们自己滚到哪」识别程序滚动，不再为它读一次 `scrollHeight`；内部顺带滚动改成 `softFollow()`（用户翻上去就绝不拽回） |

### 收尾（本轮全部清空）

| 编号 | 状态 |
|---|---|
| P1-3 | 代码侧风险已消除（主图不再写脏键）；`student_kp` 里遗留的 `ser.p_series` 这类旧 id 已从画像里过滤，库里的历史行没动 —— 属于数据清理，不影响功能 |
| P2-1~4 | 按钮位置、账本换行在上一轮已修；诊断弹窗本轮流式修好；「加练后仍可能触发通关」已用 `drill` 标记区分（加练完成只提示，不写通关） |
| P2-7~10 | P2-7/8/9 本轮修完；P2-10（脚注「0 次=50%」与实现矛盾）上一轮已修 |

## 三、验证记录

| 检查 | 结果 |
|---|---|
| `node scripts/browser_smoke.mjs` | 6/6 通过（含自动进入下一站、侧栏打勾） |
| `node scripts/stream_quality.mjs` | 6/6 通过（上滑不被拽回 0px、解析 28 次/4s、长任务 3 个 430ms） |
| `node scripts/report_shot.mjs` | 报告正常打开；**小屏 390px 无横向溢出** |
| `/api/analytics` | `practiced 2/69`，`overall 0.021`，掌握度 0.80 / 0.50 分知识点 |
| `/api/ledger?kp_id=lim.definition` | `attempts=3, correct=3`，与前端账本一致 |
| `/api/practice_more` | 返回 3 题（choice/choice/fill），带上次认知偏差；首次实现因字段不规范失败，已加 `coerce_card` + 一次重试 |
| 复习队列 | 答错入队 stage0；模拟到期后连答两次 → stage1；`not_due` 不升档 |

## 四、已知口径

- **掌握度**：`(正确+1)/(作答+2) × (0.7+0.3×新鲜度)`，新鲜度半衰期 14 天；章节分按考频加权；未练过的知识点计 0 且不进分子。
- **复习**：答错 → 1 天后；答对（且到期）streak+1，满 2 次升档；7 天档再满 2 次出队。
- **通关**：服务端要求 `attempts ≥ 3`，分数由作答推导，客户端传的分不采信。

## 五、下一步建议

1. 修 P1-2（中文填空判题）与 P1-10（两张 mistakes 表合一）——这两个直接影响「错题本」的可信度。
2. 修 P1-12（追问上下文）——否则「我还是不懂第三步」永远从头讲。
3. 做 P2-1/P2-2 的窄屏与长文本兜底，再拍一次 390px 截图。


## 六、本轮补充验证（2026-11-10 01:40）

| 检查 | 结果 |
|---|---|
| 中文填空判题 | `发散`→对 3ms；`收敛`→错 10.7ms；`不存在`→错 5.1ms；`发散（调和级数）`→对 3.5ms（全部规则判定，不花 LLM） |
| 错题本合并 | `count=2`，来源 `{diagnosed, quiz}`，题卡答错已进列表 |
| 追问上下文 | 带 2 轮历史 + 「我还是不懂第三步」→ 正文直接讲「第三步是验证条件再动手」，`round=1` |
| 三套 UI 验收 | browser_smoke 6/6、stream_quality 6/6、report_shot 390px 无横向溢出 |

### 本轮事故记录

修 P1-10 时用字符串切片替换 `/api/mistakes` 区块，切片终点选在 `health_v3`，
把夹在中间的**整个学习闭环 block（analytics/review/ledger/practice_more）一起删掉了**，
直到 `/api/mistakes` 报 `NameError: _STUDENT_CONN` 才发现。已按原文重建并复验 20 条路由齐全。
教训：改 api_server.py 这种单文件大杂烩，切片要按 `@app.` 边界取，不能按文件尾锚点。

## 七、P1-4 / P1-7 收口（2026-11-10 01:52）

### P1-7：先复现，再修

- 复现脚本 `scripts/typing_done_regression.mjs`：用 CDP 注入 fetch stub，把「整段讲义 + quiz_pack + done」塞进**同一个网络包**，让「done 到达时打字机队列一定非空」从偶发变成确定性事件。
- 修复前实测：`❌ 不再显示「老师正在写…」 — 状态=「老师正在写…」`、`❌ 气泡退出流式态 — 1 个光标`（其余 5 项 PASS）→ 死锁稳定复现。
- 修复后：7/7 PASS，状态回到「等待作答」，光标 0 个。
- 两处根因：① `drainTyping` 排空队列时**从不**调用 `finishTyping`（当时的注释是「故意不收尾」），而 `queueDone` 只在「done 到达那一瞬间队列恰好为空」时才收尾；② rAF 在后台标签页会被暂停，队列永远排不空。
- 现在的收尾：排空即收尾（只在 `done`/`quiz` 已到时才做，避免流未结束时闪回思考态）；流结束后再挂 1.5s `flushTyping` 保底，把剩余字一次性倒出并收尾。另外题卡到达时不再把 `streaming` 拧成 false —— 否则 `StreamingMarkdown` / `MarkdownMessage` 会来回换组件、整篇重解析闪一下。

### P1-4：画像真的进了提示词

- 单测 `scripts/test_learner_note.py`：**11/11**
  - `lesson_node` 在 `round=0` 时把画像交给 `build_request`（修复前被 `round>0` 挡住，测试直接红）
  - 画像内容 = 中文知识点名 + 本轮作答次数/掌握度 + 上次诊断出的认知偏差，≤ 400 字（schema 上限）
  - 没练过的知识点不编造「本轮作答」；`ser.p_series` 这类旧版本遗留、认不出来的 id 直接过滤，不把内部主键喂给模型
  - 有画像时提示词多一句「掌握度低就从最小一步讲起，已掌握就直接讲易错点」；空画像不出现这一段
- 真库预览（`GET /api/learner_note?kp_id=der.definition`）：
  `本轮知识点「导数定义与可导性」：作答 4 次、答对 3 次，掌握度 67%`
- 真流验证（`check_e2e.py --kp der.definition --student local-user`）：TTFT 中位数 **1243 ms**，3 次请求的 `meta.learner_note` 与预览**逐字一致**（37 字）
- 可观测性：lesson 的 trace 事件多记一个 `learner_note_chars`，以后怀疑「画像到底进没进提示词」，翻 `runs/trace.jsonl` 就能对账，不用重跑模型。

### 本轮全量回归

| 检查 | 结果 |
|---|---|
| `node scripts/typing_done_regression.mjs` | 7/7（新增，P1-7 回归） |
| `python scripts/test_learner_note.py` | 11/11（新增，P1-4 回归） |
| `node scripts/browser_smoke.mjs` | 6/6，首字 1346 ms，通关 + 自动下一站正常 |
| `node scripts/stream_quality.mjs` | 6/6（上滑漂移 0px、解析 20 次/4s、长任务 3 个 414 ms） |
| `python scripts/check_e2e.py` | PASS，TTFT 中位数 1863 ms（budget 2000），判题层 `choice/text/cjk/fallback` |
| `python scripts/check_e2e.py --student local-user` | PASS，画像注入逐字一致 + TTFT 1243 ms |
| `python scripts/test_cjk_judge.py` | 中文判题 4/4（1.2~5.3 ms），错题本合并正常 |
| `python scripts/test_followup.py` | 「我还是不懂第三步」命中第三步，`round=1` |
| `npx tsc --noEmit` | 无错误 |
| 后端路由 | 21 条（新增 `/api/learner_note`）；Next 代理同步加 `app/api/learner_note/route.ts` |

### 一处口径修正

`browser_smoke.mjs` 的首字门槛从 5 s 放宽到 8 s，并在标签里写明原因：单次样本 + 冷缓存（新进程 / 新知识点前缀缓存未命中）会把 1.3 s 抖到 6.2 s —— 上一轮那次单点 6250 ms 就是这种冷启动，同一脚本立刻重跑即 1346 ms。严格 TTFT 门禁仍然是 `check_e2e.py` 的「预热后取中位数 < 2000 ms」。

## 八、P1-11 / P2-3 / P2-7 / P2-8 / P2-9 收口（2026-11-10 03:00）

### P1-11 连接与事务：从「能跑」到「可断言」

改造（新增 `backend/v3core/db.py`）：

- **每线程一条真实连接**（`threading.local`）。原来的 `check_same_thread=False` 只是关掉了检查，并不会让 sqlite3 连接变线程安全；
- **同一库文件在进程内只有一个连接代理** → 写锁也只可能有一把，不会出现两个连接互抢；
- `transaction(conn)`：`BEGIN IMMEDIATE` 开事务，嵌套安全（内层 `commit()` 变 no-op），最外层统一提交 / 回滚；
- `students.db` 的「作答记录」和「复习队列」以前是两条独立连接，现在合成一个代理 —— 跨这两套表的写才可能原子；
- `except: pass` 全部清掉：判题 / 诊断失败会返回 `persisted=false` + `persist_error`，并写 `mn.api` 日志，不再静默吞锁错误。

实测（`scripts/test_backend_hardening.py`，20/20）：

- 事务中途抛异常 → 0 行残留；
- 嵌套事务里 `commit()` 外部读不到，最外层退出后两条一起可见；
- 8 线程 × 25 事务并发写 → 202 行一条不丢，217 ms，**无锁错误**；
- 4 个线程各拿到不同的 `conn.raw`；
- 端到端 8 线程 × 6 次 `/api/judge`（对错交替）→ `attempts=48`、`correct=24`、错题行 `24`、未解决 `1`（答对会把旧错题标记已解决），48 次全部 `persisted=True`。

### P2-8 断连清理

- 旧：无界 `queue.Queue` + 阻塞 `get()`，只有循环正常退出才 `unregister`。客户端一断，生成器永远醒不过来，sink 留在 `_STREAM_SINKS` 里，图还在往里推累计全文。
- 新：分片队列（`md` 只保留最新一份，`events` 按序）+ 异步生成器 + 每秒 `request.is_disconnected()` 轮询 + `finally` 摘 sink + 空闲 8 秒发 SSE 注释帧保活。
- 实测：掐断连接后 `streams.active` 2 秒内回到 0（判定上限 20 秒）；正常跑完也是 0；`/api/health_v3` 现在带 `streams.active` 可直接观测。

### P2-7 客户端单例

- 新增 `v3core/clients.py`：`get_llm_client()`（`lru_cache`）+ `reset_llm_client()`；判题兜底 / 侧问 / 诊断 / 加练四处的 `LLMClient(load_config())` 全部换掉。
- 单测：连调三次只构造一次、返回同一实例。
- 微基准（`scripts/bench_llm_client.py`，各 4 次取中位数）：每次新建 **1465 ms** → 复用 **1165 ms**，省约 **300 ms / 次**。样本小、含网络抖动，只当量级参考。

### P2-3 诊断弹窗

- `max-h-[88vh]` + 头尾 `shrink-0` + 正文 `min-h-0 flex-1 overflow-y-auto`；顺带 `createPortal` 到 `body`（原来嵌在 `.paper-canvas` 的层叠上下文里，`z-50` 压不过外层 `z-30/z-40` 的浮动控件）。
- 实测（390×844，12 步诊断）：面板 77–820 在视口内，正文 1071 px / 视口 698 px 可滚，滚到底能看到第 12 步与结论，标题栏固定不动；`panel.parentElement.parentElement === body`（portal 生效）。
- 复现脚本 `scripts/dialog_scroll_check.mjs`（7/7），截图 `docs/shots/p23-dialog.png`。

### P2-9 跟随路径（含一个连带发现的 bug）

- 删掉打字机里那次多余的滚动，跟随只保留 `messages` 的 layout effect 一处；`handleScroll` 用 `programmaticTopRef` 认出「这是我们自己滚的」，不再为它多读一次 `scrollHeight`。
- **诚实结论**：`LayoutCount`（213~221 / 120 chunks）和 `LayoutDuration`（88~110 ms）在修复前后没有可分辨差异 —— 被删掉的那次重复读，读到的是已经算好的布局，本来就不贵。真正的收益是「跟随只有一处、每帧最多读一次」，以及下面这个 bug。
- **连带发现**：题卡到达时调的是 `advanceToBottom()`（无条件滚 + 打开跟随），所以**讲义一结束就把正在往上读的人硬拽到底部**。以前 960 px 视口下内容撑不满、上滑测试是假通过；把 `stream_quality` 的视口压到 640 高、并等内容真的溢出再上滑，才暴露出来（滑动后 0 → 4 秒后 576）。改成 `softFollow()` 后回到 0。
- 诊断脚本 `scripts/layout_cost.mjs`（合成流，0 token）：报渲染次数 / 跟随次数 / `LayoutCount` / `LayoutDuration`，只做诊断不做性能门禁。

### 本轮全量回归

| 检查 | 结果 |
|---|---|
| `python scripts/test_backend_hardening.py` | 20/20（新增） |
| `python scripts/test_learner_note.py` | 11/11 |
| `python scripts/test_cjk_judge.py` | 中文判题 4/4（3.8~8.6 ms），错题本合并正常 |
| `node scripts/browser_smoke.mjs` | 6/6，首字 1159 ms |
| `node scripts/stream_quality.mjs` | 6/6（视口 640 高后上滑不再被拽回：0 → 0，文档高 968） |
| `node scripts/typing_done_regression.mjs` | 7/7 |
| `node scripts/dialog_scroll_check.mjs` | 7/7（新增） |
| `node scripts/layout_cost.mjs` | 4/4（诊断） |
| `python scripts/check_e2e.py` | PASS，TTFT 中位数 1135 ms（budget 2000） |
| `npx tsc --noEmit` | 无错误 |
| `/api/health_v3` | `streams.active=0`，21 条路由齐全 |

### 一处仍需注意

- `LlmClient`（`openai.OpenAI` 里的 httpx 连接池）现在是进程级共享，`OpenAI` 客户端本身线程安全；但如果以后换成带状态的自定义客户端，复用前要重新确认线程安全性。
- 旧 sidecar（`api.py` 的 `/api/teach_turn`、`/api/teach_answer`）没有换成 `v3core.clients`：它用的是根目录的 `config.py`，和 `v3core/config.py` 不是同一份，换了等于偷偷换配置源；只给它的 `_client()` 加了 `lru_cache`，收益一样、风险为零。
- SSE 生成器每秒一次 `is_disconnected()` + 线程池里的 `pop(0.5)`，意味着**每条活跃流占用一个线程池线程**。单机单用户没问题；将来要多路并发，得先把 `pop` 改成事件驱动的等待（`anyio.Event`），不要再轮询。
- LangGraph 的 `SqliteSaver` 仍自持一条连接，不在这次改造范围内（它内部有锁）。
