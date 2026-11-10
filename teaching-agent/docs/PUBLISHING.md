# 发布与可见性说明

> 这个仓库当前是 **public**。发布前请先读这一页。

## 1. 当前状态

- 仓库：`https://github.com/AlexWang-AI/adaptive-trainer`
- 默认分支：`main`
- 可见性：**public**
- 账号：`AlexWang-AI`（本机 SSH 实际认证账号；不是 `alex-Wang`）
- `teaching-agent/textbook/tree/` 与 `teaching-agent/backend/curriculum_data.json` 含教材抽取内容，公开再分发前请确认授权。

## 2. 推荐做法（二选一）

### A. 改成 private（保留完整数据）

GitHub 仓库页：

```text
Settings → General → Danger Zone → Change visibility → Make private
```

改成 private 后，仓库里的教材树/课程表只对你有权限的成员可见。

### B. 保持 public（移除教材数据）

如果仓库必须公开，建议移除教材抽取数据，只保留代码、文档、starter_kit 示例和 pipeline 脚本：

```powershell
git rm -r teaching-agent/textbook/tree
git rm teaching-agent/backend/curriculum_data.json
git commit -m "chore: remove textbook-derived data from public repo"
git push origin main
```

然后在 `teaching-agent/README.md` 里说明：

- 教材数据不随仓库分发；
- 运行主系统前，把自有的 `textbook/tree` 和 `curriculum_data.json` 放回对应目录；
- 或先跑 `starter_kit`（自带 3 个示例知识点，不依赖教材数据）。

## 3. 密钥与隐私

- 仓库不包含 `.env`、学生数据库、`runs/*.jsonl`、教材 OCR 原文/图片。
- 如果曾经把真实 key 提交到任何仓库，立即去 DeepSeek / LangSmith 控制台轮换。
- 不要把学生姓名、作答、诊断原文、截图贴到 Issue/PR。
- 手册/评估里如果出现学生数据，先脱敏。

## 4. CI

仓库根有：

```text
.github/workflows/teaching-agent-ci.yml
```

它会在 `teaching-agent/**` 变更时跑：

- `py_compile` 核心后端；
- 判题幂等/独立答案键 14 条；
- 画像回归 11 条；
- planner 契约 9 条；
- 早期快照 93 条；
- starter_kit 18 条。

如果仓库页没有 Actions 运行记录，去 **Actions** 标签启用 workflow，或检查仓库是否禁用了 Actions。

## 5. 发布前检查清单

- [ ] 确认仓库可见性符合教材授权；
- [ ] 确认没有 `.env` / `*.db` / `runs/*.jsonl` 被跟踪；
- [ ] `git ls-files | Select-String '\.env$|\.db$|trace\.jsonl'` 为空；
- [ ] 最近一次 CI 通过；
- [ ] README 的 clone URL / 目录名与实际仓库一致；
- [ ] 如需公开，补 LICENSE（当前未声明开源许可证）。
