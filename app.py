# app.py
import os
import re
import json
import base64
import pytz
import csv
from datetime import datetime
from dotenv import load_dotenv
from io import StringIO
from flask import Response

# Load env vars before anything else
load_dotenv() 

from flask import Flask, render_template, request, jsonify, session, redirect
import gspread
from google.oauth2.credentials import Credentials 
from drive_manager import upload_photo_to_drive 

app = Flask(__name__)

# [SECURE] Load Configuration
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_dev_key")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SHEET_NAME = "SRIT_Visitor_Database"

# NEW: Define IST Timezone
IST = pytz.timezone('Asia/Kolkata')

ALLOWED_DEPTS = ['cse', 'it', 'me', 'sh', 'ece', 'eee']
FACULTY_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._]+[.](" + "|".join(ALLOWED_DEPTS) + r")@sritcbe\.ac\.in$")

# 1. DEFINE THE MAPPING LOGIC
DEPT_MAPPING = {
    'cse': 'CSE',
    'it': 'IT',
    'me': 'MECH',
    'ece': 'ECE',
    'eee': 'EEE',
    'sh': 'Science and Humanities',
    'ce': 'CIVIL'
}

ws_users = None
ws_visitors = None
ws_bookings = None

def connect_to_db():
    global ws_users, ws_visitors, ws_bookings
    try:
        creds = None
        if os.getenv('GOOGLE_TOKEN'):
            token_info = json.loads(os.getenv('GOOGLE_TOKEN'))
            creds = Credentials.from_authorized_user_info(token_info, ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        elif os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])

        if creds:
            gc = gspread.authorize(creds)
            if SHEET_ID:
                sh = gc.open_by_key(SHEET_ID)
            else:
                sh = gc.open(SHEET_NAME)
                
            ws_users = sh.worksheet("Users")
            ws_visitors = sh.worksheet("Visitors")
            ws_bookings = sh.worksheet("Bookings")
            print("✅ Connected to Google Database.")
            return True
        else:
            print("❌ No credentials found.")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

connect_to_db()

def get_dept_from_email(email):
    try:
        local_part = email.split('@')[0]
        dept_code = local_part.split('.')[-1].lower()
        return DEPT_MAPPING.get(dept_code, "STAFF")
    except:
        return "STAFF"

# --- ROUTES ---

@app.route('/')
def index():
    firebase_config = {
        'apiKey': os.getenv('FIREBASE_API_KEY'),
        'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN'),
        'projectId': os.getenv('FIREBASE_PROJECT_ID'),
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET'),
        'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
        'appId': os.getenv('FIREBASE_APP_ID')
    }
    return render_template('login.html', firebase_config=firebase_config)

@app.route('/api/login', methods=['POST'])
def api_login():
    if not ws_users: connect_to_db()
    data = request.json
    email = data.get('email').lower().strip()
    name = data.get('name')

    if FACULTY_EMAIL_PATTERN.match(email):
        dept = get_dept_from_email(email)
        session['user'] = email
        session['role'] = 'Faculty'
        session['name'] = name
        session['dept'] = dept
        try:
            cell = ws_users.find(email)
        except gspread.exceptions.CellNotFound:
             try: ws_users.append_row([email, 'Faculty', name, dept])
             except: pass
        return jsonify({'status': 'success', 'redirect': '/dashboard'})

    try:
        cell = ws_users.find(email)
        role = ws_users.cell(cell.row, 2).value 
        session['user'] = email
        session['role'] = role
        session['name'] = name
        session['dept'] = 'ADMIN' if role == 'Admin' else 'SECURITY'
        return jsonify({'status': 'success', 'redirect': '/dashboard'})
    except: pass 

    return jsonify({'status': 'error', 'message': 'Access Denied: User not found.'})

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    role = session['role']
    if not ws_visitors: connect_to_db()

    if role == 'Security': 
        return render_template('security_dashboard.html')
    elif role == 'Faculty': 
        return render_template('faculty_dashboard.html')
    elif role == 'Admin':
        visitors_data = []
        active_visitors = []
        upcoming_bookings = []
        past_bookings = []
        try:
            v_rows = ws_visitors.get_all_values()
            for index, row in enumerate(v_rows):
                row.append(index + 1)
            visitors_data = v_rows[1:][-20:] 
            visitors_data.reverse() 
            active_visitors = [row for row in v_rows[1:] if len(row) > 10 and row[10] == ""]
            active_visitors.reverse()

            b_rows = ws_bookings.get_all_values()
            for row in b_rows[1:]:
                if len(row) > 7:
                    if row[7] == "Pending": upcoming_bookings.append(row)
                    else: past_bookings.append(row)
            upcoming_bookings.reverse()
            past_bookings.reverse()
        except Exception as e: 
             print(f"Dashboard Data Error: {e}")
        return render_template('admin_dashboard.html', visitors=visitors_data, active_visitors=active_visitors, bookings=upcoming_bookings, past_bookings=past_bookings, sheet_id=SHEET_ID, drive_id=DRIVE_FOLDER_ID)
    return "Unknown Role"

