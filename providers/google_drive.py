import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_drive_service():
    # In production, use OAuth flow. Using a saved token.json here for simplicity.
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive', 'v3', credentials=creds)

def scan_google_drive() -> list:
    service = get_drive_service()
    normalized_photos =[]
    
    # Query for image files and request specific metadata fields
    query = "mimeType contains 'image/' and trashed = false"
    fields = "files(id, name, size, modifiedTime, imageMediaMetadata)"
    
    results = service.files().list(q=query, spaces='drive', fields=fields, pageSize=100).execute()
    items = results.get('files',[])
    
    for item in items:
        size_mb = int(item.get('size', 0)) / (1024 * 1024)
        img_meta = item.get('imageMediaMetadata', {})
        
        normalized_photos.append({
            "filename": item.get('name'),
            "source": "Google Drive",
            "size_mb": round(size_mb, 2),
            "width": img_meta.get('width'),
            "height": img_meta.get('height'),
            "last_modified": item.get('modifiedTime')
        })
        
    return normalized_photos
