---
title: "Deploying FastAPI on Ubuntu VPS with Docker, Nginx & GitHub Actions"
description: "Step-by-step guide to deploying production-ready FastAPI apps on an Ubuntu VPS using Docker, Nginx, SSL, and automated GitHub Actions CI/CD."
pubDate: 2026-11-23
linkedinSummary: "Tired of high PaaS bills on Heroku or Vercel for your Python workloads? Moving your FastAPI app to a self-hosted Ubuntu VPS gives you complete architectural control while keeping infrastructure costs low. In this step-by-step guide, we demonstrate how to set up a production-ready server hardened with UFW, Docker multi-stage builds, Nginx reverse proxying, and automated GitHub Actions CI/CD pipelines. Read the full post to build a secure, zero-downtime deployment stack for your APIs today!"
affiliateDisclosure: true
draft: false
images:
  - "https://images.pexels.com/photos/1010487/pexels-photo-1010487.jpeg?auto=compress&cs=tinysrgb&h=650&w=940"
  - "https://images.pexels.com/photos/9705929/pexels-photo-9705929.jpeg?auto=compress&cs=tinysrgb&h=650&w=940"
  - "https://images.pexels.com/photos/5257445/pexels-photo-5257445.jpeg?auto=compress&cs=tinysrgb&h=650&w=940"
---

## Introduction

Platform as a Service (PaaS) providers like Heroku and Vercel offer frictionless deployment, but costs scale rapidly as application traffic increases. Running FastAPI workloads on a dedicated virtual private server (VPS)—such as DigitalOcean, Hetzner, or AWS EC2—provides total architectural control and lowers infrastructure expenses. However, deploying on raw compute requires managing process execution, security, web servers, and continuous integration pipelines manually.

This guide walks through creating a production-grade, secure, and automated deployment pipeline for Python FastAPI applications using Docker, systemd, Nginx, and GitHub Actions. Prerequisites include a basic FastAPI project codebase, SSH access to a VPS running Ubuntu 22.04 LTS or newer, and a registered domain name pointed to your server's public IP address.

## Preparing the FastAPI Application for Production

Production deployments require strict separation of configuration settings from codebase logic, explicit concurrency configuration, and clean dependency management. Utilize `pydantic-settings` to parse environment variables safely at runtime:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FastAPI Production"
    DEBUG: bool = False
    DATABASE_URL: str

    class Config:
        env_file = ".env"

settings = Settings()
```

Configure Uvicorn explicitly to use optimized event loops and worker processes based on available CPU cores. Multi-stage Docker builds ensure small container image sizes and clear separation between build-time tools and runtime environments.

```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY ./app ./app
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop"]
```

## Provisioning and Hardening the VPS

Before deploying application code, secure the host operating system against common attack vectors. Establish an SSH session as root, apply outstanding updates, and create a restricted deployment user:

```bash
apt update && apt upgrade -y
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Harden SSH access by modifying `/etc/ssh/sshd_config` to disallow remote root access and disable password authentication entirely:

```text
PermitRootLogin no
PasswordAuthentication no
```

Apply the configuration changes with `systemctl restart ssh`. Next, configure the Uncomplicated Firewall (UFW) to block incoming connections except for SSH, HTTP, and HTTPS traffic:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Install and activate `fail2ban` to monitor authentication logs and automatically drop IP addresses demonstrating brute-force signatures:

```bash
apt install fail2ban -y
systemctl enable fail2ban --now
```

## Configuring Nginx as a Reverse Proxy and SSL

Nginx serves as the frontend entry point, managing SSL/TLS termination, request buffering, and reverse proxying to Uvicorn running on local port 8000. Remove the default Nginx configuration and define a dedicated server block at `/etc/nginx/sites-available/fastapi`:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Link the site configuration to the active sites directory and verify the syntax prior to reloading the process:

```bash
ln -s /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

Provision a free, automatically renewing SSL certificate using Certbot and Let's Encrypt:

```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d api.yourdomain.com
```

## Automating Deployments with GitHub Actions

Automated continuous deployment prevents manual execution mistakes and speeds up delivery cycles. Create a deployment workflow file inside `.github/workflows/deploy.yml` triggered by commits pushed to your repository's primary branch:

```yaml
name: FastAPI CD Pipeline

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Execute Remote SSH Commands
        uses: appleboy/ssh-action@v0.1.10
        with:
          host: ${{ secrets.VPS_HOST }}
          username: deploy
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /var/www/fastapi-app
            git pull origin main
            docker build -t fastapi-app .
            docker stop fastapi-app || true
            docker rm fastapi-app || true
            docker run -d --name fastapi-app --restart always -p 127.0.0.1:8000:8000 --env-file .env fastapi-app

      - name: Validate Deployment Health
        run: |
          curl --fail --retry 5 --retry-delay 3 https://api.yourdomain.com/health || exit 1
```

Managing deployment scripts, server keys, and secrets across multiple environments can consume valuable developer velocity.

## Monitoring, Logging, and Maintenance

To maintain system reliability, set Docker container restart policies to `--restart always` or configure systemd service definitions to ensure recovery after server reboot events.

Prevent disk space exhaustion from continuous logging by configuring Docker log driver limits in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Reload the Docker daemon using `systemctl restart docker`. Combine system monitoring tools such as UptimeRobot or Prometheus with automated cron backups targeting external S3 storage.

If managing raw infrastructure, SSH keys, and firewall scripts manually slows down your development cycle, streamline your setup by using PaaS platforms like **Hatchbox** or **Coolify** via <a href="https://example.com/?ref=YOUR_AFFILIATE_ID" rel="sponsored nofollow noopener" target="_blank">your-default-product</a>.