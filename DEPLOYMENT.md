# 田间智瞰 — 线上部署指南

> 面向 UAV 视觉智能监测系统（Flask + Vue 3 单端口架构）的完整部署手册

---

## 目录

1. [架构总览](#1-架构总览)
2. [部署前代码改造](#2-部署前代码改造)
3. [服务器选型与准备](#3-服务器选型与准备)
4. [Docker 容器化](#4-docker-容器化)
5. [Nginx 反向代理与 HTTPS](#5-nginx-反向代理与-https)
6. [域名与 DNS 配置](#6-域名与-dns-配置)
7. [CI/CD 自动化部署](#7-cicd-自动化部署)
8. [日志与监控](#8-日志与监控)
9. [数据备份策略](#9-数据备份策略)
10. [安全加固](#10-安全加固)
11. [常见问题排查](#11-常见问题排查)
12. [部署检查清单](#12-部署检查清单)

---

## 1. 架构总览

### 1.1 当前架构

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────────┐
│  Flask (:5000)                          │
│  ├── /api/*  → 7 个 Blueprint API       │
│  └── /*      → 静态资源 / SPA 回退      │
│       (backend/static/ 下的 Vue 构建产物)│
└─────────────────────────────────────────┘
    │
    ├── models/*.pt   (YOLO 权重文件)
    ├── data/          (飞行架次 + YAML 注册表)
    ├── output/        (处理任务输出)
    ├── results/       (计数结果)
    └── datasets/      (数据集目录)
```

### 1.2 线上目标架构

```
用户浏览器
    │  HTTPS (443)
    ▼
┌───────────────────┐
│   Nginx (反向代理)  │  ← SSL 终止 / 静态缓存 / 限流
│   :443 / :80       │
└───────┬───────────┘
        │  proxy_pass :5000
        ▼
┌───────────────────────────┐
│  Docker 容器 (Flask + Gunicorn) │
│  ├── /api/* → Blueprint API     │
│  └── /*     → SPA 静态资源      │
└───────────────────────────┘
        │
        ├── Volume: models/    (YOLO .pt 权重)
        ├── Volume: data/      (飞行架次数据)
        ├── Volume: output/    (处理输出)
        ├── Volume: results/   (计数结果)
        └── Volume: datasets/  (数据集)
```

---

## 2. 部署前代码改造

### 2.1 关闭 Debug 模式

**文件**: `backend/config.py`

将 `DEBUG = True` 改为环境变量驱动：

```python
import os

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
PORT = int(os.environ.get("FLASK_PORT", "5000"))
```

### 2.2 引入 Gunicorn 生产服务器

Flask 自带的 `app.run()` 仅适用于开发。生产环境应使用 Gunicorn：

```bash
# 安装（已在依赖文件中添加）
pip install gunicorn
```

启动命令：

```bash
gunicorn "backend.app:create_app()" \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 4 \
  --timeout 300 \
  --access-logfile - \
  --error-logfile -
```

> **worker 数量建议**：`CPU 核心数 × 2 + 1`。由于 YOLO 推理占用 GPU 显存，建议 workers=2，避免 OOM。
> 每个 worker 内的线程数用于处理等待 I/O 的请求（如文件上传/下载）。

### 2.3 创建 `.env` 配置文件

在项目根目录创建 `.env`：

```env
# Flask
FLASK_DEBUG=0
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Gunicorn
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=300
```

在 `backend/config.py` 中读取：

```python
import os
from pathlib import Path

# 仅在开发环境加载 .env
if os.environ.get("FLASK_DEBUG", "0") == "1":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
```

### 2.4 后端 CORS 限制

**文件**: `backend/app.py` 或 CORS 初始化位置

线上环境应限制 CORS 来源：

```python
from flask_cors import CORS
import os

allowed_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000"  # 开发默认
).split(",")

CORS(app, origins=allowed_origins)
```

在 `.env` 中设置：

```env
CORS_ORIGINS=https://your-domain.com
```

### 2.5 上传文件大小限制（可调）

当前已设置 `MAX_CONTENT_LENGTH = 500MB`。在服务器内存较小的情况下，建议通过环境变量调整：

```python
app.config['MAX_CONTENT_LENGTH'] = int(
    os.environ.get("MAX_UPLOAD_MB", "500")
) * 1024 * 1024
```

---

## 3. 服务器选型与准备

### 3.1 推荐配置

| 场景 | CPU | 内存 | GPU | 磁盘 | 预算参考 |
|------|-----|------|-----|------|----------|
| **开发测试** | 2 vCPU | 4 GB | 无 (CPU推理) | 50 GB SSD | 云服务器 ~¥100/月 |
| **小规模生产** | 4 vCPU | 16 GB | RTX 4060 Ti 16G | 200 GB SSD | 自建/托管 ~¥500/月 |
| **中规模生产** | 8 vCPU | 32 GB | RTX 4090 24G / A10 | 500 GB SSD | GPU 云实例 ~¥2000/月 |
| **高并发生产** | 16+ vCPU | 64 GB | A100 40G | 1 TB SSD | 企业级 ~¥5000+/月 |

### 3.2 云服务商推荐

| 服务商 | GPU 实例类型 | 特点 |
|--------|-------------|------|
| **阿里云** | ecs.gn7i 系列 (A10/T4) | 国内访问快，文档完善 |
| **腾讯云** | GN10X/GN7 系列 | 学生优惠多 |
| **AutoDL** | 按时计费 GPU 实例 | 适合短期实验，性价比高 |
| **恒源云** | RTX 4090 等 | 价格低，适合学生 |

### 3.3 服务器初始化

```bash
# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. 安装 Docker Compose
sudo apt install docker-compose-plugin -y

# 4. 安装 NVIDIA Container Toolkit（GPU 服务器需要）
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 5. 验证 GPU 在 Docker 中可用
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

---

## 4. Docker 容器化

### 4.1 Dockerfile（GPU 版本）

在项目根目录创建 `Dockerfile`：

```dockerfile
# ===== 阶段一：构建前端 =====
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ===== 阶段二：生产运行 =====
FROM python:3.8.20-slim AS production

# 系统依赖（OpenCV 需要 libgl/libglib）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn python-dotenv

# 应用代码
COPY backend/ ./backend/
COPY config/ ./config/

# 前端构建产物（从阶段一复制）
COPY --from=frontend-build /app/backend/static ./backend/static/

# 创建数据目录
RUN mkdir -p models data output results datasets

# 环境变量
ENV FLASK_DEBUG=0
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["gunicorn", "backend.app:create_app()", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### 4.2 .dockerignore

在项目根目录创建 `.dockerignore`：

```
.git
.github
__pycache__
*.pyc
*.pyo
node_modules
frontend/node_modules
backend/static
models/*.pt
output/
results/
datasets/
data/
.env
*.log
docs/
paper_chapter/
reports/
start.ps1
```

### 4.3 docker-compose.yml

在项目根目录创建 `docker-compose.yml`：

```yaml
version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: uav-survey-app
    restart: unless-stopped
    ports:
      - "127.0.0.1:5000:5000"  # 仅本机访问，Nginx 转发
    environment:
      - FLASK_DEBUG=0
      - CORS_ORIGINS=https://your-domain.com
      - GUNICORN_WORKERS=2
      - GUNICORN_THREADS=4
    volumes:
      - ./models:/app/models
      - ./data:/app/data
      - ./output:/app/output
      - ./results:/app/results
      - ./datasets:/app/datasets
      - ./config:/app/config
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"
```

### 4.4 构建与启动

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f app

# 查看运行状态
docker compose ps
```

### 4.5 处理大文件（模型权重）

模型权重文件（`.pt`）体积较大，不建议放入镜像。两种方案：

**方案 A：挂载 Volume（推荐）**

已在 `docker-compose.yml` 中配置 `./models:/app/models`，直接将宿主机的模型文件挂载进容器。

**方案 B：运行时下载**

创建初始化脚本 `scripts/download-models.sh`：

```bash
#!/bin/bash
# 从对象存储或模型仓库下载权重
MODEL_DIR="/app/models"
BASE_URL="https://your-model-storage.com/models"

for model in yolov5su_sugarcane.pt yolov8s_sugarcane.pt yolov12s_sugarcane.pt; do
  if [ ! -f "$MODEL_DIR/$model" ]; then
    echo "Downloading $model..."
    curl -L "$BASE_URL/$model" -o "$MODEL_DIR/$model"
  fi
done
```

---

## 5. Nginx 反向代理与 HTTPS

### 5.1 安装 Nginx

```bash
sudo apt install nginx -y
sudo systemctl enable nginx
```

### 5.2 Nginx 配置

创建 `/etc/nginx/sites-available/uav-survey`：

```nginx
# HTTP → HTTPS 重定向
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # ── SSL 证书（Let's Encrypt 自动生成）──
    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # ── SSL 安全配置 ──
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # ── 上传大小（匹配后端 500MB）──
    client_max_body_size 500M;

    # ── 静态资源缓存 ──
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        proxy_pass http://127.0.0.1:5000;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # ── API 代理 ──
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 长时间推理任务超时
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # ── SPA 回退 ──
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5.3 启用配置

```bash
sudo ln -s /etc/nginx/sites-available/uav-survey /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # 移除默认站点
sudo nginx -t                                 # 验证配置
sudo systemctl reload nginx
```

---

## 6. 域名与 DNS 配置

### 6.1 域名购买

| 注册商 | 说明 |
|--------|------|
| **阿里云万网** | 国内主流，`.com` 约 ¥55/年 |
| **腾讯云** | DNSPod 解析方便 |
| **Cloudflare** | 免费 CDN + DNS，海外访问快 |

### 6.2 DNS 解析记录

在域名管理后台添加：

| 类型 | 主机记录 | 记录值 | TTL |
|------|---------|--------|-----|
| A | @ | 服务器公网 IP | 600 |
| A | www | 服务器公网 IP | 600 |

### 6.3 SSL 证书（Let's Encrypt 免费）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 自动获取并配置 SSL
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 验证自动续签
sudo certbot renew --dry-run
```

证书每 90 天自动续期。Certbot 会自动修改 Nginx 配置。

> **国内服务器注意**：域名需完成 ICP 备案后才能绑定 80/443 端口。

---

## 7. CI/CD 自动化部署

### 7.1 GitHub Actions 方案

在仓库中创建 `.github/workflows/deploy.yml`：

```yaml
name: Build and Deploy

on:
  push:
    branches: [master]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "18"

      - name: Build frontend
        run: |
          cd frontend
          npm ci
          npm run build

      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/uav-survey
            git pull origin master
            docker compose build --no-cache app
            docker compose up -d
            docker system prune -f
```

### 7.2 需要配置的 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 值 |
|-------------|---|
| `SERVER_HOST` | 服务器 IP 或域名 |
| `SERVER_USER` | SSH 用户名（如 `deploy`） |
| `SSH_PRIVATE_KEY` | SSH 私钥内容 |

### 7.3 服务器端初始化

```bash
# 在服务器上克隆仓库
sudo mkdir -p /opt/uav-survey
sudo chown $USER:$USER /opt/uav-survey
cd /opt/uav-survey
git clone https://github.com/your-username/UAV-Visual-Intelligence-System-in-Agriculture.git .

# 首次构建
docker compose up -d --build
```

---

## 8. 日志与监控

### 8.1 应用日志

Flask 日志已通过 Gunicorn 的 `--access-logfile` 和 `--error-logfile` 输出到 stdout/stderr，Docker 会自动收集。

```bash
# 实时查看日志
docker compose logs -f app

# 查看最近 100 行
docker compose logs --tail 100 app
```

### 8.2 简易健康监控脚本

创建 `scripts/health-monitor.sh`：

```bash
#!/bin/bash
# 每 5 分钟检查一次，失败时重启容器并发送通知

URL="https://your-domain.com/api/health"
WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-id"

response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL")

if [ "$response" != "200" ]; then
  echo "[$(date)] Health check failed: HTTP $response" >> /var/log/uav-monitor.log
  cd /opt/uav-survey && docker compose restart app

  # 发送飞书/钉钉告警
  curl -s -X POST "$WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"⚠ 田间智瞰服务异常，已自动重启 (HTTP $response)\"}}"
fi
```

加入 crontab：

```bash
chmod +x scripts/health-monitor.sh
crontab -e
# 添加：
*/5 * * * * /opt/uav-survey/scripts/health-monitor.sh
```

### 8.3 系统资源监控（可选）

```bash
# 安装 netdata 轻量监控
docker run -d --name=netdata \
  --cap-add SYS_PTRACE \
  -p 19999:19999 \
  -v /proc:/host/proc:ro \
  -v /sys:/host/sys:ro \
  netdata/netdata
```

访问 `http://server-ip:19999` 查看实时 CPU/GPU/内存/磁盘状态。

---

## 9. 数据备份策略

### 9.1 需要备份的目录

| 目录 | 内容 | 重要性 | 大小估算 |
|------|------|--------|----------|
| `config/` | 模型注册表 YAML | 高（易恢复） | < 1 MB |
| `data/` | 飞行架次数据 + 注册表 | 高 | 取决于上传量 |
| `results/` | 计数结果（标注图 + JSON） | 高 | 中等 |
| `models/` | YOLO 权重文件 | 高 | ~100-500 MB/个 |
| `output/` | 处理任务输出 | 中（可重算） | 较大 |
| `datasets/` | 数据集 | 中（可重建） | 较大（数GB） |

### 9.2 自动备份脚本

创建 `scripts/backup.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/uav-survey"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/opt/uav-survey"
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"

# 备份配置和结果（核心数据）
tar czf "$BACKUP_DIR/core_$DATE.tar.gz" \
  -C "$PROJECT_DIR" \
  config/ data/ results/

# 备份模型列表（不含权重文件本身，记录版本信息）
ls -lh "$PROJECT_DIR/models/" > "$BACKUP_DIR/models_manifest_$DATE.txt"

# 清理旧备份
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -name "*.txt" -mtime +$KEEP_DAYS -delete

echo "[$(date)] Backup completed: core_$DATE.tar.gz"
```

加入 crontab（每天凌晨 3 点）：

```
0 3 * * * /opt/uav-survey/scripts/backup.sh >> /var/log/uav-backup.log 2>&1
```

### 9.3 异地备份（可选）

```bash
# 同步到对象存储（以阿里云 OSS 为例）
ossutil cp "$BACKUP_DIR/core_$DATE.tar.gz" \
  oss://your-bucket/uav-survey-backups/
```

---

## 10. 安全加固

### 10.1 服务器基础安全

```bash
# 1. 修改 SSH 端口（避免 22 端口扫描）
sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# 2. 配置防火墙（仅开放必要端口）
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp   # SSH
sudo ufw allow 80/tcp     # HTTP（重定向到 HTTPS）
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable

# 3. 禁止 root 登录
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 10.2 应用层安全

| 措施 | 说明 | 当前状态 |
|------|------|----------|
| HTTPS 强制 | Nginx HTTP→HTTPS 重定向 | 需配置 |
| CORS 限制 | 仅允许指定域名 | 需改造（2.4 节） |
| 上传文件校验 | 检查文件类型/大小 | 已有 500MB 限制 |
| Debug 关闭 | 生产环境禁用 Flask debug | 需改造（2.1 节） |
| Rate Limiting | API 限流防滥用 | 建议添加 |

### 10.3 Nginx 限流配置（补充）

在 Nginx 配置中 `server` 块外添加：

```nginx
# API 限流：每 IP 每秒 10 次请求
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# 上传接口限流：每 IP 每秒 2 次
limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=2r/s;
```

在 `location /api/` 块内添加：

```nginx
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    # ... proxy_pass 配置
}
```

---

## 11. 常见问题排查

### 11.1 Docker 容器启动失败

```bash
# 查看容器日志
docker compose logs app

# 常见原因：
# 1. 模型文件未挂载 → 检查 volumes 配置
# 2. 端口被占用 → lsof -i :5000
# 3. 镜像构建失败 → 重新 docker compose build --no-cache
```

### 11.2 GPU 不可用

```bash
# 检查宿主机 GPU
nvidia-smi

# 检查 NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 检查 docker-compose.yml 中的 deploy 配置
```

### 11.3 前端白屏

```bash
# 确认构建产物存在
docker compose exec app ls -la /app/backend/static/

# 重新构建前端
docker compose exec app sh -c "cd /app && npm install && npm run build"
# 或在宿主机上重新构建镜像
docker compose build --no-cache app
docker compose up -d
```

### 11.4 上传大文件超时

确保 Nginx 和 Docker 的超时配置匹配：

- Nginx: `proxy_read_timeout 600s;` + `client_max_body_size 500M;`
- Gunicorn: `--timeout 300`
- Docker: `start_period: 40s`（healthcheck）

### 11.5 推理速度慢

| 原因 | 排查 | 解决 |
|------|------|------|
| 未使用 GPU | 检查 PyTorch CUDA 是否可用 | 确认 `nvidia-smi` 正常 + CUDA 版本匹配 |
| 模型太大 | 对比各模型推理速度 | 使用 `yolov12n` 替代 `yolov12s` |
| 高分辨率图 | 分块数量多 | 调整 `tiling.py` 中的 tile_size |
| 显存不足 | 检查 GPU 使用率 | 减少 Gunicorn workers 数量 |

---

## 12. 部署检查清单

在正式上线前，逐项确认：

### 代码改造
- [ ] `config.py` 中 `DEBUG` 改为环境变量控制
- [ ] CORS 限制为正式域名
- [ ] `.env` 文件已创建（不含敏感信息）
- [ ] `requirements.txt` 中已加入 `gunicorn` 和 `python-dotenv`

### 服务器环境
- [ ] Docker 和 Docker Compose 已安装
- [ ] NVIDIA Container Toolkit 已安装（GPU 场景）
- [ ] `nvidia-smi` 在 Docker 容器内正常工作

### 容器化
- [ ] `Dockerfile` 已创建并构建成功
- [ ] `.dockerignore` 已创建
- [ ] `docker-compose.yml` 已配置（端口/Volumes/GPU）
- [ ] 模型权重文件已放置在 `models/` 目录
- [ ] `docker compose up -d` 启动成功
- [ ] 健康检查接口 `/api/health` 返回正常

### 域名与证书
- [ ] 域名已购买并完成 ICP 备案（国内服务器）
- [ ] DNS A 记录已指向服务器 IP
- [ ] Nginx 反向代理配置完成
- [ ] SSL 证书已获取（Let's Encrypt）
- [ ] HTTP → HTTPS 重定向生效
- [ ] 浏览器访问 `https://your-domain.com` 正常加载

### 自动化
- [ ] GitHub Actions 部署流水线已配置
- [ ] SSH 密钥和 Secrets 已设置
- [ ] 推送代码后自动构建部署正常

### 监控与备份
- [ ] 健康监控脚本已配置
- [ ] 定时备份任务已加入 crontab
- [ ] 日志收集正常

### 安全
- [ ] 防火墙已开启，仅开放必要端口
- [ ] SSH 端口已修改，禁止 root 登录
- [ ] API 限流已配置
- [ ] 敏感配置通过环境变量传递，未提交到代码仓库

---

## 附录：快速部署命令汇总

```bash
# 1. 克隆代码
git clone https://github.com/your-username/UAV-Visual-Intelligence-System-in-Agriculture.git
cd UAV-Visual-Intelligence-System-in-Agriculture

# 2. 放置模型权重
cp /path/to/*.pt models/

# 3. 配置环境变量
cp .env.example .env
vim .env  # 编辑配置

# 4. 构建并启动
docker compose up -d --build

# 5. 验证
curl http://localhost:5000/api/health

# 6. 配置 Nginx + SSL
sudo certbot --nginx -d your-domain.com

# 7. 完成
echo "部署完成！访问 https://your-domain.com"
```