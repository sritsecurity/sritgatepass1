import io
import os
import json
import pytz # NEW: For Timezone
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
load_dotenv()
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/drive']

# NEW: Define IST Timezone
IST = pytz.timezone('Asia/Kolkata')

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

def get_or_create_daily_folder(service, root_folder_id):
    """
    Checks for a folder named 'DD-MM-YYYY' (in IST) inside the root_folder_id.
    Creates it if it doesn't exist.
    """
    # FIX: Use IST instead of Server Time (UTC)
    folder_name = datetime.now(IST).strftime("%d-%m-%Y")
    
    if not root_folder_id:
        print("⚠️ Warning: root_folder_id is Missing! Uploading to Drive Root.")
        return None

    try:
        # Search for the folder
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{root_folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields='files(id)').execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']
        else:
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [root_folder_id]
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            print(f"📂 Created new daily folder: {folder_name}")
            return folder.get('id')
            
    except Exception as e:
        print(f"❌ Error creating/finding daily folder: {e}")
        # Fallback to root folder if subfolder creation fails
        return root_folder_id

def upload_photo_to_drive(image_bytes, filename, root_folder_id):
    try:
        service = authenticate_drive()
        if not service: return None

        # 1. Get correct folder (Daily Subfolder)
        target_folder_id = get_or_create_daily_folder(service, root_folder_id)

        # 2. Upload File (If target is None, it uploads to Root)
        file_metadata = {'name': filename}
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]
        
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype='image/jpeg')
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # 3. Make Public (Reader)
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