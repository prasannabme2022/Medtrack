import boto3
import os
import datetime
import pytz
from botocore.exceptions import ClientError

# --- Configuration ---
REGION = os.environ.get('AWS_REGION', 'ap-south-1') # Default to Mumbai

try:
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    # The 8 Tables matching aws_setup.py
    # We map the legacy simple names to the actual PROD tables
    admin_table = dynamodb.Table('medtrack_admin') # Not in aws_setup, maybe use logic for admin?
    doctor_table = dynamodb.Table('medtrack_doctors')
    patient_table = dynamodb.Table('medtrack_patients')
    data_table = dynamodb.Table('medtrack_data') # This seems to be the catch-all for app.py logic
    # Note: app.py uses a single 'Medtrack_data' for records/appts in the adapter logic
    # But aws_setup.py creates 'medtrack_appointments', 'medtrack_medical_vault' etc separately.
    # This is a schema mismatch. app.py's `database_dynamo` adapter writes to ONE table, 
    # while `aws_setup.py` creates MANY tables.
    
    # DECISION: We must stick to `app.py`'s logic since that's the running code.
    # We will rename the table variables to match what `database_dynamo.py` expects, 
    # but pointing to the names likely created or intended.
    # If the user ran aws_setup.py, they have multi-table. 
    # If they run app.py with this adapter, they expect single-table (mostly).
    
    # Let's check `database_dynamo.py` logic again. 
    # It writes 'APPT#' to `data_table`. 
    # `aws_setup.py` writes to `appointments_table`.
    
    # CRITICAL FIX: The current `database_dynamo.py` is a Single-Table Design (STD) adapter.
    # `aws_setup.py` is a Multi-Table Design (MTD) script.
    # We cannot easily reconcile them without rewriting one.
    # Since `app.py` is the application logic, we should probably ensure the 'Medtrack_data' table exists.
    # I will stick to 'Medtrack_data' for the ST logic, but update the user/doctor tables to match if possible.
    
    # Let's just update the region and keep table names consistent with the ADAPTER's expectation for now,
    # but warn the user they might need to create 'Medtrack_data' if aws_setup didn't.
    
    admin_table = dynamodb.Table('AdminUser')
    doctor_table = dynamodb.Table('DoctorUser')
    patient_table = dynamodb.Table('PatientUser')
    data_table = dynamodb.Table('Medtrack_data')
    
    # Check if they exist (simple check)
    admin_table.load()
    print("✅ Connected to AWS DynamoDB")
    IS_CONNECTED = True
except Exception as e:
    print(f"⚠️ AWS DynamoDB Not Connected: {e}")
    print("   (Falling back to In-Memory mode is NOT supported in this adapter. Ensure keys are set.)")
    IS_CONNECTED = False

# --- Helper Functions ---

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

def get_formatted_date_time():
    return get_ist_time().strftime("%d-%m-%Y %I:%M %p")

# --- User Management (Tables 1-3) ---

def get_user(email):
    # Search all 3 tables since we don't know the role initially
    # 1. Try Patient
    try:
        resp = patient_table.get_item(Key={'username': email})
        if 'Item' in resp:
            u = resp['Item']
            u['role'] = 'patient'
            return u
    except: pass

    # 2. Try Doctor
    try:
        resp = doctor_table.get_item(Key={'username': email})
        if 'Item' in resp:
            u = resp['Item']
            u['role'] = 'doctor'
            return u
    except: pass

    # 3. Try Admin
    try:
        resp = admin_table.get_item(Key={'username': email})
        if 'Item' in resp:
            u = resp['Item']
            u['role'] = 'admin'
            return u
    except: pass
    
    return None

def get_all_patients():
    try:
        resp = patient_table.scan()
        return resp.get('Items', [])
    except: return []

def get_all_doctors():
    try:
        resp = doctor_table.scan()
        return resp.get('Items', [])
    except: return []

# --- Data Management (Table 4: MedTrack_Data) ---
# Schema: PK=EntityID, SK=Meta/Type

