<#
.SYNOPSIS
  低空智瞰（UAV 智能监测管理系统）一键启动脚本
.DESCRIPTION
  1. 检查 Python / Node 环境
  2. 安装后端依赖（如未安装）
  3. 构建前端到 backend/static（如产物缺失）
  4. 启动 Flask 服务（:5000，同时提供 API 与前端静态资源）
  5. 打开浏览器访问 http://localhost:5000
#>

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }

# ---------- 0. 解析 Python 解释器 ----------
# 优先使用 uav-vis conda 环境（含 cv2/torch/ultralytics 完整推理能力），
# 找不到则回退到当前 shell 的默认 python（推理可能不可用）。
$PY = "python"   # 默认值，后续若找到 uav-vis 则替换为绝对路径
$envBase = Join-Path $env:USERPROFILE ".conda\envs\uav-vis"
$envPy = Join-Path $envBase "python.exe"
if (Test-Path $envPy) {
    $PY = $envPy
    Write-Step "检测到 conda 环境: uav-vis"
} else {
    Write-Warn "未找到 uav-vis 环境（$envPy），将使用默认 python 运行（推理功能可能不可用）"
}

# ---------- 1. 环境检查 ----------
Write-Step "检查运行环境"
$pythonOk = $false
try { $pyVer = (& $PY --version 2>&1); Write-Host "    Python: $pyVer"; $pythonOk = $true } catch { Write-Warn "未检测到 Python，请安装 Python 3.10+" }
try { $nodeVer = (node --version 2>&1); Write-Host "    Node:   $nodeVer" } catch { Write-Warn "未检测到 Node，前端构建需要 Node 18+" }

if (-not $pythonOk) { exit 1 }

# ---------- 2. 后端依赖 ----------
Write-Step "检查后端依赖"
$needInstall = $false
foreach ($pkg in @("flask", "cv2", "yaml", "numpy")) {
    & $PY -c "import $pkg" 2>$null
    if ($LASTEXITCODE -ne 0) { $needInstall = $true; break }
}
if ($needInstall) {
    Write-Host "    安装 requirements.txt ..."
    & $PY -m pip install -r requirements.txt
} else {
    Write-Host "    后端依赖已就绪"
}

# 检测/计数推理依赖（可选，缺失时算法广场 API 以降级模式运行）
& $PY -c "import torch, ultralytics" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "未检测到 torch / ultralytics：算法广场的检测与计数推理将不可用（模型管理/列表/mock 页面正常）"
    Write-Warn "    如需完整推理功能，请：pip install torch ultralytics"
}

# ---------- 3. 前端构建 ----------
Write-Step "检查前端构建产物"
$staticIndex = Join-Path $ROOT "backend\static\index.html"
if (-not (Test-Path $staticIndex)) {
    Write-Host "    backend/static 缺失，开始构建前端 ..."
    Push-Location (Join-Path $ROOT "frontend")
    if (-not (Test-Path "node_modules")) {
        Write-Host "    安装前端依赖 ..."
        npm install --no-fund --no-audit
    }
    Write-Host "    执行 npm run build ..."
    npm run build
    Pop-Location
    Write-Host "    前端构建完成 -> backend/static/"
} else {
    Write-Host "    前端构建产物已存在"
}

# ---------- 4. 模型权重提示 ----------
$modelsDir = Join-Path $ROOT "models"
if (-not (Test-Path $modelsDir)) { New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null }
$hasWeights = (Get-ChildItem -Path $modelsDir -Filter "*.pt" -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
if (-not $hasWeights) {
    Write-Warn "models/ 目录未发现 *.pt 权重文件"
    Write-Warn "    检测/计数推理需要将 4 个 best.pt 放入 models/ 并按 config/models.yaml 命名："
    Write-Warn "      yolov5su_sugarcane_best.pt / yolov8s_sugarcane_best.pt / yolov11s_sugarcane_best.pt / yolov12s_sugarcane_best.pt"
}

# ---------- 5. 启动服务 ----------
Write-Step "启动 Flask 服务（http://localhost:5000）"
Write-Step "后端 Python: $PY"
$url = "http://localhost:5000"
# 延迟打开浏览器
Start-Job -ScriptBlock { param($u) Start-Sleep -Seconds 3; Start-Process $u } -ArgumentList $url | Out-Null

& $PY -m backend.app