@app.route('/api/book_visitor', methods=['POST'])
def book_visitor():
    if session.get('role') not in ['Faculty', 'Admin']: return jsonify({'error': 'Unauthorized'})
    data = request.json
    
    try:
        mobile_to_check = str(data.get('mobile')).strip()
        all_bookings = ws_bookings.get_all_values()
        for row in all_bookings[1:]:
            if len(row) > 7:
                existing_mobile = str(row[4]).strip()
                status = row[7]
                if existing_mobile == mobile_to_check and status == "Pending":
                    return jsonify({'status': 'error', 'message': 'Duplicate: Visitor has pending booking.'})
    except: pass

    # Use provided host details if available (Editable Fields), else fallback to Session
    host_name = data.get('to_meet', session['name'])
    host_dept = data.get('department', session.get('dept', 'STAFF'))
    booked_by_email = session['user']

    row = [
        datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        booked_by_email,
        host_name,
        host_dept,
        data['mobile'],
        data['name'],
        data['purpose'],
        "Pending",
        data.get('company', '-'),
        data.get('vehicle', '-')
    ]
    try:
        ws_bookings.append_row(row)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    
@app.route('/api/get_today_bookings', methods=['GET'])
def get_today_bookings():
    if session.get('role') != 'Security': return jsonify([])
    try:
        if not ws_bookings: connect_to_db()
        all_bookings = ws_bookings.get_all_values()
        pending_list = []
        for row in all_bookings[1:]:
            if len(row) > 7 and row[7] == "Pending":
                vehicle_val = row[9] if len(row) > 9 else "-"
                pending_list.append({
                    'time': row[0],
                    'booked_by': row[2],
                    'dept': row[3],
                    'mobile': row[4],
                    'visitor': row[5],
                    'purpose': row[6],
                    'company': row[8] if len(row) > 8 else "-",
                    'vehicle_number': vehicle_val
                })
        return jsonify(pending_list)
    except: return jsonify([])

# NEW: Endpoint for Faculty to see their bookings
@app.route('/api/get_user_bookings', methods=['GET'])
def get_user_bookings():
    if 'user' not in session: return jsonify([])
    try:
        if not ws_bookings: connect_to_db()
        all_rows = ws_bookings.get_all_values()
        my_bookings = []
        user_email = session['user']
        
        # Iterate and filter by "Booked By" (Col 2, index 1)
        for row in all_rows[1:]:
            if len(row) > 1 and row[1] == user_email:
                my_bookings.append({
                    'time': row[0],
                    'visitor': row[5],
                    'mobile': row[4],
                    'purpose': row[6],
                    'status': row[7]
                })
        # Return newest first
        return jsonify(list(reversed(my_bookings)))
    except Exception as e:
        return jsonify([])