def create_appointment(patient_id, doctor_id, time, center=None, state=None, age=None, gender=None, reason=None):
    # ID Generation
    import uuid
    uid = str(uuid.uuid4())[:8]
    appt_id = f"appt_{uid}"
    inv_id = f"inv_{uid}"
    
    # Invoice Data
    invoice_item = {
        'PK': f"INV#{inv_id}",
        'SK': 'META',
        'id': inv_id,
        'patient_id': patient_id,
        'amount': 150,
        'status': 'Unpaid',
        'date': time.split("T")[0]
    }
    
    # Appointment Data
    # Fetch doctor name first
    doc = get_doctor(doctor_id)
    doc_name = doc['name'] if doc else "Unknown"
    
    appt_item = {
        'PK': f"APPT#{appt_id}",
        'SK': 'META',
        'id': appt_id,
        'patient_id': patient_id,
        'doctor_id': doctor_id,
        'doctor_name': doc_name,
        'time': time,
        'location': f"{center}, {state}" if center else "Clinic",
        'status': "BOOKED",
        'invoice_id': inv_id,
        'age': age,
        'gender': gender,
        'reason': reason
    }
    
    # Batch Write
    try:
        with data_table.batch_writer() as batch:
            batch.put_item(Item=invoice_item)
            batch.put_item(Item=appt_item)
        return appt_item
    except Exception as e:
        print(f"Error creating appointment: {e}")
        return None

def get_appointments_by_patient(patient_id):
    # Scan is inefficient but fine for this scale. 
    # Better: GSI on patient_id, but staying within single table limits.
    try:
        resp = data_table.scan()
        items = resp.get('Items', [])
        return [i for i in items if i['PK'].startswith('APPT#') and i.get('patient_id') == patient_id]
    except: return []

def get_appointments_by_doctor(doctor_id):
    try:
        resp = data_table.scan()
        items = resp.get('Items', [])
        return [i for i in items if i['PK'].startswith('APPT#') and i.get('doctor_id') == doctor_id]
    except: return []

def get_patient_invoices(patient_id):
    try:
        resp = data_table.scan()
        items = resp.get('Items', [])
        return [i for i in items if i['PK'].startswith('INV#') and i.get('patient_id') == patient_id]
    except: return []

def update_invoice_status(inv_id, status):
    try:
        data_table.update_item(
            Key={'PK': f"INV#{inv_id}", 'SK': 'META'},
            UpdateExpression="set #s = :s",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': status}
        )
        return True
    except: return False

def add_record(patient_id, filename, ai_summary, category='Report'):
    import uuid
    rec_id = f"rec_{str(uuid.uuid4())[:8]}"
    
    item = {
        'PK': f"REC#{rec_id}",
        'SK': 'META',
        'id': rec_id,
        'patient_id': patient_id,
        'filename': filename,
        'ai_summary': ai_summary,
        'category': category,
        'date': get_formatted_date_time()
    }
    data_table.put_item(Item=item)
    return item

def get_patient_records(patient_id):
    try:
        resp = data_table.scan()
        items = resp.get('Items', [])
        return [i for i in items if i['PK'].startswith('REC#') and i.get('patient_id') == patient_id]
    except: return []

# --- Legacy Getters (Mocked or Simplified) ---
def get_doctor(doctor_id):
    # Assuming doctor_id is username/email or PK
    # In Dynamo, existing User Tables use 'username' as PK.
    try:
        resp = doctor_table.get_item(Key={'username': doctor_id})
        return resp.get('Item')
    except: return None

def get_blood_stock():
    # Mock for display - storing in DynamoDB needs pre-seeding
    return {
        "A+": {"group": "A+", "units": 12, "status": "Available"},
        "O+": {"group": "O+", "units": 5, "status": "Low"}
    }

def get_hospital_capacity():
    return {
        "ICU": {"name": "ICU", "total": 20, "occupied": 15, "status": "High Load"}
    }

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

def get_locations():
    return {
        "Sydney": {"CBD": ["Central Health"], "North": ["Northern Beaches Hospital"]}
    }
