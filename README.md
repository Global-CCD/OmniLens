


# OmniLens: Multi-Cloud Photo Pipeline

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Deploy](https://img.shields.io/badge/Deployment-Cloud%20%7C%20Local-orange.svg)]()

## 📖 Overview
**OmniLens** is a unified Python-based web application and automated scripting pipeline designed for photographers, developers, and creators who need to upload, process, and catalog photos across various cloud providers while on the go. 

Whether you are walking through a city automatically uploading shots from your phone to Google Drive, or syncing bulk raw files to a Cloudflare R2 bucket, OmniLens detects new uploads instantly, extracts EXIF metadata (size, resolution, camera make), and compiles a unified, searchable database of all your assets—regardless of where they are physically stored.

```
omnilens/
├── main.py                  # Main FastAPI application and webhook endpoints
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variables template
├── providers/
│   ├── __init__.py
│   ├── google_drive.py      # Google Drive API and metadata extractor
│   └── s3_storage.py        # Cloudflare R2 / Backblaze B2 API + Range Requests
└── utils/
    ├── __init__.py
    └── image_processor.py   # Pillow EXIF and byte parsing
```

---

## ✨ Features
*   **Universal Cloud Support:** Works natively with Consumer Clouds (Google Drive, Microsoft OneDrive) and S3-compatible Object Storage (Backblaze B2, Cloudflare R2).
*   **Instant "On-The-Go" Processing:** Webhook-enabled architecture catches and processes photos the exact second they are uploaded from your mobile device.
*   **Deep Metadata Extraction:** Automatically pulls EXIF data (resolution, camera info, focal length, ISO) directly from APIs or via smart byte-range image parsing.
*   **Unified Dashboard:** Aggregates metadata from completely different storage platforms into one normalized dictionary/database format.
*   **Flexible Hosting:** Designed to run anywhere—from a $5 cloud VPS or Serverless functions, to a local Raspberry Pi in your living room.

---

## 🚀 Roadmap: Future Features
*   [ ] **AI Auto-Tagging:** Integration with Google Cloud Vision / OpenAI Vision to automatically generate tags based on image content.
*   [ ] **Cross-Cloud Sync & Backup:** Automatically duplicate files (e.g., watch Google Drive for new phone uploads, and automatically copy them to cheaper Backblaze B2 storage).
*   [ ] **Thumbnail Generation:** Auto-generate and cache low-res WebP thumbnails for faster dashboard loading.
*   [ ] **Map/Location View:** Extract GPS coordinates from EXIF data to map your "on-the-go" walking photo routes.
*   [ ] **Smart Deduplication:** Hash checking to ensure duplicate photos uploaded to different clouds are flagged and merged.

---
---

## 🛠️ Technical Deep Dive: Integration & Processing 
*(Incorporating Full Implementation Details)*

Building this pipeline requires handling different platforms natively. Here is how OmniLens handles APIs, metadata, and data processing.

### 1. Connecting to the Cloud Storage Providers
To access files across these different platforms, OmniLens uses their respective Python SDKs:

*   **Google Drive:** 
    *   **Libraries:** `google-api-python-client` and `google-auth`
    *   **Mechanics:** Uses OAuth 2.0 to authenticate. Uses the `files().list()` method to generate file lists.
*   **Microsoft OneDrive:**
    *   **Libraries:** `azure-identity` and `msgraph-sdk-python` (or the `requests` library to call the Microsoft Graph API).
    *   **Mechanics:** Authenticates via OAuth 2.0. The Microsoft Graph API queries `/me/drive/root/children` to get file lists.
*   **Backblaze B2 & Cloudflare R2:**
    *   **Libraries:** `boto3` (The Amazon Web Services SDK for Python).
    *   **Mechanics:** Both services utilize **S3-compatible APIs**. OmniLens uses `boto3` by changing the `endpoint_url` to point to Backblaze or Cloudflare, supplying API access keys directly.

### 2. Getting Filenames, Size, and Metadata
The way OmniLens retrieves metadata (size, resolution, EXIF) differs significantly depending on the service architecture:

**A. Consumer Clouds (Google Drive & OneDrive)**
These services automatically scan and extract metadata from images upon upload. The image *does not* need to be downloaded to get its resolution.
*   **Google Drive:** By requesting the `imageMediaMetadata` field in the API call, the JSON response natively returns width, height, camera make, model, focal length, ISO, filename, and file size.
*   **OneDrive:** The Microsoft Graph API contains an `image` or `photo` facet in the JSON response for image files, instantly providing width, height, and EXIF data.

**B. Object Storage (Backblaze B2 & Cloudflare R2)**
These are "dumb" storage buckets. They store exact byte arrays and do not automatically extract image resolutions.
*   `boto3.client('s3').list_objects_v2()` quickly provides the **filename** (Key), **file size** (Size), and **last modified date**.
*   **Resolution/EXIF Extraction:** OmniLens handles this via two methods:
    1.  Downloading the file temporarily into memory to read it.
    2.  **HTTP Range Requests:** Downloading just the first few kilobytes of the image (which contains the EXIF/header data) to save bandwidth, and parsing that.

### 3. Processing Images in Python
For Backblaze, Cloudflare, or local processing, OmniLens utilizes the `Pillow` (PIL) library.

```python
from PIL import Image
from io import BytesIO

# Assuming 'image_bytes' is fetched via boto3 from Backblaze/Cloudflare
img = Image.open(BytesIO(image_bytes))
width, height = img.size
format = img.format       # e.g., 'JPEG'
exif_data = img.getexif() # Extracts camera metadata
```

### 4. High-Level App Architecture
1.  **Frontend (UI):** Interface to trigger connections (OAuth) or enter R2/B2 API keys.
2.  **Backend (FastAPI/Flask):** Handles OAuth flows, stores API keys securely via `.env` files, and makes asynchronous calls to gather file lists.
3.  **Data Normalization Engine:** Maps the drastically different JSON responses from Google vs. Cloudflare into a unified dictionary format:
    `{'filename': 'walk_01.jpg', 'source': 'Google Drive', 'size_mb': 2.4, 'width': 1920, 'height': 1080}`
4.  **Database:** Stores the generated list in SQLite or PostgreSQL for fast searching, sorting, and filtering without needing to hit cloud APIs repeatedly.

**Security & Best Practices:** 
*   **Bandwidth Avoidance:** Cloudflare R2 has zero egress fees, but Backblaze egress costs money. Range requests mitigate high bandwidth bills.
*   **Pagination:** A `while` loop implementation utilizing pagination tokens handles cloud drives with thousands of files.

---
---

## 🌍 Deployment & Hosting Options: On-The-Go Uploads
*(Incorporating Full Hosting Details)*

Because the core use case involves **taking photos while walking and uploading them on the go**, the hosting choice dictates how OmniLens receives and processes photos. 

### The Core Trigger: Polling vs. Webhooks
*   **Polling:** OmniLens wakes up every 10 minutes, checks the cloud for new files, and processes them. Easy to set up locally.
*   **Webhooks (Event Triggers):** The moment your phone uploads a photo, Google Drive or Cloudflare sends a "ping" (HTTP POST) to OmniLens. **Requires a publicly accessible internet address.**

Here are the supported hosting options depending on your needs:

### Option 1: Remote Server (Cloud Hosting)
*Best for instant processing, high reliability, and easy dashboard access from your phone.*

If hosted remotely, OmniLens is always on, has high bandwidth, and can receive webhooks instantly.

*   **Platform-as-a-Service (PaaS) (Render, Railway, Heroku):** Easiest option. Push Python code to GitHub, and it hosts automatically (~$5-$10/mo).
*   **Virtual Private Server (VPS) (DigitalOcean, Hetzner, Linode):** Total control over a Linux environment (~$4-$6/mo). Excellent data center internet speeds. Requires manual Nginx/Gunicorn setup.
*   **Serverless Functions (AWS Lambda, Cloudflare Workers):** OmniLens goes to sleep until an upload wakes it up. Virtually **free** for personal use as you only pay for milliseconds of compute time. 

**Pros of Remote Hosting:**
*   Instant webhook reception.
*   Lightning-fast data center speeds for downloading images to extract EXIF data.
*   Easy to access the web dashboard via your phone browser while out walking.

### Option 2: Local Machine at Home (Home Server, PC, Raspberry Pi)
*Best for saving money, creating physical backups, and ultimate privacy.*

**Challenges & Solutions for Local Hosting:**
*   **The Webhook Problem:** Home routers block the incoming internet traffic required for instant cloud notifications.
    *   *Solution:* Run **Cloudflare Tunnels** or **ngrok** alongside OmniLens to create a secure, public URL pointing to your local app.
*   **Remote Dashboard Access:** You cannot access `localhost:5000` from your phone while walking.
    *   *Solution:* Install a mesh VPN like **Tailscale** on both your phone and home server to securely access the dashboard from anywhere.
*   **Bandwidth Bottlenecks:** Downloading thousands of Object Storage photos to extract metadata relies heavily on your home ISP's download speed.

### 💡 Hosting Recommendations
1.  **For a live mobile dashboard:** Go with a **Remote Server (VPS/PaaS)**. It processes instantly, has a real domain name, and won't bottleneck your home internet.
2.  **For local physical backups:** Go with **Local Hosting + Cloudflare Tunnels**. Process metadata instantly while simultaneously downloading a hard copy of the photo to an external drive at your house as you shoot.
3.  **For zero monthly costs:** Go with **Serverless Functions**. Create an event-driven backend that extracts metadata and updates your database the exact second a photo hits the cloud, without paying for a 24/7 server.
