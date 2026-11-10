﻿# -*- coding: utf-8 -*-
"""一键启动（PowerShell 版，比 .bat 更可靠地等待健康检查）。

    powershell -ExecutionPolicy Bypass -File scripts/start_all.ps1
"""

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = 'C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

Write-Host '[1/3] Python 后端 :8008' -ForegroundColor Cyan
Start-Process -FilePath 'cmd.exe' `
  -ArgumentList '/k', "cd /d `"$root\backend`" && `"$py`" -m uvicorn api_server:app --host 127.0.0.1 --port 8008" `
  -WorkingDirectory "$root\backend"

Write-Host '[2/3] Next.js 前端 :3000' -ForegroundColor Cyan
# 生产模式：SSE 首字稳定在 1.4~1.9s；dev 模式（Turbopack）偶尔会把流缓冲到 4s+
$built = Test-Path (Join-Path $root '.next\BUILD_ID')
$webCmd = if ($built) { 'npm run start' } else { 'npm run dev' }
Write-Host ("     模式：" + $(if ($built) { 'production (已构建)' } else { 'dev (首次会慢，建议先 npm run build)' }))
Start-Process -FilePath 'cmd.exe' `
  -ArgumentList '/k', "cd /d `"$root`" && $webCmd" `
  -WorkingDirectory $root

Write-Host '[3/3] 等待后端健康检查…' -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8008/api/health_v3' -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { }
  Start-Sleep -Milliseconds 800
}

if (-not $ok) {
  Write-Host '后端未就绪，请查看 8008 窗口的报错。' -ForegroundColor Red
  exit 1
}

Write-Host '后端就绪，等待前端编译…' -ForegroundColor Green
for ($i = 0; $i -lt 90; $i++) {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { break }
  } catch { }
  Start-Sleep -Seconds 1
}

Start-Process 'http://localhost:3000'
Write-Host '已打开 http://localhost:3000' -ForegroundColor Green