# NEW: Endpoint for Security to get Active Visitors Table
@app.route('/api/get_active_visitors', methods=['GET'])
def get_active_visitors():
    if session.get('role') != 'Security': return jsonify([])
    try:
        if not ws_visitors: connect_to_db()
        all_rows = ws_visitors.get_all_values()
        active_list = []
        
        # Skip header, iterate all
        for row in all_rows[1:]:
            # Check if OUT TIME (Col 11, index 10) is empty
            if len(row) > 10 and row[10] == "":
                active_list.append({
                    'in_time': row[1],
                    'mobile': row[2],
                    'name': row[3],
                    'vehicle': row[12] if len(row) > 12 else "-",
                    'to_meet': row[7],
                    'dept': row[8],
                    'photo': row[9]
                })
        return jsonify(list(reversed(active_list))) # Show latest first
    except: return jsonify([])

@app.route('/api/check_visitor', methods=['GET'])
def check_visitor():
    mobile = request.args.get('mobile')
    try:
        cell_list = ws_bookings.findall(mobile)
        for cell in cell_list:
            if cell.col == 5: 
                row = ws_bookings.row_values(cell.row)
                if row[7] == "Pending":
                    vehicle = row[9] if len(row) > 9 else ""
                    return jsonify({'found': True, 'is_booking': True, 'name': row[5], 'purpose': row[6], 'booked_by': row[2], 'department': row[3], 'company': row[8], 'vehicle': vehicle, 'to_meet': row[2]})
    except: pass
    try:
        cells = ws_visitors.findall(mobile)
        if cells:
            row = ws_visitors.row_values(cells[-1].row)
            vehicle = row[12] if len(row) > 12 else ""
            # Returns data from LAST visit
            return jsonify({
                'found': True, 'is_booking': False, 
                'name': row[3], 'designation': row[4], 
                'company': row[5], 'laptop': row[6], 
                'to_meet': row[7], 'department': row[8], 
                'vehicle': vehicle
            })
    except: pass
    return jsonify({'found': False})

@app.route('/api/get_next_id', methods=['GET'])
def get_next_id():
    try:
        if not ws_visitors: connect_to_db()
        current_count = len(ws_visitors.col_values(1)) 
        return jsonify({'next_id': current_count})
    except: return jsonify({'next_id': '---'})

@app.route('/api/entry', methods=['POST'])
def entry():
    if session.get('role') != 'Security': return jsonify({'error': 'Unauthorized'})
    try:
        data = request.json
        image_data = data['image']
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        
        now = datetime.now(IST)
        filename = f"{now.strftime('%d-%m-%Y')}_{data['mobile']}_{now.strftime('%H%M%S')}.jpg"
        photo_url = ""

        try:
            if not DRIVE_FOLDER_ID: raise Exception("GOOGLE_DRIVE_FOLDER_ID not set in Env")
            drive_link = upload_photo_to_drive(image_bytes, filename, DRIVE_FOLDER_ID)
            if drive_link: photo_url = drive_link
        except Exception as e:
            print(f"⚠️ Drive Failed: {e}")
            return jsonify({'status': 'error', 'message': 'Photo Upload Failed.'})

        new_row = [
            now.strftime("%d-%m-%Y"),
            now.strftime("%I:%M %p"),
            data['mobile'],
            data['name'],
            data['designation'],
            data['company'],
            data.get('laptop', '-'),
            data['to_meet'],
            data['department'],
            photo_url,
            "", 
            session['user'],
            data.get('vehicle', '-') 
        ]
        ws_visitors.append_row(new_row)
        
        try:
            cell_list = ws_bookings.findall(data['mobile'])
            for cell in cell_list:
                if cell.col == 5 and ws_bookings.cell(cell.row, 8).value == "Pending": 
                    ws_bookings.update_cell(cell.row, 8, "Arrived")
        except: pass

        return jsonify({'status': 'success', 'pass_id': len(ws_visitors.get_all_values()), 'date': new_row[0], 'in_time': new_row[1], 'photo': photo_url})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# UPDATED EXIT LOGIC to support Custom Time
