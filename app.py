import os
import re
import json
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect
import gspread
from google.oauth2.credentials import Credentials 
from drive_manager import upload_photo_to_drive 

app = Flask(__name__)
app.secret_key = "SRIT_GATEPASS_SECRET_KEY"

# ==========================================
# ⚠️ CONFIGURATION 
# ==========================================
SHEET_NAME = "SRIT_Visitor_Database"
SHEET_ID = "19MqFYkcmkJ7BfVaiR-Lc1tWlApByh4_cTWeUanuI-ng" 
DRIVE_FOLDER_ID = "14cKg8YpnBmgDkT6yoPKx0SGFj4kcujc8" 
# ==========================================

ALLOWED_DEPTS = ['cse', 'it', 'me', 'sh', 'ece', 'eee']
FACULTY_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._]+[.](" + "|".join(ALLOWED_DEPTS) + r")@sritcbe\.ac\.in$")

# Define global variables for worksheets
ws_users = None
ws_visitors = None
ws_bookings = None

# --- CONNECT TO DATABASE (UNIVERSAL) ---
def connect_to_db():
    global ws_users, ws_visitors, ws_bookings
    try:
        creds = None
        
        # A. Check Environment Variable (Vercel Production)
        if os.environ.get('GOOGLE_TOKEN'):
            token_info = json.loads(os.environ.get('GOOGLE_TOKEN'))
            creds = Credentials.from_authorized_user_info(token_info, ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
            
        # B. Check Local File (Local Development)
        elif os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])

        if creds:
            gc = gspread.authorize(creds)
            sh = gc.open(SHEET_NAME)
            ws_users = sh.worksheet("Users")
            ws_visitors = sh.worksheet("Visitors")
            ws_bookings = sh.worksheet("Bookings")
            print("✅ Connected to Google Database.")
            return True
        else:
            print("❌ No credentials found (checked Env Var and token.json).")
            return False
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

# Connect immediately on start
connect_to_db()

# --- HELPER: PARSE DEPT ---
def get_dept_from_email(email):
    try:
        return email.split('@')[0].split('.')[-1].upper()
    except:
        return "STAFF"

# --- ROUTES ---
# ... (Keep existing imports)

# --- ROUTES ---
@app.route('/')
def index():
    # Pass Firebase Config from Env Vars to the HTML
    firebase_config = {
        'apiKey': os.environ.get('FIREBASE_API_KEY'),
        'authDomain': "security-srit.firebaseapp.com",
        'projectId': "security-srit",
        'storageBucket': "security-srit.firebasestorage.app",
        'messagingSenderId': "414935445280",
        'appId': "1:414935445280:web:73771b05508c8a99c8f145"
    }
    return render_template('login.html', firebase_config=firebase_config)

# ... (Keep the rest of the file unchanged)

@app.route('/api/login', methods=['POST'])
def api_login():
    if not ws_users: connect_to_db()
    
    data = request.json
    email = data.get('email').lower().strip()
    name = data.get('name')

    try:
        cell = ws_users.find(email)
        role = ws_users.cell(cell.row, 2).value 
        session['user'] = email
        session['role'] = role
        session['name'] = name
        return jsonify({'status': 'success', 'redirect': '/dashboard'})
    except gspread.exceptions.CellNotFound:
        pass
    except Exception as e:
        print(f"Login Sheet Error: {e}")
        pass 

    if FACULTY_EMAIL_PATTERN.match(email):
        try:
            dept = get_dept_from_email(email)
            ws_users.append_row([email, 'Faculty', name, dept])
            session['user'] = email
            session['role'] = 'Faculty'
            session['name'] = name
            return jsonify({'status': 'success', 'redirect': '/dashboard'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f"DB Error: {str(e)}"})

    return jsonify({'status': 'error', 'message': 'Access Denied: User not found in database.'})

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
            # Fetch Visitors
            v_rows = ws_visitors.get_all_values()
            visitors_data = v_rows[1:][-20:] 
            visitors_data.reverse() 
            active_visitors = [row for row in v_rows[1:] if len(row) > 10 and row[10] == ""]
            active_visitors.reverse()

            # Fetch Bookings
            b_rows = ws_bookings.get_all_values()
            for row in b_rows[1:]:
                if len(row) > 7:
                    if row[7] == "Pending":
                        upcoming_bookings.append(row)
                    else:
                        past_bookings.append(row)
            upcoming_bookings.reverse()
            past_bookings.reverse()
        except Exception as e: 
             print(f"⚠️ Dashboard Data Error: {e}")

        return render_template('admin_dashboard.html', 
                             visitors=visitors_data, 
                             active_visitors=active_visitors,
                             bookings=upcoming_bookings,
                             past_bookings=past_bookings,
                             sheet_id=SHEET_ID, 
                             drive_id=DRIVE_FOLDER_ID)
    
    return "Unknown Role"

