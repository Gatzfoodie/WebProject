# QueueCare – Barangay Health Center Appointment & Queue System

Flask + SQLite web system. Patients book time slots and get a queue number; staff manage the daily queue and record consultation notes.

## Run in Visual Studio Code
1. Unzip the folder and open it in VS Code (File > Open Folder).
2. Open a terminal (Terminal > New Terminal) and run:

        python -m venv venv
        venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
        pip install -r requirements.txt
        python app.py

3. Open http://127.0.0.1:5000 in your browser.

## Demo accounts
- Staff: staff@queuecare.com / staff123
- Patient: click Register to create one.

## Folder structure
    QueueCare/
    ├── app.py              # routes, database, logic
    ├── requirements.txt
    ├── templates/          # base, index, register, login, book, my, staff (.html)
    └── static/style.css

## Presentation notes
- Problem: long waiting lines and paper records at the health center.
- Users: residents/patients and health center staff.
- Features: registration/login, slot booking (no double booking), auto queue number, cancel, patient history with doctor's notes, staff dashboard with date filter, search, status updates.
- IMPORTANT: your professor requires a unique title per group. Rename "QueueCare" (in templates/base.html, index.html, README) and add your own feature.
