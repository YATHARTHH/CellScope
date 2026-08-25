# 🚀 Guide 7: Deployment, Docker, CI/CD & Security Hardening

This guide covers **production deployment strategies**, **Docker containerization**, **GitHub Actions CI/CD pipelines**, and **OWASP security hardening** implemented across the CellScope platform.

---

## 🐳 1. Docker & Containerization

CellScope can be containerized using a multi-stage Docker build that bundles the React Vite static frontend and FastAPI backend into a lightweight, isolated production container.

### A. Production `Dockerfile`
```dockerfile
# Stage 1: Build React Vite Frontend Static Production Bundle
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python FastAPI Backend Environment
FROM python:3.11-slim AS runner
WORKDIR /app

# Install system dependencies for OpenCV & Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt-get/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code, MLOps models, and static frontend build
COPY backend/ ./backend/
COPY mlops/ ./mlops/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Security: Run as non-root user
RUN useradd -m cellscopeuser && chown -R cellscopeuser:cellscopeuser /app
USER cellscopeuser

EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### B. Single-Command `docker-compose.yml`
```yaml
version: '3.8'

services:
  cellscope:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: cellscope_app
    ports:
      - "8000:8000"
    environment:
      - TF_ENABLE_ONEDNN_OPTS=0
      - PYTHONUNBUFFERED=1
    volumes:
      - cellscope_data:/app/backend/analyses.db
    restart: unless-stopped

volumes:
  cellscope_data:
```

---

## 🔄 2. GitHub Actions CI/CD Pipeline (`.github/workflows/ci.yml`)

Automate code quality, backend testing, and frontend build verification on every Git push or pull request:

```yaml
name: CellScope CI Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Backend Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov

      - name: Run Pytest Test Suite
        run: |
          pytest backend/tests/ -v --cov=backend

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js 20
        uses: actions/setup-node@v3
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install Frontend Dependencies
        run: |
          cd frontend
          npm ci

      - name: Verify TypeScript & Build Vite Production Bundle
        run: |
          cd frontend
          npx vite build
```

---

## 🛡️ 3. Security Hardening & OWASP Compliance

CellScope incorporates security controls to protect against common web vulnerabilities (OWASP Top 10):

### A. HTTP Security Headers (`backend/main.py`)
On every REST API response, FastAPI injects security headers:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### B. Upload File Sanitization & EXIF Stripping
- **File Format Validation**: Rejects unsupported file extensions (`.exe`, `.sh`, `.php`), allowing only `.tif`, `.tiff`, `.png`, `.jpg`, and `.jpeg`.
- **Size Limitation**: Rejects uploads exceeding 50 MB to prevent Denial of Service (DoS) disk exhaustion.
- **EXIF Metadata Stripping**: Strips potentially sensitive location/camera EXIF tags from uploaded image buffers using PIL before processing.

### C. In-Memory Sliding Window Rate Limiting
- Prevents API spamming by limiting clients to **60 requests / minute** per IP address.

### D. 21 CFR Part 11 Cryptographic Audit Trail
- Computes SHA-256 cryptographic signatures `sha256(id:hash:count:timestamp)` for all stored records, guaranteeing data immutability.

---

## 🌐 4. NGINX Reverse Proxy Configuration (Production SSL/TLS)

For institutional production deployment behind NGINX:

```nginx
server {
    listen 443 ssl http2;
    server_name cellscope.lab.institution.edu;

    ssl_certificate /etc/ssl/certs/cellscope.crt;
    ssl_certificate_key /etc/ssl/private/cellscope.key;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript image/svg+xml;

    # Static Vite frontend assets
    location / {
        root /var/www/cellscope/dist;
        try_files $uri $uri/ /index.html;
    }

    # FastAPI REST backend proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
```
