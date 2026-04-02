
# Mock Database for Medtrack
# Using Python dictionaries for data persistence (in-memory)
import datetime
import pytz

# --- Timezone Helper (IST) ---
def get_ist_time():
    """Returns current time in Indian Standard Time (IST)."""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

def get_formatted_date_time():
    """Returns formatted date string DD-MM-YYYY HH:MM AM/PM"""
    return get_ist_time().strftime("%d-%m-%Y %I:%M %p")

# Users Data: Key = Email
users = {
    "patient@example.com": {
        "id": "p1",
        "name": "John Doe",
        "email": "patient@example.com",
        "password": "password123", # In production, hash this!
        "role": "patient"
    },
    "doctor@example.com": {
        "id": "d1",
        "name": "Dr. Smith",
        "email": "doctor@example.com",
        "password": "password123",
        "role": "doctor"
    },
    "admin@example.com": {
        "id": "a1",
        "name": "Admin User",
        "email": "admin@example.com",
        "password": "password123",
        "role": "admin"
    }
}

# Doctors Database: Key = Doctor ID
# Categorized by Department
doctors_db = {
    "d1": {"id": "d1", "name": "Dr. Rajesh Koothrappali", "department": "Cardiology", "availability": "Mon-Fri, 9am-5pm"},
    "d2": {"id": "d2", "name": "Dr. Priya Sethi", "department": "Dermatology", "availability": "Mon-Sat, 10am-2pm"},
    "d3": {"id": "d3", "name": "Dr. Sanjay Gupta", "department": "General Medicine", "availability": "Tue-Sun, 8am-4pm"},
    "d4": {"id": "d4", "name": "Dr. Anjali Menon", "department": "Pediatrics", "availability": "Mon-Fri, 10am-6pm"},
    "d5": {"id": "d5", "name": "Dr. Sameer Khan", "department": "Orthopedics", "availability": "Wed-Sun, 9am-5pm"}
}

# Hospitals Database: comprehensive Indian Data
hospitals_db = {
    "Karnataka": {
        "Bangalore": ["Narayana Health City", "Manipal Hospital", "Apollo Hospital", "Sakra World Hospital", "Fortis Hospital"],
        "Mysore": ["Apollo BGS Hospitals", "Manipal Hospital", "Columbia Asia"],
        "Hubli": ["KIMS", "SDM Medical College"]
    },
    "Maharashtra": {
        "Mumbai": ["Lilavati Hospital", "Breach Candy", "Nanavati Super Speciality", "Tata Memorial Hospital", "Kokilaben Dhirubhai Ambani Hospital"],
        "Pune": ["Ruby Hall Clinic", "Jehangir Hospital", "Sancheti Hospital"],
        "Nagpur": ["Orange City Hospital", "Care Hospital"]
    },
    "Delhi NCR": {
        "New Delhi": ["AIIMS", "Sir Ganga Ram Hospital", "Max Super Speciality", "Indraprastha Apollo"],
        "Gurgaon": ["Medanta - The Medicity", "Artemis Hospital", "Fortis Memorial Research Institute"],
        "Noida": ["Jaypee Hospital", "Kailash Hospital"]
    },
    "Tamil Nadu": {
        "Chennai": ["Apollo Main Hospital", "Fortis Malar", "MIOT International", "Dr. Rela Institute"],
        "Vellore": ["CMC Vellore"],
        "Coimbatore": ["Kovai Medical Center", "Ganga Hospital"]
    },
    "Telangana": {
        "Hyderabad": ["Apollo Health City", "Yashoda Hospitals", "KIMS", "AIG Hospitals"],
        "Secunderabad": ["KIMS", "Sunshine Hospitals"]
    },
    "West Bengal": {
        "Kolkata": ["Apollo Gleneagles", "AMRI Hospitals", "Woodlands Multispeciality", "Medica Superspecialty"]
    },
    "Kerala": {
        "Kochi": ["Amrita Institute of Medical Sciences", "Aster Medcity", "Lisie Hospital"],
        "Trivandrum": ["KIMSHEALTH", "Sree Chitra Tirunal Institute"]
    },
    "Gujarat": {
        "Ahmedabad": ["Apollo Hospitals", "Zydus Hospital", "Sterling Hospital"],
        "Surat": ["Sunshine Global Hospital", "Mahavir Hospital"]
    }
}

# Blood Bank Database
blood_bank_db = {
    "A+": {"group": "A+", "units": 15, "status": "Available"},
    "A-": {"group": "A-", "units": 4, "status": "Low"},
    "B+": {"group": "B+", "units": 22, "status": "Available"},
    "B-": {"group": "B-", "units": 6, "status": "Critical"},
    "O+": {"group": "O+", "units": 30, "status": "Available"},
    "O-": {"group": "O-", "units": 2, "status": "Critical"},
    "AB+": {"group": "AB+", "units": 10, "status": "Available"},
    "AB-": {"group": "AB-", "units": 3, "status": "Low"}
}

# Hospital Capacity Mock
hospital_capacity = {
    "ICU": {"name": "ICU", "total": 20, "occupied": 16, "status": "High Load"},
    "General Ward": {"name": "General Ward", "total": 100, "occupied": 45, "status": "Normal"},
    "Emergency": {"name": "Emergency", "total": 15, "occupied": 5, "status": "Normal"},
    "Operation Theatre": {"name": "Operation Theatre", "total": 8, "occupied": 7, "status": "Critical"}
}

# Appointments & Records
appointments = {}
records = {} # Key = Patient ID
mood_logs = {} # Key = Patient ID
invoices = {} # Key = Invoice ID
chats = [] # List of messaging objects
blood_donations = [] 
blood_requests = []

