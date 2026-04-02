from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
# import database # In-Memory DB (for local testing)
import database_dynamo as database # AWS DynamoDB Adapter (PROD)
from functools import wraps
import ml_engine
from sns_service import sns_client # Import AWS SNS Service

import boto3

# AWS Configuration (UPDATED for consistency)
REGION = 'us-east-1' # N. Virginia

dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)

# DynamoDB Tables (FIXED: Consistent naming)
patient_users_table = dynamodb.Table("PatientUser")
admin_users_table = dynamodb.Table('AdminUser')  # FIXED: Was 'AdminUsers'
doctor_table = dynamodb.Table('DoctorUser')
medtrack_data_table = dynamodb.Table('Medtrack_data')

# SNS Topic ARN (UPDATED to match region)
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:050690756868:Medtrack_cloud_enabled_healthcare_management'

app = Flask(__name__)
app.secret_key = 'supersecuritykey_medtrack_dev' # Use env var in production
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'medtrack', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Authentication Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                flash('Access denied. Generalized role restriction.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Context Processor ---
@app.context_processor
def inject_user():
    return dict(current_user=session.get('user_name'), current_role=session.get('user_role'))

# --- Routes ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = database.get_user(email)
        
        if user and user['password'] == password:
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            session['user_id'] = user['id']
            
            if user['role'] == 'patient':
                return redirect(url_for('patient_dashboard'))
            elif user['role'] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Admin Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Admin-specific hardcoded auth for demo
        if email == 'admin@example.com' and password == 'password123':
            session['user_id'] = 'admin'
            session['user_role'] = 'admin'
            session['user_name'] = 'System Administrator'
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Access Denied: Invalid Administrative Credentials', 'error')
            
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    patients = database.get_all_patients()
    doctors = database.get_all_doctors()
    blood_stock = database.get_blood_stock()
    capacity = database.get_hospital_capacity()
    dept_load = database.get_department_load()
    pending_donations = database.get_pending_donations()
    
    # Advanced Stats for Dashboard UI
    stats = {
        'doctors': len(doctors),
        'patients': len(patients),
        'appointments': len(database.appointments),
        'records': sum(len(v) for v in database.records.values()),
        'invoices': len(database.invoices),
        'departments': len(set(d['department'] for d in doctors)) if doctors else 0,
        'income': sum(inv['amount'] for inv in database.invoices.values() if inv['status'] == 'Paid'),
        'pending_income': sum(inv['amount'] for inv in database.invoices.values() if inv['status'] == 'Unpaid')
    }

    return render_template('admin/dashboard.html', 
                         patients=patients, 
                         blood_stock=blood_stock, 
                         capacity=capacity, 
                         dept_load=dept_load,
                         pending_donations=pending_donations,
                         stats=stats)

# --- New Admin Management Routes ---

@app.route('/admin/manage/doctors')
@login_required
@role_required('admin')
def admin_doctors():
    doctors = database.get_all_doctors()
    return render_template('admin/doctors_list.html', doctors=doctors)

@app.route('/admin/manage/patients')
@login_required
@role_required('admin')
def admin_patients():
    patients = database.get_all_patients()
    return render_template('admin/patients_list.html', patients=patients)

@app.route('/admin/manage/appointments')
@login_required
@role_required('admin')
def admin_appointments():
    # Convert dict to list
    all_appts = list(database.appointments.values())
    return render_template('admin/appointments_list.html', appointments=all_appts)

@app.route('/admin/manage/records')
@login_required
@role_required('admin')
def admin_records():
    # Flatten records: database.records is {patient_id: [record, record]}
    all_records = []
    for pid, record_list in database.records.items():
        for r in record_list:
            r['patient_id'] = pid # Ensure ID is available
            all_records.append(r)
    return render_template('admin/records_list.html', records=all_records)

@app.route('/admin/manage/invoices')
@login_required
@role_required('admin')
def admin_invoices():
    # Convert dict to list
    all_inv = list(database.invoices.values())
    return render_template('admin/invoices_list.html', invoices=all_inv)

@app.route('/admin/capacity/update', methods=['POST'])
@login_required
@role_required('admin')
def update_capacity():
    ward = request.form.get('ward')
    occupied = request.form.get('occupied')
    status = request.form.get('status')
    
    if database.update_hospital_capacity(ward, occupied, status):
        flash(f'{ward} capacity updated successfully.', 'success')
    else:
        flash('Failed to update capacity.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify_donation/<don_id>')
@login_required
@role_required('admin')
def verify_blood_donation(don_id):
    if database.verify_donation(don_id):
        flash('Donation verified and stock updated.', 'success')
    else:
        flash('Verification failed or invalid ID.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/patient/donate', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_donate():
    if request.method == 'POST':
        group = request.form['group']
        # Assume user name is in session
        donor = session.get('user_name', 'Anonymous')
        database.add_donation(donor, group)
        flash('Donation request submitted. Thank you for saving lives!', 'success')
        return redirect(url_for('patient_dashboard'))
    return render_template('patient/donate.html')

@app.route('/doctor/vault/<patient_id>')
@login_required
@role_required('doctor')
def doctor_view_vault(patient_id):
    records = database.get_patient_records(patient_id)
    return render_template('doctor/vault_view.html', records=records, patient_id=patient_id)

@app.route('/doctor/ai_assist/<patient_id>')
@login_required
@role_required('doctor')
def doctor_ai_assist(patient_id):
    # Simulated AI logic
    import random
    opinions = [
        "AI Analysis: Patient history suggests high risk of Vitamin D deficiency. Recommend screening.",
        "AI Analysis: Symptoms align with seasonal allergies. Prescribe antihistamines and monitor.",
        "AI Analysis: No critical anomalies detected in recent logs. Proceed with standard checkup."
    ]
    return {'summary': random.choice(opinions)}

@app.route('/doctor/multimodal', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def multimodal_predict():
    result = None
    
    if request.method == 'POST':
        pred_type = request.form.get('type')
        
        if pred_type == 'image':
            if 'file' in request.files:
                f = request.files['file']
                if f.filename != '':
                    result = ml_engine.predictor.predict_image(filename=f.filename)
                    
        elif pred_type == 'signal':
            if 'file' in request.files:
                f = request.files['file']
                # In real app, read file content. Here we simulate length
                content = "simulated_signal_data" * 10
                result = ml_engine.predictor.predict_signal(signal_data_text=content)
                
        elif pred_type == 'genomics':
            sequence = request.form.get('sequence', '')
            result = ml_engine.predictor.predict_genomics(sequence_data=sequence)

        elif pred_type == 'fracture':
            if 'file' in request.files:
                f = request.files['file']
                if f.filename != '':
                     result = ml_engine.predictor.predict_fracture(filename=f.filename)
            
    return render_template('doctor/multimodal.html', result=result)

@app.route('/admin/blood_bank')
@login_required
@role_required('admin')
def blood_bank_view():
    stock = database.get_blood_stock()
    return render_template('blood_bank.html', stock=stock)

@app.route('/admin/blood/update/<group>/<action>')
@login_required
@role_required('admin')
def update_blood_stock(group, action):
    stock = database.get_blood_stock()
    if group in stock:
        if action == 'add':
            stock[group]['units'] += 1
        elif action == 'remove' and stock[group]['units'] > 0:
            stock[group]['units'] -= 1
        
        # Update status
        units = stock[group]['units']
        if units < 5:
            stock[group]['status'] = 'Critical'
        elif units < 10:
            stock[group]['status'] = 'Low'
        else:
            stock[group]['status'] = 'Available'
            
    return redirect(url_for('blood_bank_view'))

# --- Patient Routes ---

@app.route('/patient/dashboard')
@login_required
@role_required('patient')
def patient_dashboard():
    appointments = database.get_appointments_by_patient(session['user_id'])
    return render_template('patient/dashboard.html', appointments=appointments)

@app.route('/patient/book', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def book_appointment():
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        time = request.form['time']
        state = request.form.get('state')
        center = request.form.get('center')
        
        appointment_id = database.create_appointment(session['user_id'], doctor_id, time, center, state)
        
        # --- Trigger AWS SNS Notification ---
        msg = f"New Appointment Booked!\nPatient: {session.get('user_name')}\nDoctor ID: {doctor_id}\nTime: {time}"
        sns_client.send_notification(message=msg, subject="MedTrack Appointment Alert")
        # ------------------------------------

        flash('Appointment booked successfully! Invoice generated.', 'success')
        return redirect(url_for('patient_dashboard'))
        
    doctors = database.get_all_doctors()
    locations = database.get_locations()
    return render_template('patient/book.html', doctors=doctors, locations=locations)

@app.route('/patient/invoices')
@login_required
@role_required('patient')
def patient_invoices():
    invoices = database.get_patient_invoices(session['user_id'])
    return render_template('patient/invoices.html', invoices=invoices)

@app.route('/patient/claim/<inv_id>')
@login_required
@role_required('patient')
def claim_insurance(inv_id):
    if database.update_invoice_status(inv_id, "Claimed"):
        flash('Insurance claim submitted successfully.', 'success')
    else:
        flash('Invoice not found.', 'error')
    return redirect(url_for('patient_invoices'))

def mock_ai_diagnosis(filename):
    """
    Simulated AI analysis.
    In a real app, this would call an inference API/model.
    """
    import random
    
    insights = [
        {"status": "Attention Needed", "summary": f"Simulated AI analysis of {filename}: Detected markers consistent with elevated blood pressure. Recommend monitoring sodium intake and scheduling a follow-up."},
        {"status": "Normal", "summary": f"Simulated AI analysis of {filename}: All vital signs and indicators appear within normal ranges. No immediate action required."},
        {"status": "Review Recommended", "summary": f"Simulated AI analysis of {filename}: Slight irregularities found in hemogram. A physician review is recommended to rule out anemia."}
    ]
    
    return random.choice(insights)

@app.route('/patient/vault', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_vault():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
            
        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            category = request.form.get('category', 'Report')
            
            # Save record with category
            database.add_record(session['user_id'], filename, "Uploaded to Vault", category)
            flash(f'File uploaded successfully.', 'success')
            return redirect(url_for('patient_vault'))
            
    records = database.get_patient_records(session['user_id'])
    return render_template('patient/vault.html', records=records)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/patient/diagnosis', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_diagnosis():
    result = None
    
    if request.method == 'POST':
        symptoms = request.form.get('symptoms', '')
        file = request.files.get('file')
        
        filename = "No Image"
        if file and file.filename != '':
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        # Run Multimodal Prediction
        result = ml_engine.predictor.predict(symptoms, filename)
        
        # Save to records so it appears in history
        database.add_record(session['user_id'], filename, result['summary'])
        
    return render_template('patient/predict.html', result=result)

@app.route('/patient/assistant')
@login_required
@role_required('patient')
def patient_assistant():
    return render_template('patient/assistant.html')

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    data = request.json
    msg = data.get('message', '').lower()
    
    # Simple Rule-Based AI Logic
    if 'headache' in msg or 'pain' in msg:
        reply = "I understand you're in pain. For headaches, try to rest in a quiet, dark room and stay hydrated. If the pain is severe, please book an appointment."
    elif 'fever' in msg or 'hot' in msg:
        reply = "A fever can be a sign of infection. Monitor your temperature. If it exceeds 102°F (39°C), consult a doctor immediately."
    elif 'appointment' in msg or 'book' in msg:
        reply = "You can book an appointment by clicking 'Book Now' in the sidebar or menu."
    elif 'thank' in msg:
        reply = "You're welcome! I'm here to help."
    else:
        reply = "I'm still learning! Could you describe your symptoms in more detail? Or you can upload a report in the 'Report Analysis' tab."
        
    return {'reply': reply}

@app.route('/patient/analyze', methods=['POST'])
@login_required
@role_required('patient')
def analyze_report():
    result = None
    if 'file' in request.files:
        file = request.files['file']
        symptoms = request.form.get('symptoms', '')
        
        if file and file.filename != '':
            filename = file.filename
            # Enhance: Save file logic here if needed
            
            # Use ML Engine
            result = ml_engine.predictor.predict(symptoms, filename)
            
            # Save record
            database.add_record(session['user_id'], filename, result['summary'])
            
    return render_template('patient/assistant.html', analysis_result=result)

@app.route('/api/mood/log', methods=['POST'])
@login_required
def log_mood():
    data = request.json
    score = data.get('score')
    note = data.get('note', '')
    
    if score:
        database.log_mood(session['user_id'], score, note)
        return {'status': 'success'}
    return {'status': 'error'}, 400

@app.route('/api/mood/history')
@login_required
def get_mood_history():
    history = database.get_mood_history(session['user_id'])
    # Return last 7 entries for chart
    return {'history': history[-7:]}

# --- Doctor Routes ---

@app.route('/doctor/dashboard')
@login_required
@role_required('doctor')
def doctor_dashboard():
    # 1. Basic Data
    appointments = database.get_appointments_by_doctor(session['user_id'])
    weekly_stats = database.get_weekly_stats(session['user_id'])
    blood_stock = database.get_blood_stock()
    alerts = [data for data in blood_stock.values() if data['status'] in ['Low', 'Critical']]

    # 2. Key Metrics for New UI
    total_patients_count = len(database.get_all_patients()) # Mock metric
    
    # Filter for Today
    today_str = database.get_formatted_date_time().split(' ')[0]
    today_appointments = [a for a in appointments if a.get('time', '').startswith(today_str)]
    
    today_count = len(today_appointments)
    today_patient_count = len(set(a['patient_id'] for a in today_appointments))
    
    # 3. Next Patient Details
    # Find the earliest upcoming appointment that isn't completed
    upcoming = [a for a in appointments if a['status'] in ['BOOKED', 'CHECKED-IN']]
    # Sort by time (string sort works for ISO-like, but our mock might vary. Assuming logic holds)
    upcoming.sort(key=lambda x: x.get('time', ''))
    
    next_patient = upcoming[0] if upcoming else None
    next_patient_details = None
    if next_patient:
        # Fetch full patient object
        next_patient_details = database.users.get(next_patient['patient_id'])
        # Merge appointment specific info
        if next_patient_details:
             next_patient_details['appt_reason'] = next_patient.get('reason', 'General Checkup')
             next_patient_details['appt_time'] = next_patient.get('time', '')

    return render_template('doctor/dashboard.html', 
                           appointments=appointments, 
                           today_appointments=today_appointments, # For specific list
                           weekly_stats=weekly_stats, 
                           alerts=alerts,
                           stats={
                               "total_patients": total_patients_count,
                               "today_patients": today_patient_count,
                               "today_appts": today_count
                           },
                           next_patient=next_patient_details)

@app.route('/doctor/my_appointments')
@login_required
@role_required('doctor')
def doctor_appointments_list():
    appointments = database.get_appointments_by_doctor(session['user_id'])
    return render_template('doctor/appointments_list.html', appointments=appointments)

@app.route('/doctor/my_patients')
@login_required
@role_required('doctor')
def doctor_patients_list():
    # In a real app, join appointments to find unique patients for this doctor
    # For now, we will show all patients but highlight those with history
    # Or better, just show customers who have booked this doctor?
    # Let's show all generic patients for this demo "directory" style or filter
    # To be safe and show functionality, let's filter patients who have at least one appointment with this doctor
    
    my_appts = database.get_appointments_by_doctor(session['user_id'])
    patient_ids = set(a['patient_id'] for a in my_appts)
    
    all_patients = database.get_all_patients()
    # Filter text matches or ID matches
    my_patients = [p for p in all_patients if p['id'] in patient_ids or p['name'] in patient_ids] 
    
    # If no patients found (fresh demo), show all for visibility? No, keep it realistic.
    # Actually, the Mock DB usually has IDs like 'Patient A'.
    
    return render_template('doctor/patients_list.html', patients=my_patients)

@app.route('/doctor/advance/<appt_id>')
@login_required
@role_required('doctor')
def advance_status(appt_id):
    # Logic to cycle status: BOOKED -> CHECKED-IN -> CONSULTING -> COMPLETED
    # Ideally find current status and move to next
    # For now, let's just implement a simple rigid flow or pass next status/action
    # But to keep it simple, let's iterate or pass a query param?
    # Let's check current status
    # This part requires reading the appointment.
    # Since database functions don't supporting getting single appointment easily without looping or ID lookup (I implemented ID lookup but returned dict?)
    # Wait, create_appointment returns dict. I didn't verify if I have get_appointment.
    # Ah, I missed get_appointment_by_id in database.py. I'll rely on appointments global in database being accessible or add a quick helper here or use the globals directly if imported, but cleaner to update database.py.
    # Actually, appointments is a dict in database.py, and I didn't expose a 'get_by_id'.
    # I will modify database.py to add `get_appointment(id)` or just access `database.appointments[id]` if I know it exists.
    
    if appt_id in database.appointments:
        current_status = database.appointments[appt_id]['status']
        next_status = current_status
        if current_status == 'BOOKED':
            next_status = 'CHECKED-IN'
        elif current_status == 'CHECKED-IN':
            next_status = 'CONSULTING'
        elif current_status == 'CONSULTING':
            next_status = 'COMPLETED'
        
        database.update_appointment_status(appt_id, next_status)
        flash(f'Appointment status updated to {next_status}', 'success')
    
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/review/<appt_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def review_appointment(appt_id):
    if appt_id not in database.appointments:
        flash('Appointment not found', 'error')
        return redirect(url_for('doctor_dashboard'))
        
    appointment = database.appointments[appt_id]
    
    if request.method == 'POST':
        review_text = request.form['review']
        appointment['review'] = review_text
        flash('Review saved successfully.', 'success')
        return redirect(url_for('doctor_dashboard'))
        
    return render_template('doctor/review.html', appointment=appointment)

@app.route('/patient/chat')
@login_required
@role_required('patient')
def patient_chat():
    departments = sorted(list(set(d['department'] for d in database.get_all_doctors())))
    return render_template('patient/chat.html', departments=departments)

@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_chat_message():
    data = request.json
    message = data.get('message')
    dept = data.get('dept')
    
    if not message or not dept:
        return {'status': 'error', 'message': 'Missing fields'}, 400
        
    sender_name = session.get('user_name', 'Anonymous')
    role = session.get('user_role', 'patient')
    
    new_msg = database.add_chat_message(sender_name, dept, message, role)
    return {'status': 'success', 'message': new_msg}

@app.route('/api/chat/get')
@login_required
def get_chat_messages():
    dept = request.args.get('dept')
    messages = database.get_chat_messages(dept)
    return {'status': 'success', 'messages': messages}

# --- Doctor Chat Routes ---

@app.route('/doctor/chat')
@login_required
@role_required('doctor')
def doctor_chat_view():
    # In a real app, filtering would be based on the doctor's actual department
    # For this mock, we'll let them see all or pass a department if we tracked it in session
    # Let's assume for now they want to see "Cardiology" by default or all active threads
    
    # We will pass unique departments so they can filter if they want
    departments = sorted(list(set(d['department'] for d in database.get_all_doctors())))
    return render_template('doctor/chat.html', departments=departments)

@app.route('/api/doctor/reply', methods=['POST'])
@login_required
@role_required('doctor')
def doctor_reply():
    data = request.json
    chat_id = data.get('chat_id')
    reply_text = data.get('reply')
    
    if database.request_doctor_reply(chat_id, reply_text):
        return {'status': 'success'}
    return {'status': 'error', 'message': 'Chat ID not found'}, 404

if __name__ == '__main__':
    # Use database.get_ist_time() to print start time in IST
    try:
        start_time = database.get_formatted_date_time()
        print(f"Server started at {start_time} (IST)")
    except Exception:
        pass

    # Match Reference Project (SecureBank) Startup Style
    # This allows direct execution via 'python3 app.py' on AWS
    app.run(host="0.0.0.0", port=5000, debug=True)
