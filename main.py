from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv
import os

# Import our cloud providers
from providers.google_drive import scan_google_drive
from providers.s3_storage import scan_r2_bucket

load_dotenv()

app = FastAPI(title="OmniLens Multi-Cloud Pipeline")

# In-memory database for this example (Swap with SQLite/PostgreSQL in production)
photo_database =