# --- Accessor Functions for Locations ---
def get_locations():
    return hospitals_db

# --- User Functions ---
def get_user(email):
    return users.get(email)

def get_doctor(doctor_id):
    return doctors_db.get(doctor_id)

def get_all_doctors():
    return list(doctors_db.values())

def get_all_patients():
    return [user for user in users.values() if user['role'] == 'patient']

# --- Blood Bank Functions ---
def get_blood_stock():
    return blood_bank_db

def add_donation(donor_name, group):
    donation = {
        "id": f"don_{len(blood_donations) + 1}",
        "donor": donor_name,
        "group": group,
        "status": "Pending",
        "date": get_formatted_date_time()
    }
    blood_donations.append(donation)
    return donation

def verify_donation(donation_id):
    for don in blood_donations:
        if don['id'] == donation_id and don['status'] == 'Pending':
            don['status'] = 'Verified'
            if don['group'] in blood_bank_db:
                blood_bank_db[don['group']]['units'] += 1
            return True
    return False

def get_pending_donations():
    return [d for d in blood_donations if d['status'] == 'Pending']

# --- Hospital Capacity Functions ---
def get_hospital_capacity():
    return hospital_capacity

def update_hospital_capacity(ward_name, occupied, status):
    if ward_name in hospital_capacity:
        hospital_capacity[ward_name]['occupied'] = int(occupied)
        hospital_capacity[ward_name]['status'] = status
        return True
    return False

def get_department_load():
    load = {}
    for appt in appointments.values():
        if appt['status'] in ['BOOKED', 'CHECKED-IN', 'CONSULTING']:
            dept = appt.get('doctor_dept', 'General')
            load[dept] = load.get(dept, 0) + 1
    return load

# --- Appointment Functions ---
def create_appointment(patient_id, doctor_id, time, center=None, state=None, age=None, gender=None, reason=None):
    appt_id = f"appt_{len(appointments) + 1}"
    
    # Auto-generate an invoice 
    invoice_amount = 500  # ₹500 standard consultation fee
    inv_id = f"inv_{len(invoices) + 1}"
    
    # Simple date handling
    date_str = time.replace("T", " ") if time else get_formatted_date_time()

    invoices[inv_id] = {
        "id": inv_id,
        "appt_id": appt_id,
        "patient_id": patient_id,
        "amount": invoice_amount,
        "status": "Unpaid", 
        "date": date_str.split(" ")[0], 
        "details": f"Consultation Fee - {center if center else 'General'}"
    }

    appointments[appt_id] = {
        "id": appt_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "doctor_name": doctors_db[doctor_id]["name"] if doctor_id in doctors_db else "Unknown",
        "doctor_dept": doctors_db[doctor_id]["department"] if doctor_id in doctors_db else "General",
        "time": date_str,
        "location": f"{center}, {state}" if center else "Main Clinic",
        "status": "BOOKED", 
        "review": None,
        "invoice_id": inv_id,
        "age": age,
        "gender": gender,
        "reason": reason
    }
    return appointments[appt_id]

def get_appointments_by_patient(patient_id):
    return [appt for appt in appointments.values() if appt["patient_id"] == patient_id]

def get_appointments_by_doctor(doctor_id):
    return [appt for appt in appointments.values() if appt["doctor_id"] == doctor_id]

def update_appointment_status(appt_id, new_status):
    if appt_id in appointments:
        appointments[appt_id]["status"] = new_status
        return True
    return False

# --- Invoice Functions ---
def get_patient_invoices(patient_id):
    return [inv for inv in invoices.values() if inv["patient_id"] == patient_id]

def update_invoice_status(inv_id, status):
    if inv_id in invoices:
        invoices[inv_id]["status"] = status
        return True
    return False

# --- Medical Record Functions ---
def add_record(patient_id, filename, ai_summary, category='Report'):
    if patient_id not in records:
        records[patient_id] = []
    
    record_id = f"rec_{len(records.get(patient_id, [])) + 1}"
    new_record = {
        "id": record_id,
        "filename": filename,
        "ai_summary": ai_summary,
        "category": category,
        "date": get_formatted_date_time()
    }
    if patient_id not in records: records[patient_id] = []
    records[patient_id].append(new_record)
    return new_record

def get_patient_records(patient_id):
    return records.get(patient_id, [])

# --- Chat Functions ---
def add_chat_message(sender_name, department, message, sender_role='patient'):
    chat_id = len(chats) + 1
    new_msg = {
        'id': chat_id,
        'sender': sender_name,
        'role': sender_role,
        'dept': department,
        'message': message,
        'time': get_formatted_date_time(),
        'reply': None
    }
    chats.append(new_msg)
    return new_msg

def get_chat_messages(department=None):
    if department:
        return [msg for msg in chats if msg['dept'] == department]
    return chats

def request_doctor_reply(chat_id, reply_text):
    for msg in chats:
        if msg['id'] == int(chat_id):
            msg['reply'] = reply_text
            return True
    return False

# --- Mood Logging ---
def log_mood(patient_id, score, note):
    if patient_id not in mood_logs:
        mood_logs[patient_id] = []
        
    entry = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.datetime.now().strftime("%H:%M"),
        "score": int(score),
        "note": note
    }
    mood_logs[patient_id].append(entry)
    return entry

def get_mood_history(patient_id):
    return mood_logs.get(patient_id, [])

# --- Stats Helper ---
def get_weekly_stats(doctor_id):
    return [
        {"day": "Mon", "count": 12},
        {"day": "Tue", "count": 19},
        {"day": "Wed", "count": 15},
        {"day": "Thu", "count": 22},
        {"day": "Fri", "count": 18},
        {"day": "Sat", "count": 8},
        {"day": "Sun", "count": 5}
    ]
