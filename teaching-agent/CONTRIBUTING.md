# Contributing

## 先读

1. [`docs/handbook/handbook.md`](docs/handbook/handbook.md) 第 2–4 章：环境、代码地图、请求链路。
2. [`docs/AGENT_STANDARD.md`](docs/AGENT_STANDARD.md)：新增 agent 的目录结构、五条硬规矩、DoD。
3. [`ARCHITECTURE.md`](ARCHITECTURE.md)：当前拓扑与已知债。

## 分支 / 提交

```text
feat/<scope>-<short>
fix/<bug>-<short>
docs/<topic>
```

提交示例：

```text
feat(judge): 支持独立答案键
fix(sse): 客户端断开后清理 sink
test(judge): 增加 attempt 幂等回归
```

## 改代码前

- 不要改 `contracts.py` / `curriculum_data.json` / 旧 `api.py`，除非任务明确要求；
- 改 prompt 必须同步 schema/checks/测试；
- 写库必须在 `db.transaction` 里，且考虑幂等；
- 不要把整段历史/整本书塞进 prompt。

## 提交前必须跑

```powershell
python -m py_compile backend\api_server.py backend\v3core\student.py backend\v3core\judge.py
python scripts\test_judge_ledger.py
python scripts\test_learner_note.py
python -m pytest backend\agents\planner\test_contract.py -q
```

涉及前端：

```powershell
npx tsc --noEmit
```

涉及 SSE/真实模型：

```powershell
python scripts\check_e2e.py --direct --kp l01-b01-k01 --samples 1
```

## PR 描述

- 改了什么、为什么；
- 怎么验证（命令 + 输出）；
- 影响面（接口/表/前端）；
- 回滚方式；
- 截图/trace（如涉及 UI/流式）。

## 数据与隐私

- 不提交 `.env`、`backend/data/*.db`、`runs/*.jsonl`、学生原始作答；
- 教材树来自教辅抽取，公开前确认授权；
- 截图前先脱敏学生姓名/作答。
