import io
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate_drive():
    # 1. Try Loading from Environment Variable (Vercel Production)
    if os.environ.get('GOOGLE_TOKEN'):
        try:
            token_info = json.loads(os.environ.get('GOOGLE_TOKEN'))
            return build('drive', 'v3', credentials=Credentials.from_authorized_user_info(token_info, SCOPES))
        except Exception as e:
            print(f"❌ Env Token Error: {e}")
            return None

    # 2. Try Loading from Local File (Local Development)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        return build('drive', 'v3', credentials=creds)
    
    return None

def upload_photo_to_drive(image_bytes, filename, parent_id):
    try:
        service = authenticate_drive()
        if not service: return None

        # On Vercel, we can't easily search/create folders dynamically without more permissions.
        # We will upload directly to the parent folder to keep it simple and robust.
        
        file_metadata = {
            'name': filename,
            'parents': [parent_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype='image/jpeg')
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # Make public/reader
        try:
            service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except:
            pass 

        return file.get('webViewLink')

    except Exception as e:
        print(f"❌ Drive Upload Error: {e}")
        return None