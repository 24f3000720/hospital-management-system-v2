# Local Hospital Management System v2

## 1. Project Details

### 1.1. Title
**Local Hospital Management System v2**

### 1.2. Problem Statement
Hospitals operations and appointments usually rely on manual paperwork, fragmented data, poor coordination between departments, and lack of transparency in the processes between patients' and doctors. These operations' effectiveness can be improved with a centralised system for data management such that all process are fast and direct. There is a need for a all-in-one system for data management and interaction between hospital, doctors and patients.

### 1.3. Approach
A web application is built that consolidates all data between hospitals, doctors and patients such that interactions and operations can be attended directly from one's end, ensuring data consistency and ease in processes. The robust, modular application is developed with a Python Flask REST API backend and a separate, modern Vue.js single-page application (SPA) front-end interface, ensuring a seamless and responsive user experience. The system also leverages Redis for caching to optimize API performance and handle background task queues.

### 1.4. Features
The application provides a comprehensive ecosystem where patients can register, manage their profiles with an optional photo feature, and search for doctors by specific departments to book appointments at available time slots. Doctors utilize a chronological dashboard to manage their schedules, mark visits as completed, and record detailed treatment data such as diagnoses and prescriptions directly into the patient history. For centralized oversight, the Admin role serves as the pre-existing superuser who manages all user profiles and core data while monitoring hospital performance via integrated charts and metrics.

Beyond standard interactions, the system implements an intelligent 7-day rolling schedule algorithm and robust role-based access control to ensure secure, automated operations. High-performance background tasks manage automated daily reminders for patients, generate comprehensive monthly activity reports for medical staff, and facilitate on-demand exports of treatment history. To ensure a professional user experience, the platform includes a simulated payment portal for billing and maintains data consistency through strict backend validations and caching mechanisms.

---

## 2. AI Usage
Part wise breakdown of AI usage and their purposes in the project:

| Part | Purpose | % | Notes |
|:--- |:--- |:--- |:--- |
| Flask App Layer | Backend and Routing | 25 | Generating boilerplate for RESTful API endpoints |
| SQLAlchemy + SQLite | Database and Schema | 20 | Mapping complex entity relationships and constraints |
| Backend | Logic checks | 35 | Logic checking and verification of connection between components |
| Frontend | UI UX and Vue.js | 15 | Converting wireframes into responsive frontend components |
| CRUD Logic | Data Management | 20 | Standardizing validation logic for hospital records |
| Debugging | Code polishing | 60 | Analyzing stack traces and refining edge case handling |
| Async Jobs (Celery) | Background Tasks | 25 | Structuring logic for daily reminders and CSV exports |

---

## 3. Technologies Used
* **A. Flask:** Core python library used for backend REST API development
* **B. Vue.js:** Core javascript framework for frontend SPA development
* **C. Celery & Redis:** Asynchronous task queue and message broker for handling background jobs and cache
* **D. SQLAlchemy:** Object relational mapper (ORM) that acts as a bridge between object-oriented programming and relational databases
* **E. Flask-Migrate:** Tracking changes and applying to the database during development
* **F. SQLite:** Relational Database

---


## 5. Entity Relationship Schema

### 5.1. Tables
1. **User:** uid (Primary Key), name, email, password, profile_image_data, f_rid (Role Foreign Key), Doctor Specific Fields (specialization, experience_years, f_did), blacklisted
2. **Appointment:** aid (Primary Key), f_patient_uid, f_doctor_uid, appointment_date, status, completed_at, Medical Data (diagnosis, prescription, doctor_notes)
3. **Role:** rid (Primary Key), role_name, description
4. **Department:** did (Primary Key), name
5. **DoctorAvailability:** id (Primary Key), doctor_uid, slot_str, available
6. **ExportJob:** id (Primary Key), patient_uid, export_type, status, celery_task_id, file_name, file_path, message, error_message, created_at, completed_at
7. **Payment:** id (Primary Key), patient_uid, appointment_id, amount, currency, card_holder, card_last4, payment_status, payment_reference, created_at, paid_at

### 5.2. Relationships
* Role &rarr; User [One-to-Many]
* Department &rarr; User (as Doctor) [One-to-Many]
* User (as Patient) &rarr; Appointment [One-to-Many]
* User (as Doctor) &rarr; Appointment [One-to-Many]
* User (as Doctor) &rarr; DoctorAvailability [One-to-Many]
* User (as Patient) &rarr; ExportJob [One-to-Many]
* User (as Patient) &rarr; Payment [One-to-Many]
* Appointment &rarr; Payment [One-to-One]

---

## Video Presentation

https://drive.google.com/file/d/1b6JqLnhit3nh6vnuZ-BXIFczCG1-DB_P/view?usp=share_link

---

## How to Run

### Step 1: Redis Server Setup
Redis is required for background task management and caching. Note: Install Redis prior to running this.
```bash
# Start the Redis development server (run in a dedicated terminal window)
redis-server
```

### Step 2: Backend Environment Setup
Initialize the database and install the required Python packages for the Flask application.
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # (On Windows use: venv\Scripts\activate)

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Run Celery Workers
The background jobs (reminders, reports, exports) run asynchronously using Celery.
```bash
# In the backend/ directory with your virtual environment activated:
# Run the celery worker processing tasks
celery -A celery_app.celery worker --loglevel=info

# In another terminal window (with venv activated):
# Run celery beat to manage scheduled reminders
celery -A celery_app.celery beat --loglevel=info
```

### Step 4: Run the Flask API Server
Start the core backend server that communicates with the SQLite database.
```bash
# In the backend/ directory with your virtual environment activated:
python app.py
```

### Step 5: Frontend Vue Setup and Run
Launch the Vue Single Page Application (SPA).
```bash
# In an entirely new terminal window:
cd frontend

# Install Node modules via npm
npm install

# Run the frontend development server
npm run dev
```
