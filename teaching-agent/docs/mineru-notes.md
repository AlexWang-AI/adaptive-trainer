# MinerU 运行手册（实测，非战略）

> 本文件记录设备上的实测参数与坑，供复跑用。战略条款见 `../战略.md`。

## 1. 关键配置（改这里才算数）

`C:\Users\明\.mineru\config.yaml`

```yaml
doclib:
  auth:
    token: <本机 token>
model:
  onnx_device: cpu        # ← 必须是 cpu
  base_dir: C:\mineru_models
```

**为什么必须 cpu**：`onnx_device: gpu` 走 DirectML（Intel Iris Xe），在 241 页之后的重内容页上会**无报错直接死掉**（进程消失、stderr 无 traceback）。切到 cpu 后同一批稳定跑通。

**注意**：`mineru config set` 需要 doclib 服务在跑，否则报「本地 mineru 服务未运行」。直接改 yaml 更可靠（改完新进程即生效）。

## 2. 参数

| 项 | 值 | 理由 |
|---|---|---|
| 档位 | `--tier basic`（纯 ONNX） | standard 的 llama.cpp 在本机中文路径下初始化崩溃 |
| 批大小 | **15 页** | 30 页批在重内容段（极限计算+大量例题）必崩 |
| 单批超时 | 15 分钟 | 超时即杀、记 FAIL、继续下一批 |
| 速度（CPU） | 约 **38 秒/页** | 15 页 ≈ 9.5 分钟 |
| 模型目录 | `C:\mineru_models` | 中文路径会让 llama.cpp 报 Unicode 错 |

## 3. 已跑过的分片

| 分片 | 页 | 状态 |
|---|---|---|
| p001_030 ~ p211_240（8 个） | 1–240 | ✅ |
| q241_255 | 241–255 | ✅（CPU 模式首次成功） |
| q256_270 起 | 256– | 进行中 |

## 4. 编码修正（每个分片解析完都要做）

MinerU 输出是「UTF-8 字节被当 GBK 解码」的乱码，逐行反转即可：

```python
def fix(line):
    try:
        return line.encode("gbk").decode("utf-8")
    except Exception:
        return line
```

**注意**：必须整行做，逐字做会丢字节。修复后的文件统一放 `textbook/chunks/fixed/`，不要和原始分片混在一起（否则会被统计成"新分片"）。

## 5. 进程管理

- 用 `Start-Process -WindowStyle Hidden` 起独立进程，不要挂在 agent 会话的后台任务上（会话结束会被回收）
- `.ps1` 必须存成 **UTF-8 with BOM**，否则 Windows PowerShell 会把中文路径读成乱码
- 单批超时用 `$p.WaitForExit(ms)`（单调计时），不要用文件时间戳判断（本机系统时钟会漂移）
