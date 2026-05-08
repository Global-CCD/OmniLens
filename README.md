# OmniLens: Multi-Cloud Photo Pipeline

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

## 📖 Overview

**OmniLens** is a unified Python-based web application and automated pipeline that aggregates photo metadata across multiple cloud storage providers into a single, searchable database.

**Current Status:** v3.0 MVP — Core architecture complete with database persistence, pagination, retry logic, webhook verification, and comprehensive EXIF extraction.

### Supported Providers (Implemented)
| Provider | Status | Features |
|----------|--------|----------|
| **Google Drive** | ✅ Implemented | OAuth2, pagination, full EXIF, GPS, token refresh |
| **Cloudflare R2** | ✅ Implemented | S3-compatible, range requests, pagination |
| **Backblaze B2** | ✅ Implemented | S3-compatible, Bandwidth Alliance egress optimization |
| **Microsoft OneDrive** | 🚧 Planned | Microsoft Graph API integration |

### Architecture
```
omnilens/
├── main.py                  # FastAPI app with endpoints, CORS, rate limiting
├── config.py                # Pydantic Settings for env vars
├── database.py              # SQLAlchemy async models (Photo, SyncLog)
├── requirements.txt         # Pinned dependencies
├── .env.example             # Environment template
├── Dockerfile               # Production container
├── docker-compose.yml       # Local orchestration
├── pytest.ini               # Test configuration
├── providers/
│   ├── __init__.py          # Abstract CloudProvider interface + registry
│   ├── google_drive.py      # Google Drive with pagination & token refresh
│   └── s3_storage.py        # S3-compatible (R2/B2) with range requests
├── utils/
│   ├── __init__.py
│   ├── image_processor.py   # Pillow EXIF + GPS + header parsing
│   └── retry.py             # Exponential backoff decorator
└── tests/
    ├── __init__.py
    ├── test_main.py         # API endpoint tests
    └── test_image_processor.py  # EXIF extraction tests
```

---

## ✨ Implemented Features

### Core
- **Database Persistence**: Async SQLite (default) or PostgreSQL via SQLAlchemy 2.0
- **Unified Metadata Schema**: Normalized `Photo` model across all providers
- **Full EXIF Extraction**: Camera make/model, focal length, ISO, aperture, shutter speed, GPS coordinates, timestamps
- **Duplicate Prevention**: Source + source_id based upsert (not filename-only)

### Reliability
- **Pagination**: All providers handle unlimited library sizes via token-based pagination
- **Retry Logic**: Exponential backoff with jitter for all cloud API calls
- **Token Refresh**: Automatic OAuth2 token refresh for Google Drive
- **Sync Logging**: Audit trail of all scan operations with success/failure tracking

### Security
- **Webhook Verification**: HMAC-SHA256 signature verification (S3) + channel token validation (Google Drive)
- **Rate Limiting**: Per-IP rate limits via slowapi (configurable)
- **CORS**: Configurable allowed origins
- **Input Validation**: Pydantic models on all endpoints

### API Endpoints
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| GET | `/` | Health check + stats | 60/min |
| GET | `/photos` | List photos (paginated, filterable) | 60/min |
| GET | `/photos/{id}` | Get single photo by ID | 60/min |
| POST | `/scan` | Trigger manual scan | 10/min |
| GET | `/sync-history` | View sync operation logs | 30/min |
| POST | `/webhook/google` | Google Drive push notification | 120/min |
| POST | `/webhook/s3` | S3 event notification | 120/min |

---

## 🚀 Roadmap

| Feature | Status | Target |
|---------|--------|--------|
| AI Auto-Tagging | 🚧 Planned | v3.1 |
| Cross-Cloud Sync | 🚧 Planned | v3.2 |
| Thumbnail Generation | 🚧 Planned | v3.2 |
| Map/Location View | 🚧 Planned | v3.3 |
| Smart Deduplication (perceptual hash) | 🚧 Planned | v3.3 |
| Microsoft OneDrive Provider | 🚧 Planned | v3.1 |
| Web Dashboard (React/Vue) | 🚧 Planned | v3.2 |

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- Docker (optional)
- Google Cloud project with Drive API enabled (for Google Drive)
- Cloudflare R2 or Backblaze B2 account (for S3-compatible storage)

### 1. Clone & Install
```bash
git clone https://github.com/yourusername/omnilens.git
cd omnilens
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required variables:**
```env
# Google Drive
GOOGLE_CLIENT_SECRETS_FILE=client_secrets.json
GOOGLE_TOKEN_FILE=token.json

# S3-Compatible (R2/B2)
S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
S3_ACCESS_KEY=your_key
S3_SECRET_KEY=your_secret
S3_BUCKET_NAME=your-bucket
```

### 3. Google Drive OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth2 credentials (Desktop app type)
3. Download `client_secrets.json` to project root
4. Run once to authenticate: `python -c "from providers.google_drive import GoogleDriveProvider; GoogleDriveProvider()._get_credentials()"`

### 4. Run
```bash
# Development
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker-compose up -d
```

### 5. Test
```bash
pytest
```

---

## 🌍 Deployment

### Docker (Recommended)
```bash
docker build -t omnilens .
docker run -p 8000:8000 --env-file .env omnilens
```

### PaaS (Render, Railway, Heroku)
1. Set environment variables in dashboard
2. Push to GitHub
3. Connect repository to PaaS

### VPS (DigitalOcean, Hetzner, Linode)
```bash
# Using Gunicorn + Uvicorn workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Serverless (AWS Lambda, Cloudflare Workers)
Use [Mangum](https://github.com/jordaneremieff/mangum) adapter for ASGI on Lambda.

---

## 📊 Cost Analysis

| Provider | Storage | Egress | API Ops | Notes |
|----------|---------|--------|---------|-------|
| **Cloudflare R2** | $0.015/GB/mo | **$0** | $0.004/1M req | Zero egress fees |
| **Backblaze B2** | $0.005/GB/mo | $0.01/GB | Free | **Free egress via Cloudflare Bandwidth Alliance** |
| **Google Drive** | Free (15GB) | N/A | Quota limited | 1,000 req/100s/user |

**Bandwidth Optimization:**
- Range requests download only first 2MB for EXIF extraction
- Full download fallback only for small files (<5MB) when range insufficient
- Estimated 90%+ bandwidth savings vs full file downloads

---

## 🔒 Security Best Practices

1. **Never commit `.env` or `token.json`** — add to `.gitignore`
2. **Rotate API keys quarterly**
3. **Use webhook secrets** — configure `S3_WEBHOOK_SECRET` and `GOOGLE_WEBHOOK_TOKEN`
4. **Run behind HTTPS** in production (Cloudflare Tunnel, Nginx, or PaaS)
5. **Limit CORS origins** — don't use `*` in production
6. **Monitor sync logs** — check `/sync-history` for anomalies

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test file
pytest tests/test_main.py -v
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

Please ensure:
- Code passes `ruff check .` and `black --check .`
- Tests pass (`pytest`)
- Type hints pass (`mypy .`)
