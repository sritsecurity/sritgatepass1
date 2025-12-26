# SRIT Visitor Gate Pass System 🛡️

A centralized digital **Visitor Management System** developed for **Sri Ramakrishna Institute of Technology (SRIT)**.  
This web-based application streamlines visitor entry, faculty appointments, and gate-level security operations through a secure, cloud-enabled workflow.

---

## 🚀 Features

### 👮 Security Dashboard
- **Fast Visitor Entry:** Register visitors quickly with automatic retrieval of previous details using mobile numbers.
- **Live Photo Capture:** Built-in webcam integration to capture visitor photographs instantly.
- **Gate Pass Generation:** Automatically generates and prints a professional gate pass containing visitor details and photo.
- **Active Visitor Tracking:** Real-time monitoring of all visitors currently present on campus.
- **Check-Out Control:** Seamless visitor exit process with support for instant or backdated checkout times.

### 👨‍🏫 Faculty Portal
- **Advance Visitor Booking:** Faculty members can pre-schedule visitor appointments to reduce gate congestion.
- **Booking History:** View past and upcoming visitor schedules.
- **Smart Auto-Fill:** Reduces repetitive data entry by learning from previous visitor records.

### 👑 Admin Console
- **Analytics Dashboard:** Overview of live visitors, pending appointments, and total entry counts.
- **Report Generation:** Filter records by date range and export data in CSV format for audits and analysis.
- **Complete Logs:** Access full visitor history and faculty booking records.
- **System Resources:** Direct access to the connected Google Sheets database and Drive photo storage.

---

## 🎯 Objectives

- Digitize and standardize the visitor entry process at SRIT
- Improve campus security and traceability
- Reduce manual paperwork and errors
- Enable real-time monitoring of visitor movement
- Provide audit-ready visitor reports for administration

---

## 🧩 System Roles & Access

| Role      | Access Level |
|----------|-------------|
| Security | Visitor entry, photo capture, check-in & check-out |
| Faculty  | Visitor pre-booking and appointment tracking |
| Admin   | Full access, analytics, reports, and system data |

---

## 🛠️ Technology Stack

- **Backend:** Python (Flask)
- **Database:** Google Sheets API (cloud-based, real-time storage)
- **File Storage:** Google Drive API (secure image storage with daily folder segregation)
- **Authentication:** Firebase Authentication (Google Sign-In)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Deployment:** Vercel / Localhost

---

## 🔐 Security & Privacy Considerations

- Google Sign-In authentication for authorized access
- Secure OAuth-based Google API access
- Visitor photos stored in protected Drive folders
- No sensitive personal data exposed publicly
- Environment variables used for all secrets

---

## 📈 Scalability & Extensibility

The system is designed to be easily extended with:
- SMS or email notifications for faculty
- QR code–based gate passes
- ID card scanning integration
- Role-based permission expansion
- Centralized database migration (MySQL / PostgreSQL)

---

## 📋 Prerequisites

- Python 3.x
- Google Cloud Project with Drive & Sheets APIs enabled
- OAuth 2.0 credentials (`credentials.json`)
- Firebase project for authentication

---

## ⚙️ Installation & Setup

### Clone the Repository
```bash
git clone https://github.com/yourusername/srit-gatepass-system.git
cd srit-gatepass-system
````

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file (see Configuration section).

### Generate Google OAuth Token

```bash
python setup_drive.py
```

### Run the Application

```bash
python app.py
```

Access the app at:

```
http://localhost:5000
```

---

## 🔐 Configuration

```env
FLASK_SECRET_KEY="your_secure_secret_key"
FLASK_ENV="development"

GOOGLE_SHEET_ID="your_google_sheet_id"
GOOGLE_DRIVE_FOLDER_ID="your_drive_folder_id"

GOOGLE_TOKEN='{"token": "...", "refresh_token": "..."}'

FIREBASE_API_KEY="your_firebase_api_key"
FIREBASE_AUTH_DOMAIN="your_project.firebaseapp.com"
FIREBASE_PROJECT_ID="your_project_id"
FIREBASE_STORAGE_BUCKET="your_project.appspot.com"
FIREBASE_MESSAGING_SENDER_ID="your_sender_id"
FIREBASE_APP_ID="your_app_id"
```

---

## ☁️ Deployment (Vercel)

1. Add a `vercel.json` file
2. Push code to GitHub
3. Import project into Vercel
4. Configure environment variables
5. Deploy

---

## 🧪 Testing Recommendations

* Test visitor entry with repeat mobile numbers
* Validate checkout edge cases
* Verify report accuracy with date filters
* Test webcam capture permissions on different browsers

---

## 📌 Future Enhancements

* Admin approval for visitor bookings
* Real-time notification alerts
* Biometric or RFID integration
* Multi-campus support
* Audit logs for admin actions

---

## 👥 Credits

**Designed and Developed by:**
**Keethapriyan MR** and **Alan S**
*(HIVE – Innovation & Development Team)*

---

## 📄 License

This project is developed for **institutional use at SRIT**.
Commercial redistribution is not permitted without authorization.

---

## ❤️ Acknowledgement

Special thanks to the SRIT administration and security team for their feedback and operational insights during development.

---