@app.route('/api/book_visitor', methods=['POST'])
def book_visitor():
    if session.get('role') not in ['Faculty', 'Admin']: return jsonify({'error': 'Unauthorized'})
    data = request.json
    
    if session['role'] == 'Admin':
        host_name = data.get('to_meet', session['name'])
        host_dept = data.get('department', 'ADMIN')
        booked_by_email = session['user']
    else:
        host_name = session['name']
        host_dept = get_dept_from_email(session['user'])
        booked_by_email = session['user']

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        booked_by_email,
        host_name,
        host_dept,
        data['mobile'],
        data['name'],
        data['purpose'],
        "Pending",
        data.get('company', '-') 
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
        all_bookings = ws_bookings.get_all_values()
        pending_list = []
        for row in all_bookings[1:]:
            if len(row) > 7 and row[7] == "Pending":
                pending_list.append({
                    'time': row[0],
                    'booked_by': row[2],
                    'dept': row[3],
                    'mobile': row[4],
                    'visitor': row[5],
                    'purpose': row[6],
                    'company': row[8]
                })
        return jsonify(pending_list)
    except Exception as e:
        return jsonify([])

@app.route('/api/check_visitor', methods=['GET'])
def check_visitor():
    mobile = request.args.get('mobile')
    try:
        cell_list = ws_bookings.findall(mobile)
        for cell in cell_list:
            if cell.col == 5: 
                row = ws_bookings.row_values(cell.row)
                if row[7] == "Pending":
                    return jsonify({
                        'found': True, 'is_booking': True, 
                        'name': row[5], 'purpose': row[6], 
                        'booked_by': row[2], 'department': row[3], 'company': row[8]
                    })
    except: pass
        
    try:
        cells = ws_visitors.findall(mobile)
        if cells:
            row = ws_visitors.row_values(cells[-1].row)
            return jsonify({
                'found': True, 'is_booking': False,
                'name': row[3], 'designation': row[4], 
                'company': row[5], 'laptop': row[6],
                'to_meet': row[7], 'department': row[8]
            })
    except: pass
    return jsonify({'found': False})

@app.route('/api/entry', methods=['POST'])
def entry():
    if session.get('role') != 'Security': return jsonify({'error': 'Unauthorized'})
    try:
        data = request.json
        image_data = data['image']
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        
        now = datetime.now()
        filename = f"{now.strftime('%d%m%Y')}_{data['mobile']}_{now.strftime('%H%M%S')}.jpg"
        photo_url = ""

        # 1. ALWAYS USE DRIVE UPLOAD (Required for Vercel & Sync)
        try:
            drive_link = upload_photo_to_drive(image_bytes, filename, DRIVE_FOLDER_ID)
            if drive_link:
                photo_url = drive_link
                print("✅ Uploaded to Drive")
            else:
                raise Exception("Drive upload failed")
        except Exception as e:
            print(f"⚠️ Drive Failed: {e}")
            return jsonify({'status': 'error', 'message': 'Photo Upload Failed. Check Internet.'})

        # 2. SAVE TO SHEETS
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
            session['user']
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

@app.route('/api/exit', methods=['POST'])
def exit_visitor():
    data = request.json
    try:
        cell_list = ws_visitors.findall(str(data.get('mobile')))
        if not cell_list: return jsonify({'status': 'error', 'message': 'Visitor not found'})
        last_cell = cell_list[-1]
        
        if ws_visitors.cell(last_cell.row, 11).value: return jsonify({'status': 'error', 'message': 'Already OUT'})
        ws_visitors.update_cell(last_cell.row, 11, datetime.now().strftime("%I:%M %p"))
        return jsonify({'status': 'success', 'out_time': datetime.now().strftime("%I:%M %p")})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)