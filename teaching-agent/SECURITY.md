# Security

## 这个仓库里有什么 / 没有什么

**有**

- 讲课智能体代码、提示词、课程表、教材树 JSON、前端、文档、测试。
- 已脱敏的示例配置 `.env.example`。

**没有**

- 任何 `.env`、API Key、LangSmith Key、GitHub Token。
- `backend/data/*.db`、`runs/*.jsonl`、学生作答/诊断原文。
- `node_modules`、`.next`、教材 OCR 原文、扫描 PDF、图片。

## 当前安全状态（必须知道）

这套代码是**教学/演示系统**，不是生产多租户系统：

1. **没有认证**：`student_id` 由客户端传；`/api/analytics`、`/api/ledger`、`/api/mistakes` 可按 id 读。
2. **没有对象级授权**：知道别人的 `student_id` 就可能读其学习数据。
3. **旧后端 `backend/api.py` 仍挂载**：6 个旧端点用 `MemorySaver`，且没有新栈的加固。
4. **学生输入直入 prompt**：`history` / `student_message` 未做注入检测。
5. **原始作答/思路会落库**：`mistakes` 表保存原文，未做保留期限/删除接口。

## 生产前最低检查清单

- [ ] 加认证（JWT / OIDC / 反向代理 auth），`student_id` 从 token 取；
- [ ] analytics/ledger/mistakes 做对象级授权；
- [ ] 关闭旧 `api.py` 路由（410）或整体移除；
- [ ] 学生输入做长度/注入/内容安全过滤；
- [ ] 数据保留期限 + 删除接口 + 脱敏；
- [ ] 审计日志（谁在何时改了掌握度/通关）；
- [ ] 限流与成本上限；
- [ ] 不要把 `.env`、`data/*.db`、`runs/*.jsonl` 提交到 git。

## 报告漏洞

这是个人项目，没有正式 SLO。请在仓库 Issue 中描述复现步骤，不要贴真实学生数据或 Key。