@app.route('/api/exit', methods=['POST'])
def exit_visitor():
    data = request.json
    mobile = str(data.get('mobile')).strip()
    custom_time = data.get('out_time') # Optional custom time
    
    try:
        # 1. Get ALL data
        all_rows = ws_visitors.get_all_values()
        target_row_index = -1
        target_out_time = None
        
        # 2. Iterate BACKWARDS
        total_rows = len(all_rows)
        for i in range(total_rows - 1, 0, -1): 
            row = all_rows[i]
            row_mobile = str(row[2]).strip() # Col 3 is Mobile
            
            if row_mobile == mobile:
                target_row_index = i + 1 
                if len(row) > 10: target_out_time = row[10]
                else: target_out_time = "" 
                break 
        
        if target_row_index == -1:
             return jsonify({'status': 'error', 'message': 'Visitor not found in database'})
             
        if not target_out_time or str(target_out_time).strip() == "":
            # Determine Out Time (Custom or Now)
            if custom_time:
                # Expecting format "HH:MM" from input type="time"
                # Convert 14:30 -> 02:30 PM
                try:
                    t_obj = datetime.strptime(custom_time, "%H:%M")
                    out_time = t_obj.strftime("%I:%M %p")
                except:
                    out_time = datetime.now(IST).strftime("%I:%M %p")
            else:
                out_time = datetime.now(IST).strftime("%I:%M %p")

            ws_visitors.update_cell(target_row_index, 11, out_time)
            return jsonify({'status': 'success', 'out_time': out_time})
        else:
            return jsonify({'status': 'error', 'message': f'Already OUT (Time: {target_out_time})'})

    except Exception as e:
        print(f"Exit Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# ... [Admin routes remain the same] ...
@app.route('/api/admin/filter_data', methods=['POST'])
def filter_data():
    if session.get('role') != 'Admin': 
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    start_str = data.get('from')
    end_str = data.get('to')

    if not ws_visitors: connect_to_db()
    
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        
        # Get all values including the row index logic
        all_rows = ws_visitors.get_all_values()
        headers = all_rows[0]
        filtered_rows = []

        # Start from 1 to skip header
        for idx, row in enumerate(all_rows[1:]): 
            try:
                # idx starts at 0, so actual sheet row is idx + 2 (Header is 1)
                sheet_row_number = idx + 2 
                
                # Check Date (Column A / Index 0)
                row_date = datetime.strptime(row[0], "%d-%m-%Y").date()
                
                if start_date <= row_date <= end_date:
                    # Append the Sheet Row Number (Pass ID) to the end of the row data
                    # This ensures the frontend has the ID to display
                    row.append(sheet_row_number)
                    filtered_rows.append(row)
            except (ValueError, IndexError):
                continue

        return jsonify({
            'status': 'success',
            'headers': headers,
            'data': filtered_rows
        })
    except Exception as e:
        print(f"Filter Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/api/admin/download_report', methods=['GET'])
def download_report():
    if session.get('role') != 'Admin': return "Unauthorized", 403
    
    start_str = request.args.get('from')
    end_str = request.args.get('to')
    
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        
        all_rows = ws_visitors.get_all_values()
        
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(all_rows[0]) # Header
        
        for row in all_rows[1:]:
            try:
                row_date = datetime.strptime(row[0], "%d-%m-%Y").date()
                if start_date <= row_date <= end_date:
                    cw.writerow(row)
            except: continue

        output = si.getvalue()
        
        # UPDATED: Filename with today's date
        today_str = datetime.now(IST).strftime("%d-%m-%Y")
        filename = f"SRIT_Visitor_Report_{today_str}.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return str(e), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)