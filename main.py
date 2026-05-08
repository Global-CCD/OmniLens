from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from dotenv import load_dotenv
import os
from typing import List, Dict, Any

# Import our custom cloud providers (from the previous snippets)
from providers.google_drive import scan_google_drive
from providers.s3_storage import scan_r2_bucket

# Load environment variables (API keys, bucket names) from .env file
load_dotenv()

app = FastAPI(
    title="OmniLens Multi-Cloud Pipeline",
    description="Unified API to process and retrieve photo metadata across multiple clouds.",
    version="1.0.0"
)

# In-memory database for this example. 
# (In production v1.1.0, swap this with SQLAlchemy/PostgreSQL)
photo_database: List[Dict[str, Any]] =[]

def sync_cloud_providers(provider: str = "all"):
    """
    Background task to scan providers and update the global photo database.
    This runs asynchronously so webhooks can return a 200 OK instantly.
    """
    global photo_database
    temp_db =[]
    
    try:
        if provider in ["all", "google"]:
            print("Scanning Google Drive...")
            google_photos = scan_google_drive()
            temp_db.extend(google_photos)
            
        if provider in["all", "s3"]:
            bucket_name = os.getenv("S3_BUCKET_NAME")
            if bucket_name:
                print(f"Scanning S3 Bucket ({bucket_name})...")
                s3_photos = scan_r2_bucket(bucket_name)
                temp_db.extend(s3_photos)
            else:
                print("S3_BUCKET_NAME not set in .env. Skipping S3 scan.")

        # Update the in-memory database
        if provider == "all":
            # Overwrite completely for a full scan
            photo_database = temp_db
        else:
            # Append/Update logic for specific provider webhooks.
            # We filter out existing filenames to prevent duplicates in our list.
            existing_filenames = {p['filename'] for p in photo_database}
            new_photos = [p for p in temp_db if p['filename'] not in existing_filenames]
            photo_database.extend(new_photos)
            
        print(f"Sync complete. Total photos in unified database: {len(photo_database)}")
        
    except Exception as e:
        print(f"Error during sync: {e}")


# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    """Health check and simple dashboard stats."""
    return {
        "status": "online",
        "app": "OmniLens Pipeline",
        "total_photos_indexed": len(photo_database)
    }

@app.get("/photos")
def get_all_photos():
    """Returns the unified list of normalized photo metadata."""
    return {
        "count": len(photo_database), 
        "data": photo_database
    }

@app.post("/scan")
def trigger_manual_scan(background_tasks: BackgroundTasks, provider: str = "all"):
    """
    Manually trigger a full or partial scan. 
    Uses FastAPI's BackgroundTasks so the API responds instantly without waiting.
    """
    if provider not in["all", "google", "s3"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'all', 'google', or 's3'.")
        
    background_tasks.add_task(sync_cloud_providers, provider)
    return {"message": f"Scan for '{provider}' initiated in the background."}


# ==========================================
# WEBHOOK ENDPOINTS (For "On-The-Go" Processing)
# ==========================================

@app.post("/webhook/google")
async def google_drive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Google Drive Push Notifications.
    Google sends a POST request here the exact second a new photo is uploaded from your phone.
    """
    # NOTE: In production, verify the 'X-Goog-Channel-Token' header here
    # to ensure the request is actually from Google.
    
    background_tasks.add_task(sync_cloud_providers, "google")
    return {"status": "success", "message": "Webhook received, syncing Google Drive."}

@app.post("/webhook/s3")
async def s3_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Cloudflare R2 / Backblaze B2 Event Notifications.
    Triggers automatically when a new file hits the bucket.
    """
    # NOTE: Verify webhook signature here depending on the specific S3 provider you are using.
    
    background_tasks.add_task(sync_cloud_providers, "s3")
    return {"status": "success", "message": "Webhook received, syncing S3 Bucket."}
