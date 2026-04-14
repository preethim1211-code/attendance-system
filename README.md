# Attendance System - Face Recognition

A full-stack attendance management system using facial recognition.

## Tech Stack
- **Backend:** Python Flask
- **Database:** SQLite
- **Face Recognition:** face_recognition (dlib-based)
- **Frontend:** HTML, CSS, JavaScript

## Setup Instructions

### 1. Install Python (3.9+)
Download from https://www.python.org/downloads/

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** `face_recognition` requires `dlib` which needs CMake.
> - **Windows:** Install Visual Studio Build Tools + CMake
> - **Mac:** `brew install cmake`
> - **Linux:** `sudo apt install cmake build-essential`

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
Go to **http://127.0.0.1:5000**

## Usage
1. **Register** employees with name, email, and a face photo (webcam)
2. **Mark Attendance** — employees look at the camera; the system identifies them and logs check-in/check-out
3. **View Records** — browse attendance by date with stats

## Project Structure
```
attendance-system/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── attendance.db           # SQLite database (auto-created)
├── known_faces/            # Stored employee photos
├── static/css/style.css    # Styles
├── templates/
│   ├── index.html          # Home page
│   ├── register.html       # Employee registration
│   ├── mark.html           # Mark attendance via face recognition
│   └── attendance.html     # View attendance records
└── README.md
```
