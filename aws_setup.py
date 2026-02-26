from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
import boto3
from botocore.exceptions import ClientError
import json
from dotenv import load_dotenv
from decimal import Decimal
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'medtrack-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
PATIENTS_TABLE = 'medtrack_patients'
DOCTORS_TABLE = 'medtrack_doctors'
APPOINTMENTS_TABLE = 'medtrack_appointments'
MEDICAL_VAULT_TABLE = 'medtrack_medical_vault'
BLOOD_BANK_TABLE = 'medtrack_blood_bank'
INVOICES_TABLE = 'medtrack_invoices'
CHAT_MESSAGES_TABLE = 'medtrack_chat_messages'
MOOD_LOGS_TABLE = 'medtrack_mood_logs'
APPOINTMENT_REQUESTS_TABLE = 'medtrack_appointment_requests'
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:908027408356:Medtrack_cloud_enabled_healthcare_management')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
try:
    # Smart SNS Client Initialization
    # If ARN has a region (arn:aws:sns:REGION:...), use it.
    sns_region = AWS_REGION
    if 'arn:aws:sns:' in SNS_TOPIC_ARN:
        try:
            sns_region = SNS_TOPIC_ARN.split(':')[3]
        except:
            pass

    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    sns_client = boto3.client('sns', region_name=sns_region)
    
    # Table configurations
    TABLES_CONFIG = [
        {'name': PATIENTS_TABLE, 'key': 'email'},
        {'name': DOCTORS_TABLE, 'key': 'email'},
        {'name': APPOINTMENTS_TABLE, 'key': 'appointment_id'},
        {'name': MEDICAL_VAULT_TABLE, 'key': 'vault_id'},
        {'name': BLOOD_BANK_TABLE, 'key': 'blood_group'},
        {'name': INVOICES_TABLE, 'key': 'invoice_id'},
        {'name': CHAT_MESSAGES_TABLE, 'key': 'message_id'},
        {'name': MOOD_LOGS_TABLE, 'key': 'mood_id'},
        {'name': APPOINTMENT_REQUESTS_TABLE, 'key': 'request_id'}
    ]

    def create_tables():
        """Create DynamoDB tables if they don't exist"""
        existing_tables = [t.name for t in dynamodb.tables.all()]
        
        for table_config in TABLES_CONFIG:
            table_name = table_config['name']
            key_name = table_config['key']
            
            if table_name not in existing_tables:
                logger.info(f"Creating table: {table_name}")
                try:
                    dynamodb.create_table(
                        TableName=table_name,
                        KeySchema=[{'AttributeName': key_name, 'KeyType': 'HASH'}],
                        AttributeDefinitions=[{'AttributeName': key_name, 'AttributeType': 'S'}],
                        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    )
                    logger.info(f"Table {table_name} creation initiated.")
                except ClientError as e:
                    logger.error(f"Failed to create table {table_name}: {e}")
            else:
                logger.info(f"Table {table_name} already exists.")

    # Initialize all DynamoDB tables (lazy reference)
    patients_table = dynamodb.Table(PATIENTS_TABLE)
    doctors_table = dynamodb.Table(DOCTORS_TABLE)
    appointments_table = dynamodb.Table(APPOINTMENTS_TABLE)
    medical_vault_table = dynamodb.Table(MEDICAL_VAULT_TABLE)
    blood_bank_table = dynamodb.Table(BLOOD_BANK_TABLE)
    invoices_table = dynamodb.Table(INVOICES_TABLE)
    chat_messages_table = dynamodb.Table(CHAT_MESSAGES_TABLE)
    mood_logs_table = dynamodb.Table(MOOD_LOGS_TABLE)
    appointment_requests_table = dynamodb.Table(APPOINTMENT_REQUESTS_TABLE)
    
    logger.info("AWS services initialized successfully")
    AWS_AVAILABLE = True
    
except Exception as e:
    logger.warning(f"AWS services not available: {e}")
    logger.info("Falling back to local file-based storage for development")
    
    # Import local storage fallback
    from local_storage import LocalStorage
    
    # Initialize local storage tables
    patients_table = LocalStorage(PATIENTS_TABLE)
    doctors_table = LocalStorage(DOCTORS_TABLE)
    appointments_table = LocalStorage(APPOINTMENTS_TABLE)
    medical_vault_table = LocalStorage(MEDICAL_VAULT_TABLE)
    blood_bank_table = LocalStorage(BLOOD_BANK_TABLE)
    invoices_table = LocalStorage(INVOICES_TABLE)
    chat_messages_table = LocalStorage(CHAT_MESSAGES_TABLE)
    mood_logs_table = LocalStorage(MOOD_LOGS_TABLE)
    appointment_requests_table = LocalStorage(APPOINTMENT_REQUESTS_TABLE)
    
    AWS_AVAILABLE = False
    logger.info("Local storage initialized - data will persist in local_data/ folder")

# ============================================
# HELPER FUNCTIONS
# ============================================

def to_decimal(value):
    """Convert float to Decimal for DynamoDB storage"""
    if isinstance(value, float):
        return Decimal(str(value))
    return value

def serialize_datetime(obj):
    """Serialize datetime and Decimal objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

def deserialize_item(item):
    """Deserialize DynamoDB item to Python dict"""
    if not item:
        return None
    result = {}
    for key, value in item.items():
        if isinstance(value, str) and 'T' in value:
            try:
                result[key] = datetime.fromisoformat(value)
            except ValueError:
                result[key] = value
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result

def generate_id(prefix=""):
    """Generate unique ID with optional prefix"""
    return prefix + str(uuid.uuid4().hex)[:8]

def get_current_datetime():
    """Get current datetime as ISO string"""
    return datetime.now().isoformat()

# ============================================
# SNS NOTIFICATION SERVICE (Email & SMS)
# ============================================

def send_notification(message, subject="MedTrack Notification"):
    """Send SNS notification to topic subscribers"""
    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=subject
        )
        logger.info(f"SNS notification sent: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {e}")
        return False

def subscribe_email(email):
    """Subscribe email to SNS Topic"""
    try:
        response = sns_client.subscribe(
            TopicArn=SNS_TOPIC_ARN,
            Protocol='email',
            Endpoint=email
        )
        logger.info(f"Subscribed {email} to SNS Topic. Subscription ARN: {response.get('SubscriptionArn')}")
        return True
    except Exception as e:
        logger.error(f"Failed to subscribe {email}: {e}")
        return False

def send_email_notification(email, subject, message):
    """Send email notification via SNS"""
    try:
        # Ensure subscription first (Idempotent-ish)
        subscribe_email(email)
        
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=subject,
            MessageAttributes={
                'email': {
                    'DataType': 'String',
                    'StringValue': email
                }
            }
        )
        logger.info(f"Email notification sent to {email}: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {e}")
        return False

def send_sms_notification(phone_number, message):
    """Send SMS notification via SNS (max 160 characters)"""
    try:
        # Format phone number (must be in E.164 format: +919876543210)
        if not phone_number.startswith('+'):
            phone_number = '+91' + phone_number.lstrip('0')
        
        response = sns_client.publish(
            PhoneNumber=phone_number,
            Message=message[:160],  # SMS limit
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'  # For important messages
                }
            }
        )
        logger.info(f"SMS sent to {phone_number}: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {e}")
        return False

def notify_appointment_status_change(patient_email, status, appointment_id=None, doctor_name=None):
    """Send SNS notification when appointment status changes in patient tracking system"""
    try:
        # Status-specific messages
        status_messages = {
            'BOOKED': {
                'subject': 'Appointment Confirmed - MedTrack',
                'message': f'Your appointment has been successfully booked. Appointment ID: {appointment_id or "N/A"}. Please arrive 15 minutes early for check-in.'
            },
            'CHECKED-IN': {
                'subject': 'Checked In - MedTrack',
                'message': f'You have been checked in for your appointment. Please wait in the designated area. The doctor will see you shortly.'
            },
            'CONSULTING': {
                'subject': 'Consultation Started - MedTrack',
                'message': f'Your consultation with {doctor_name or "the doctor"} has started. Please proceed to the consultation room.'
            },
            'COMPLETED': {
                'subject': 'Appointment Completed - MedTrack',
                'message': f'Your consultation is complete. An invoice has been generated. Thank you for choosing MedTrack!'
            }
        }
        
        notification_data = status_messages.get(status)
        if notification_data:
            # Send notification via SNS Topic
            send_notification(
                message=notification_data['message'],
                subject=notification_data['subject']
            )
            
            # Also send email notification if available
            if patient_email:
                send_email_notification(
                    email=patient_email,
                    subject=notification_data['subject'],
                    message=notification_data['message']
                )
            
            logger.info(f"Status change notification sent for {patient_email}: {status}")
            return True
        else:
            logger.warning(f"Unknown status for notification: {status}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send status change notification: {e}")
        return False

def notify_appointment_created(patient_email, doctor_name, appointment_date, patient_phone=None):
    """Send appointment confirmation via email and SMS"""
    subject = "MedTrack - Appointment Confirmed"
    message = f"""
Dear Patient,

Your appointment has been successfully booked!

Doctor: {doctor_name}
Date & Time: {appointment_date}

Please arrive 10 minutes early for check-in.

Thank you for choosing MedTrack!
    """.strip()
    
    # Send email
    send_email_notification(patient_email, subject, message)
    
    # Send SMS if phone provided
    if patient_phone:
        sms_message = f"MedTrack: Appointment with Dr. {doctor_name} on {appointment_date}. Arrive 10 min early."
        send_sms_notification(patient_phone, sms_message)


# ============================================
# PATIENT MANAGEMENT
# ============================================

def get_patient(email):
    """Get patient by email from DynamoDB"""
    try:
        response = patients_table.get_item(Key={'email': email})
        return deserialize_item(response.get('Item'))
    except ClientError as e:
        logger.error(f"Error getting patient {email}: {e}")
        return None

def create_patient(email, password, name, phone, address, dob, blood_group):
    """Create patient in DynamoDB"""
    try:
        if not password or not isinstance(password, str) or len(password.strip()) == 0:
            logger.error("Invalid password provided")
            return False
        
        patient_data = {
            'email': email,
            'password': generate_password_hash(password.strip(), method='pbkdf2:sha256'),
            'name': name,
            'phone': phone or '',
            'address': address or '',
            'dob': dob or '',
            'blood_group': blood_group or '',
            'role': 'patient',
            'created_at': get_current_datetime(),
            'mood_history': []
        }
        
        patients_table.put_item(
            Item=patient_data,
            ConditionExpression='attribute_not_exists(email)'
        )
        
        # Subscribe patient to SNS notifications
        subscribe_email(email)
        
        # Send notification
        send_notification(
            f"New patient registered: {name} ({email})",
            "New Patient Registration"
        )
        
        logger.info(f"Patient created successfully: {email}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Patient already exists: {email}")
            return False
        logger.error(f"Error creating patient {email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating patient {email}: {e}")
        return False

def update_patient(email, updates):
    """Update patient information"""
    try:
        update_expr = "SET "
        expr_values = {}
        expr_names = {}
        
        for idx, (key, value) in enumerate(updates.items()):
            attr_name = f"#attr{idx}"
            attr_value = f":val{idx}"
            update_expr += f"{attr_name} = {attr_value}, "
            expr_names[attr_name] = key
            expr_values[attr_value] = value
        
        update_expr = update_expr.rstrip(', ')
        
        patients_table.update_item(
            Key={'email': email},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        logger.info(f"Patient updated: {email}")
        return True
    except ClientError as e:
        logger.error(f"Error updating patient {email}: {e}")
        return False

# ============================================
# DOCTOR MANAGEMENT
# ============================================

def get_doctor(email):
    """Get doctor by email from DynamoDB"""
    try:
        response = doctors_table.get_item(Key={'email': email})
        return deserialize_item(response.get('Item'))
    except ClientError as e:
        logger.error(f"Error getting doctor {email}: {e}")
        return None

def create_doctor(email, password, name, phone, specialization, license_number):
    """Create doctor in DynamoDB"""
    try:
        if not password or not isinstance(password, str) or len(password.strip()) == 0:
            logger.error("Invalid password provided")
            return False
        
        doctor_data = {
            'email': email,
            'password': generate_password_hash(password.strip(), method='pbkdf2:sha256'),
            'name': name,
            'phone': phone or '',
            'specialization': specialization or '',
            'license_number': license_number or '',
            'role': 'doctor',
            'status': 'available',
            'created_at': get_current_datetime()
        }
        
        doctors_table.put_item(
            Item=doctor_data,
            ConditionExpression='attribute_not_exists(email)'
        )
        
        # Send notification
        send_notification(
            f"New doctor registered: Dr. {name} ({specialization})",
            "New Doctor Registration"
        )
        
        logger.info(f"Doctor created successfully: {email}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Doctor already exists: {email}")
            return False
        logger.error(f"Error creating doctor {email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating doctor {email}: {e}")
        return False

def get_all_doctors():
    """Get all doctors from DynamoDB"""
    try:
        response = doctors_table.scan()
        doctors = [deserialize_item(item) for item in response.get('Items', [])]
        return doctors
    except ClientError as e:
        logger.error(f"Error getting all doctors: {e}")
        return []

# ============================================
# APPOINTMENT MANAGEMENT
# ============================================

def create_appointment(patient_email, doctor_email, appointment_date, symptoms, priority='normal'):
    """Create appointment in DynamoDB"""
    try:
        appointment_id = generate_id("APPT")
        
        appointment_data = {
            'appointment_id': appointment_id,
            'patient_email': patient_email,
            'doctor_email': doctor_email,
            'appointment_date': appointment_date,
            'symptoms': symptoms or '',
            'priority': priority,
            'status': 'BOOKED',
            'diagnosis': '',
            'prescription': '',
            'created_at': get_current_datetime(),
            'updated_at': get_current_datetime()
        }
        
        appointments_table.put_item(Item=appointment_data)
        
        # Get patient and doctor names safely
        patient = get_patient(patient_email)
        doctor = get_doctor(doctor_email)
        
        patient_name = patient.get('name', patient_email) if patient else patient_email
        doctor_name = doctor.get('name', doctor_email) if doctor else doctor_email
        
        # Send notification
        send_notification(
            f"New appointment booked by {patient_name} with Dr. {doctor_name} on {appointment_date}",
            "New Appointment Booked"
        )
        
        # Send patient tracking notification
        notify_appointment_status_change(
            patient_email=patient_email,
            status='BOOKED',
            appointment_id=appointment_id,
            doctor_name=doctor_name
        )
        
        logger.info(f"Appointment created: {appointment_id}")
        return appointment_id
    except ClientError as e:
        logger.error(f"Error creating appointment: {e}")
        return None

def get_appointment(appointment_id):
    """Get appointment by ID"""
    try:
        response = appointments_table.get_item(Key={'appointment_id': appointment_id})
        return deserialize_item(response.get('Item'))
    except ClientError as e:
        logger.error(f"Error getting appointment {appointment_id}: {e}")
        return None

def update_appointment_status(appointment_id, status, diagnosis='', prescription=''):
    """Update appointment status and details"""
    try:
        update_data = {
            'status': status,
            'updated_at': get_current_datetime()
        }
        
        if diagnosis:
            update_data['diagnosis'] = diagnosis
        if prescription:
            update_data['prescription'] = prescription
        
        update_expr = "SET "
        expr_values = {}
        expr_names = {}
        
        for key, value in update_data.items():
            # Use alias for reserved keywords (status is reserved in DynamoDB)
            alias = f"#{key}"
            update_expr += f"{alias} = :{key}, "
            expr_names[alias] = key
            expr_values[f":{key}"] = value
            
        update_expr = update_expr.rstrip(', ')
        
        appointments_table.update_item(
            Key={'appointment_id': appointment_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names
        )
        
        # Send notification
        appointment = get_appointment(appointment_id)
        send_notification(
            f"Appointment {appointment_id} status updated to: {status}",
            "Appointment Status Update"
        )
        
        logger.info(f"Appointment updated: {appointment_id}")
        return True
    except ClientError as e:
        logger.error(f"Error updating appointment {appointment_id}: {e}")
        return False

def get_patient_appointments(patient_email):
    """Get all appointments for a patient"""
    try:
        response = appointments_table.scan(
            FilterExpression='patient_email = :email',
            ExpressionAttributeValues={':email': patient_email}
        )
        appointments = [deserialize_item(item) for item in response.get('Items', [])]
        
        # Enrich appointments with details for display
        for appt in appointments:
            # Map time
            # Map time
            date_val = appt.get('appointment_date')
            appt['time'] = str(date_val).replace('T', ' ') if date_val else 'N/A'
            
            # Get Doctor Name
            if 'doctor_email' in appt:
                doc = get_doctor(appt['doctor_email'])
                appt['doctor_name'] = doc.get('name', appt['doctor_email']) if doc else appt['doctor_email']
            else:
                 appt['doctor_name'] = 'Unknown Doctor'
                 
        return sorted(appointments, key=lambda x: x.get('created_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting patient appointments: {e}")
        return []

def get_doctor_appointments(doctor_email):
    """Get all appointments for a specific doctor"""
    try:
        # DEMO OVERRIDE: Allow 'medtrack@gmail.com' to see ALL appointments (Super View)
        if doctor_email == 'medtrack@gmail.com':
            response = appointments_table.scan()
        else:
            # Filter appointments by doctor email for privacy
            response = appointments_table.scan(
                FilterExpression='doctor_email = :email',
                ExpressionAttributeValues={':email': doctor_email}
            )
        
        appointments = [deserialize_item(item) for item in response.get('Items', [])]
        
        # Enrich with patient details
        for appt in appointments:
            # Map time
            date_val = appt.get('appointment_date')
            appt['time'] = str(date_val).replace('T', ' ') if date_val else 'N/A'
            
            # Get Patient Details
            p_email = appt.get('patient_email')
            if p_email:
                patient = get_patient(p_email)
                appt['patient_name'] = patient.get('name', p_email) if patient else p_email
                appt['patient_id'] = p_email # Template uses this
            else:
                 appt['patient_name'] = 'Unknown'
                 appt['patient_id'] = 'N/A'

        return sorted(appointments, key=lambda x: x.get('created_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting doctor appointments: {e}")
        return []

# ... (active_queue update usually in doctor_dashboard route but function is here)

# Let me modify the doctor_dashboard route separately or if it's close enough.
# It seems get_doctor_appointments is around line 560. doctor_dashboard is around 1280.
# I will apply this change to get_doctor_appointments first.

# ============================================
# APPOINTMENT REQUEST MANAGEMENT (Doctor → Patient)
# ============================================

def create_appointment_request(doctor_email, patient_email, proposed_date, reason=''):
    """Doctor creates an appointment request for a patient"""
    try:
        request_id = generate_id("REQ")
        
        request_data = {
            'request_id': request_id,
            'doctor_email': doctor_email,
            'patient_email': patient_email,
            'proposed_date': proposed_date,
            'reason': reason or '',
            'status': 'PENDING',  # PENDING, ACCEPTED, DECLINED
            'created_at': get_current_datetime(),
            'updated_at': get_current_datetime()
        }
        
        appointment_requests_table.put_item(Item=request_data)
        
        # Get doctor and patient names
        doctor = get_doctor(doctor_email)
        patient = get_patient(patient_email)
        
        doctor_name = doctor.get('name', doctor_email) if doctor else doctor_email
        patient_name = patient.get('name', patient_email) if patient else patient_email
        
        # Send notification to patient
        send_email_notification(
            email=patient_email,
            subject="New Appointment Request - MedTrack",
            message=f"""
Dear {patient_name},

Dr. {doctor_name} has sent you an appointment request.

Proposed Date: {proposed_date}
Reason: {reason or 'Consultation'}

Please log in to your MedTrack dashboard to accept or decline this request.

Thank you,
MedTrack Team
            """.strip()
        )
        
        logger.info(f"Appointment request created: {request_id}")
        return request_id
    except ClientError as e:
        logger.error(f"Error creating appointment request: {e}")
        return None

def get_appointment_request(request_id):
    """Get appointment request by ID"""
    try:
        response = appointment_requests_table.get_item(Key={'request_id': request_id})
        return deserialize_item(response.get('Item'))
    except ClientError as e:
        logger.error(f"Error getting appointment request {request_id}: {e}")
        return None

def get_patient_appointment_requests(patient_email, status=None):
    """Get all appointment requests for a patient, optionally filtered by status"""
    try:
        if status:
            response = appointment_requests_table.scan(
                FilterExpression='patient_email = :email AND #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':email': patient_email,
                    ':status': status
                }
            )
        else:
            response = appointment_requests_table.scan(
                FilterExpression='patient_email = :email',
                ExpressionAttributeValues={':email': patient_email}
            )
        
        requests = [deserialize_item(item) for item in response.get('Items', [])]
        
        # Enrich with doctor details
        for req in requests:
            if 'doctor_email' in req:
                doc = get_doctor(req['doctor_email'])
                req['doctor_name'] = doc.get('name', req['doctor_email']) if doc else req['doctor_email']
                req['doctor_specialization'] = doc.get('specialization', 'General') if doc else 'General'
        
        return sorted(requests, key=lambda x: x.get('created_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting patient appointment requests: {e}")
        return []

def get_doctor_appointment_requests(doctor_email, status=None):
    """Get all appointment requests sent by a doctor, optionally filtered by status"""
    try:
        if status:
            response = appointment_requests_table.scan(
                FilterExpression='doctor_email = :email AND #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':email': doctor_email,
                    ':status': status
                }
            )
        else:
            response = appointment_requests_table.scan(
                FilterExpression='doctor_email = :email',
                ExpressionAttributeValues={':email': doctor_email}
            )
        
        requests = [deserialize_item(item) for item in response.get('Items', [])]
        
        # Enrich with patient details
        for req in requests:
            if 'patient_email' in req:
                patient = get_patient(req['patient_email'])
                req['patient_name'] = patient.get('name', req['patient_email']) if patient else req['patient_email']
        
        return sorted(requests, key=lambda x: x.get('created_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting doctor appointment requests: {e}")
        return []

def accept_appointment_request(request_id):
    """Patient accepts an appointment request and creates an appointment"""
    try:
        # Get the request
        request = get_appointment_request(request_id)
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        # Rigorous Status Check
        if request.get('status') != 'PENDING':
            logger.warning(f"Request {request_id} is not pending (Status: {request.get('status')})")
            return False
        
        # Create the actual appointment
        # We append a note to symptoms to indicate this was a doctor-initiated request
        original_reason = request.get('reason', '')
        symptoms = f"{original_reason} (Doctor Request Accepted)"
        
        appointment_id = create_appointment(
            patient_email=request['patient_email'],
            doctor_email=request['doctor_email'],
            appointment_date=request['proposed_date'],
            symptoms=symptoms
        )
        
        if appointment_id:
            # Update request status ONLY if appointment creation succeeded
            appointment_requests_table.update_item(
                Key={'request_id': request_id},
                UpdateExpression="SET #status = :status, updated_at = :updated, appointment_id = :aid",
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'ACCEPTED',
                    ':updated': get_current_datetime(),
                    ':aid': appointment_id
                }
            )
            
            # Get names for notification
            doctor = get_doctor(request['doctor_email'])
            patient = get_patient(request['patient_email'])
            
            doctor_name = doctor.get('name', request['doctor_email']) if doctor else request['doctor_email']
            patient_name = patient.get('name', request['patient_email']) if patient else request['patient_email']
            
            # Notify doctor
            send_email_notification(
                email=request['doctor_email'],
                subject="Appointment Request Accepted - MedTrack",
                message=f"""
Dear Dr. {doctor_name},

{patient_name} has accepted your appointment request.

Appointment ID: {appointment_id}
Date: {request['proposed_date']}
Reason: {original_reason}

The appointment is now confirmed and visible in your dashboard.

Thank you,
MedTrack Team
                """.strip()
            )
            
            logger.info(f"Appointment request {request_id} accepted, appointment {appointment_id} created")
            return True
        else:
            logger.error(f"Failed to create appointment for request {request_id}")
            return False
            
    except ClientError as e:
        logger.error(f"Error accepting appointment request {request_id}: {e}")
        return False

def decline_appointment_request(request_id, reason=''):
    """Patient declines an appointment request"""
    try:
        # Get the request
        request = get_appointment_request(request_id)
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        if request['status'] != 'PENDING':
            logger.warning(f"Request {request_id} is not pending")
            return False
        
        # Update request status
        update_expr = "SET #status = :status, updated_at = :updated"
        expr_values = {
            ':status': 'DECLINED',
            ':updated': get_current_datetime()
        }
        
        if reason:
            update_expr += ", decline_reason = :reason"
            expr_values[':reason'] = reason
        
        appointment_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues=expr_values
        )
        
        # Get names for notification
        doctor = get_doctor(request['doctor_email'])
        patient = get_patient(request['patient_email'])
        
        doctor_name = doctor.get('name', request['doctor_email']) if doctor else request['doctor_email']
        patient_name = patient.get('name', request['patient_email']) if patient else request['patient_email']
        
        # Notify doctor
        send_email_notification(
            email=request['doctor_email'],
            subject="Appointment Request Declined - MedTrack",
            message=f"""
Dear Dr. {doctor_name},

{patient_name} has declined your appointment request for {request['proposed_date']}.

{f'Reason: {reason}' if reason else ''}

You may send a new request or contact the patient directly.

Thank you,
MedTrack Team
            """.strip()
        )
        
        logger.info(f"Appointment request {request_id} declined")
        return True
        
    except ClientError as e:
        logger.error(f"Error declining appointment request {request_id}: {e}")
        return False


# ============================================
# MEDICAL VAULT (FILE STORAGE)
# ============================================

def add_to_medical_vault(patient_email, file_name, file_type, file_path, analysis=''):
    """Add medical file to vault"""
    try:
        vault_id = generate_id("VAULT")
        
        vault_data = {
            'vault_id': vault_id,
            'patient_email': patient_email,
            'file_name': file_name,
            'file_type': file_type,
            'file_path': file_path,
            'analysis': analysis or '',
            'uploaded_at': get_current_datetime()
        }
        
        medical_vault_table.put_item(Item=vault_data)
        
        logger.info(f"Medical file added to vault: {vault_id} for patient {patient_email}")
        return vault_id
    except ClientError as e:
        logger.error(f"Error adding to medical vault: {e}")
        return None

def get_patient_vault(patient_email):
    """Get all medical files for a patient"""
    try:
        response = medical_vault_table.scan(
            FilterExpression='patient_email = :email',
            ExpressionAttributeValues={':email': patient_email}
        )
        vault_items = [deserialize_item(item) for item in response.get('Items', [])]
        return sorted(vault_items, key=lambda x: x.get('uploaded_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting patient vault: {e}")
        return []

# ============================================
# BLOOD BANK MANAGEMENT
# ============================================

def get_blood_stock():
    """Get current blood stock for all blood groups"""
    try:
        response = blood_bank_table.scan()
        blood_stock = {}
        for item in response.get('Items', []):
            blood_group = item.get('blood_group')
            units = int(item.get('units', 0))
            blood_stock[blood_group] = units
        
        # Ensure all blood groups exist
        all_groups = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']
        for group in all_groups:
            if group not in blood_stock:
                blood_stock[group] = 0
        
        return blood_stock
    except ClientError as e:
        logger.error(f"Error getting blood stock: {e}")
        return {}

def update_blood_stock(blood_group, units):
    """Update blood stock for a blood group"""
    try:
        blood_bank_table.put_item(
            Item={
                'blood_group': blood_group,
                'units': int(units),
                'updated_at': get_current_datetime()
            }
        )
        
        logger.info(f"Blood stock updated: {blood_group} = {units} units")
        return True
    except ClientError as e:
        logger.error(f"Error updating blood stock: {e}")
        return False

# ============================================
# INVOICE & INSURANCE MANAGEMENT
# ============================================

def create_invoice(patient_email, appointment_id, amount, description):
    """Create invoice for patient"""
    try:
        invoice_id = generate_id("INV")
        
        invoice_data = {
            'invoice_id': invoice_id,
            'patient_email': patient_email,
            'appointment_id': appointment_id,
            'amount': to_decimal(amount),
            'description': description,
            'status': 'unpaid',
            'insurance_claimed': False,
            'created_at': get_current_datetime()
        }
        
        invoices_table.put_item(Item=invoice_data)
        
        # Send notification
        send_notification(
            f"New invoice generated for patient {patient_email}: ₹{amount}",
            "New Invoice"
        )
        
        logger.info(f"Invoice created: {invoice_id}")
        return invoice_id
    except ClientError as e:
        logger.error(f"Error creating invoice: {e}")
        return None

def get_patient_invoices(patient_email):
    """Get all invoices for a patient"""
    try:
        response = invoices_table.scan(
            FilterExpression='patient_email = :email',
            ExpressionAttributeValues={':email': patient_email}
        )
        invoices = [deserialize_item(item) for item in response.get('Items', [])]
        return sorted(invoices, key=lambda x: x.get('created_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting patient invoices: {e}")
        return []

def claim_insurance(invoice_id):
    """Claim insurance for an invoice"""
    try:
        invoices_table.update_item(
            Key={'invoice_id': invoice_id},
            UpdateExpression="SET insurance_claimed = :claimed, updated_at = :updated",
            ExpressionAttributeValues={
                ':claimed': True,
                ':updated': get_current_datetime()
            }
        )
        
        # Send notification
        send_notification(
            f"Insurance claim submitted for invoice {invoice_id}",
            "Insurance Claim"
        )
        
        logger.info(f"Insurance claimed for invoice: {invoice_id}")
        return True
    except ClientError as e:
        logger.error(f"Error claiming insurance: {e}")
        return False

# ============================================
# CHAT & MESSAGING
# ============================================

def send_chat_message(sender_email, receiver_email, message, sender_type='patient'):
    """Send chat message between patient and doctor"""
    try:
        message_id = generate_id("MSG")
        
        message_data = {
            'message_id': message_id,
            'sender_email': sender_email,
            'receiver_email': receiver_email,
            'message': message,
            'sender_type': sender_type,
            'read': False,
            'created_at': get_current_datetime()
        }
        
        chat_messages_table.put_item(Item=message_data)
        
        logger.info(f"Chat message sent: {message_id}")
        return message_id
    except ClientError as e:
        logger.error(f"Error sending chat message: {e}")
        return None

def get_chat_messages(user1_email, user2_email):
    """Get all chat messages between two users"""
    try:
        response = chat_messages_table.scan()
        all_messages = [deserialize_item(item) for item in response.get('Items', [])]
        
        # Filter messages between the two users
        chat_messages = [
            msg for msg in all_messages
            if (msg.get('sender_email') == user1_email and msg.get('receiver_email') == user2_email) or
               (msg.get('sender_email') == user2_email and msg.get('receiver_email') == user1_email)
        ]
        
        return sorted(chat_messages, key=lambda x: x.get('created_at', ''))
    except ClientError as e:
        logger.error(f"Error getting chat messages: {e}")
        return []

# ============================================
# MOOD TRACKING
# ============================================

def log_mood(patient_email, mood, notes=''):
    """Log mood for a patient"""
    try:
        mood_id = generate_id("MOOD")
        
        mood_data = {
            'mood_id': mood_id,
            'patient_email': patient_email,
            'mood': mood,
            'notes': notes,
            'logged_at': get_current_datetime()
        }
        
        mood_logs_table.put_item(Item=mood_data)
        
        logger.info(f"Mood logged: {mood_id} for patient {patient_email}")
        return mood_id
    except ClientError as e:
        logger.error(f"Error logging mood: {e}")
        return None

def get_mood_history(patient_email):
    """Get mood history for a patient"""
    try:
        response = mood_logs_table.scan(
            FilterExpression='patient_email = :email',
            ExpressionAttributeValues={':email': patient_email}
        )
        mood_logs = [deserialize_item(item) for item in response.get('Items', [])]
        return sorted(mood_logs, key=lambda x: x.get('logged_at', ''), reverse=True)
    except ClientError as e:
        logger.error(f"Error getting mood history: {e}")
        return []

# ============================================
# AI CHATBOT HELPERS
# ============================================

def get_chatbot_response(patient_email, message):
    """
    AI Chatbot response generator using AWS Bedrock (Claude) with Enhanced Fallback
    """
    # Try to get patient name for personalization
    patient_name = "there"
    try:
        if patient_email:
            p = get_patient(patient_email)
            if p and 'name' in p:
                patient_name = p['name'].split()[0] # First name
    except:
        pass

    # 1. Try Bedrock AI
    try:
        import json
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        prompt_data = f"\n\nHuman: You are Dr. AI, a helpful medical assistant for MedTrack. The user is {patient_name}. Answer friendly, concisely, and professionally.\nUser Question: {message}\n\nAssistant:"
        
        body = json.dumps({
            "prompt": prompt_data,
            "max_tokens_to_sample": 300,
            "temperature": 0.5,
            "top_p": 0.9,
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId='anthropic.claude-v2',
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body.get('completion', '').strip()
        
    except Exception as e:
        logger.warning(f"Bedrock AI unavailable ({e}), falling back to enhanced rules.")

    # 2. Enhanced Rule-based Fallback
    msg = message.lower()
    
    # Greetings & Small Talk
    if any(x in msg for x in ['hello', 'hi', 'hey', 'greetings', 'morning', 'evening']):
        return f"Hello {patient_name}! I'm your MedTrack Health Assistant. How are you feeling today?"
        
    elif any(x in msg for x in ['thank', 'thanks', 'cool', 'good', 'great']):
        return "You're very welcome! I'm here 24/7 if you need anything else to stay healthy."

    # App Navigation / Features
    elif any(x in msg for x in ['appointment', 'book', 'schedule', 'doctor', 'consult']):
        return "To book a consultation, click the **'Book Now'** button in the sidebar. We have specialists in Cardiology, Neurology, and General Medicine available today."
        
    elif any(x in msg for x in ['report', 'result', 'lab', 'test', 'upload', 'vault']):
        return "You can manage all your documents in the **Medical Vault**. It's secure and accessible by your doctor during consultations."
        
    elif any(x in msg for x in ['invoice', 'bill', 'payment', 'insurance', 'cost']):
        return "You can view and pay your bills in the **Invoices** section. Insurance claims can also be submitted directly from there."

    # Symptom Analysis (Simulated Medical Intelligence)
    elif any(x in msg for x in ['headache', 'migraine', 'dizzy']):
        return "Headaches can be caused by dehydration, stress, or lack of sleep. \n\n**Recommendation:**\n1. Drink a glass of water.\n2. Rest in a dark, quiet room.\n3. Monitor your BP in the dashboard.\n\nif it persists for >24 hours, please book an appointment."
        
    elif any(x in msg for x in ['fever', 'cold', 'flu', 'cough', 'sneeze', 'throat']):
        return f"It sounds like a viral infection, {patient_name}. \n\n**Advice:**\n- Stay hydrated and rest.\n- Monitor your temperature.\n- Gargle with warm salt water for throat pain.\n\nIf fever exceeds 101°F, please consult our General Practitioner immediately."
        
    elif any(x in msg for x in ['stomach', 'pain', 'vomit', 'nausea', 'diarrhea', 'digestion']):
        return "Abdominal issues are often dietary. Avoid spicy or heavy foods today. Probiotics or curd rice might help soothe your stomach. If pain is severe (especially on the right side), seek immediate help."
        
    elif any(x in msg for x in ['chest', 'heart', 'breath', 'tightness']):
        return "⚠️ **Important:** Chest pain or shortness of breath can be serious. \n\nIf you feel pressure, sweating, or pain radiating to your arm, please use the **SOS / Emergency** button immediately or call an ambulance. Do not ignore these symptoms."
        
    elif any(x in msg for x in ['skin', 'rash', 'itch', 'allergy']):
        return "For skin irritations, try to keep the area clean and dry. Avoid scratching. If you have a known allergy, take your prescribed antihistamine. You can upload a photo of the rash in the **Medical Vault** for a doctor to review."

    # General Health
    elif any(x in msg for x in ['diet', 'food', 'eat', 'nutrition']):
        return "A balanced diet is key! Focus on whole grains, proteins, and plenty of vegetables. Reduce sugar and processed foods. Would you like to consult a nutritionist?"
        
    elif 'stress' in msg or 'anxious' in msg or 'anxiety' in msg:
        return "I hear you. Stress affects physical health too. Try deep breathing exercises (4-7-8 technique). MedTrack also offers tele-consults with mental health experts if you'd like to talk to someone."
        
    elif 'prescription' in msg or 'medicine' in msg or 'pill' in msg:
        return "Always follow your doctor's prescription. You can view your active prescriptions in the **Medical Vault**. Never self-medicate antibiotics."

    # Emergency
    elif 'emergency' in msg or 'sos' in msg or 'help' in msg or 'urgent' in msg:
        return "🚨 **EMERGENCY PROTOCOL:** Please click the red **SOS Button** on the left sidebar immediately. This will alert nearby hospitals and your emergency contacts."
        
    else:
        return f"I understand, {patient_name}. While I'm an AI, I want to help. Could you describe your symptoms in more detail? (e.g., 'I have a headache' or 'My stomach hurts')"


# ============================================
# FLASK CONTEXT PROCESSOR
# ============================================

@app.context_processor
def inject_user_info():
    """Inject user information into all templates"""
    return {
        'current_user': session.get('user_id', 'Guest'),
        'current_role': session.get('role', None)
    }

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form
            
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()
            name = data.get('name', '').strip()
            phone = data.get('phone', '').strip()
            role = data.get('role', '').strip()
            
            # Validate inputs
            if not all([email, password, name, role]):
                flash('All fields are required.', 'error')
                return render_template('signup.html')
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
                return render_template('signup.html')
            
            # Check if user already exists
            if get_patient(email) or get_doctor(email):
                flash('Email already exists. Please choose a different one.', 'error')
                return render_template('signup.html')
            
            # Create user based on role
            success = False
            if role == 'patient':
                dob = data.get('dob', '')
                blood_group = data.get('blood_group', '')
                address = data.get('address', '').strip()
                success = create_patient(email, password, name, phone, address, dob, blood_group)
            elif role == 'doctor':
                specialization = data.get('specialization', '').strip()
                license_number = data.get('license_number', '').strip()
                success = create_doctor(email, password, name, phone, specialization, license_number)
            
            if success:
                flash('Account created successfully! Please sign in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Failed to create account. Please try again.', 'error')
                
        except Exception as e:
            logger.error(f"Signup error: {e}")
            flash('An error occurred during signup. Please try again.', 'error')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form
            
            email = data.get('email', '').strip().lower()
            password = data.get('password', '').strip()
            
            if not email or not password:
                flash('Please enter both email and password.', 'error')
                return render_template('login.html')
            
            # Check explicit admin credentials (hardcoded for demo)
            if email == 'admin@medtrack.com' and password == 'admin123':
                session['user_id'] = 'admin'
                session['role'] = 'admin'
                session['user_name'] = 'Administrator'
                flash('Welcome, Administrator!', 'success')
                return redirect(url_for('admin_dashboard'))

            # Check in patients table
            patient = get_patient(email)
            print(f"DEBUG: Retrieved patient for {email}: {patient}")
            if patient:
                print(f"DEBUG: Stored hash: {patient.get('password')}, Input password: {password}")
                is_valid = check_password_hash(patient['password'], password)
                print(f"DEBUG: Password match: {is_valid}")
                if is_valid:
                    session['user_id'] = email
                    session['role'] = 'patient'
                    session['user_name'] = patient['name']
                    
                    flash(f"Welcome back, {patient['name']}!", 'success')
                    return redirect(url_for('patient_dashboard'))
            
            # Check in doctors table
            doctor = get_doctor(email)
            print(f"DEBUG: Retrieved doctor for {email}: {doctor}")
            if doctor:
                print(f"DEBUG: Stored hash: {doctor.get('password')}, Input password: {password}")
                is_valid = check_password_hash(doctor['password'], password)
                print(f"DEBUG: Password match: {is_valid}")
                if is_valid:
                    session['user_id'] = email
                    session['role'] = 'doctor'
                    session['user_name'] = doctor['name']
                    
                    flash(f"Welcome back, Dr. {doctor['name']}!", 'success')
                    return redirect(url_for('doctor_dashboard'))
            
            flash('Invalid email or password.', 'error')
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/login')
def admin_login():
    flash("Please log in with Administrator credentials.", "info")
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin first.', 'error')
        return redirect(url_for('login'))
    
    # Simple stats for the dashboard
    stats = {
        'doctors': len(get_all_doctors()),
        'patients': 0, # get_all_patients not implemented cheaply, skip for now or implement
        'appointments': 0,
        'departments': 4
    }
    
    # We can try to scan if we want accurate numbers, but for speed just render template
    # Re-using the existing admin dashboard template but passing necessary variables
    # The existing template expects 'stats', 'patients', 'blood_stock' etc.
    
    return render_template('admin/dashboard.html', 
                         stats=stats,
                         patients=[],
                         blood_stock=get_blood_stock(),
                         capacity={'ICU': {'status': 'Normal', 'occupied': 8, 'total': 12}, 
                                   'General Ward': {'status': 'Normal', 'occupied': 45, 'total': 60}},
                         dept_load={'Cardiology': 20},
                         pending_donations=[])

@app.route('/admin/doctors')
def admin_doctors():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    doctors = get_all_doctors()
    return render_template('admin/doctors_list.html', doctors=doctors)

@app.route('/admin/patients')
def admin_patients():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin/patients_list.html', patients=[])

@app.route('/admin/appointments')
def admin_appointments():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin/appointments_list.html', appointments=[])

@app.route('/admin/records')
def admin_records():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin/records_list.html', item_counts={})

@app.route('/admin/invoices')
def admin_invoices():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin/invoices_list.html', invoices=[])

@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login as a patient first.', 'info')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # 1. Appointments (Sorted by date, earliest first)
    appointments = get_patient_appointments(user_id)
    appointments.sort(key=lambda x: x.get('appointment_date') or '', reverse=False)
    print(f"DEBUG: Appointments for {user_id}: {appointments}") 
    
    # Calculate upcoming appointment (First active appointment)
    active_statuses = ['BOOKED', 'CONFIRMED', 'CHECKED-IN', 'CONSULTING']
    upcoming_appointment = next((a for a in appointments if a.get('status') in active_statuses), None)
    
    # 2. Billing: Calculate unpaid balance
    invoices = get_patient_invoices(user_id)
    unpaid_balance = sum(float(inv['amount']) for inv in invoices if inv['status'] == 'unpaid' and not inv.get('insurance_claimed'))
    
    # 3. Vault Stats: Prescriptions & Results
    records = get_patient_vault(user_id)
    prescriptions_count = sum(1 for r in records if 'prescription' in r.get('description', '').lower() or 'rx' in r.get('description', '').lower())
    recent_results = [r for r in records if 'lab' in r.get('description', '').lower() or 'report' in r.get('description', '').lower()]
    new_results_count = len(recent_results)
    
    # 4. Fetch Vitals & Medical History from Patient Profile
    try:
        response = patients_table.get_item(Key={'email': user_id})
        patient_data = response.get('Item', {})
        vitals = patient_data.get('vitals', {'weight': '--', 'bp': '--/--', 'sugar': '--'})
        medical_history = patient_data.get('medical_history', [])
    except Exception as e:
        logger.error(f"Error fetching patient health data: {e}")
        vitals = {'weight': '-', 'bp': '-', 'sugar': '-'}
        medical_history = []
        
    # 5. Get Messages Count (Unread)
    try:
        # Assuming chat_messages_table exists and has 'receiver_id' and 'is_read'
        # For now, safe default or simple scan if schema matches
        messages_count = 0
        # msg_response = chat_messages_table.scan(
        #     FilterExpression='receiver_id = :uid AND is_read = :read',
        #     ExpressionAttributeValues={':uid': user_id, ':read': False}
        # )
        # messages_count = msg_response['Count']
    except Exception:
        messages_count = 0

    return render_template('patient/dashboard.html', 
                         appointments=appointments,
                         upcoming=upcoming_appointment, 
                         unpaid_balance=unpaid_balance,
                         prescriptions_count=prescriptions_count,
                         recent_results=recent_results[:3],
                         new_results_count=new_results_count,
                         vitals=vitals,
                         medical_history=medical_history,
                         messages_count=messages_count)

@app.route('/update_vitals', methods=['POST'])
def update_vitals():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    weight = request.form.get('weight')
    bp = request.form.get('bp')
    sugar = request.form.get('sugar')
    
    try:
        patients_table.update_item(
            Key={'email': session['user_id']},
            UpdateExpression="SET vitals = :v",
            ExpressionAttributeValues={
                ':v': {'weight': weight, 'bp': bp, 'sugar': sugar}
            }
        )
        flash('Vitals updated successfully!', 'success')
    except Exception as e:
        logger.error(f"Error updating vitals: {e}")
        flash('Error updating vitals.', 'error')
        
    return redirect(url_for('patient_dashboard'))

@app.route('/add_medical_history', methods=['POST'])
def add_medical_history():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    condition = request.form.get('condition')
    if condition:
        try:
            # Append to list (if list exists), else create new list
            patients_table.update_item(
                Key={'email': session['user_id']},
                UpdateExpression="SET medical_history = list_append(if_not_exists(medical_history, :empty_list), :c)",
                ExpressionAttributeValues={
                    ':c': [condition],
                    ':empty_list': []
                }
            )
            flash('Medical history updated.', 'success')
        except Exception as e:
            logger.error(f"Error updating history: {e}")
            flash('Error updating medical history.', 'error')
            
    return redirect(url_for('patient_dashboard'))

@app.route('/advance_status/<appt_id>')
def advance_status(appt_id):
    """Advance appointment status and auto-generate invoice on completion"""
    if session.get('role') != 'doctor':
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get current appointment
        response = appointments_table.get_item(Key={'appointment_id': appt_id})
        if 'Item' not in response:
            flash('Appointment not found', 'error')
            return redirect(url_for('doctor_dashboard'))
        
        appt = deserialize_item(response['Item'])
        current_status = appt.get('status', 'BOOKED')
        
        # Define status progression
        status_flow = {
            'BOOKED': 'CONFIRMED',
            'CONFIRMED': 'CHECKED-IN',
            'CHECKED-IN': 'CONSULTING',
            'CONSULTING': 'COMPLETED'
        }
        
        new_status = status_flow.get(current_status)
        
        if new_status:
            # Update status
            appointments_table.update_item(
                Key={'appointment_id': appt_id},
                UpdateExpression='SET #s = :status_val',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':status_val': new_status}
            )
            
            # If completing appointment, auto-generate invoice
            if new_status == 'COMPLETED':
                # Generate random consultation fee (₹500-₹2000)
                import random
                consultation_fee = random.randint(500, 2000)
                
                invoice_id = create_invoice(
                    patient_email=appt.get('patient_email'),  # Fixed: was 'patient_id'
                    appointment_id=appt_id,
                    amount=consultation_fee,
                    description=f"Consultation with Dr. {session.get('user_name', 'Doctor')}"
                )
                
                if invoice_id:
                    flash(f'Appointment completed! Invoice {invoice_id} generated for ₹{consultation_fee}', 'success')
                    
                    # Notify patient
                    notify_appointment_status_change(
                        patient_email=appt.get('patient_email'),  # Fixed: was 'patient_id'
                        status='COMPLETED',
                        appointment_id=appt_id,
                        doctor_name=session.get('user_name', 'Doctor')
                    )
                else:
                    flash('Appointment completed but invoice generation failed', 'warning')
            else:
                flash(f'Status updated to {new_status}', 'success')
                notify_appointment_status_change(
                    patient_email=appt.get('patient_email'),  # Fixed: was 'patient_id'
                    status=new_status,
                    appointment_id=appt_id,
                    doctor_name=session.get('user_name', 'Doctor')
                )
        else:
            flash('Appointment already completed', 'info')
            
    except Exception as e:
        logger.error(f"Error advancing status: {e}")
        flash('Error updating status', 'error')
    
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash('Please login as a doctor first.', 'info')
        return redirect(url_for('login'))
    
    appointments = get_doctor_appointments(session['user_id'])
    
    # Calculate stats using IST (UTC+5:30)
    from datetime import timedelta
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_str = ist_now.strftime('%Y-%m-%d')
    today_appointments = [a for a in appointments if (a.get('appointment_date') or '').startswith(today_str)]
    
    # Active Queue: Include ALL active appointments regardless of date to ensure no one is missed
    # robust case-insensitive check
    active_statuses = ['BOOKED', 'CONFIRMED', 'CHECKED-IN', 'CONSULTING']
    active_queue = [
        a for a in appointments 
        if (a.get('status') or '').upper() in active_statuses
    ]
    # Sort by time (Oldest first), safely handling None values
    active_queue.sort(key=lambda x: (x.get('appointment_date') or ''))
    
    # Calculate stats
    total_patients = len(set(a.get('patient_email') for a in appointments if a.get('patient_email')))
    
    stats = {
        'total_patients': total_patients,
        'today_patients': len(today_appointments),
        'today_appts': len(today_appointments)
    }
    
    # Mock alerts and next_patient for demo if list is empty
    next_patient = None
    if active_queue:
        # Pick the first active patient as next
        first_ppt = active_queue[0]
        # Try to get patient details
        p_email = first_ppt.get('patient_email')
        p_details = get_patient(p_email) if p_email else {}
        
        next_patient = {
            'name': first_ppt.get('patient_name', 'Unknown'),
            'id': p_email or 'Unknown',
            'dob': p_details.get('dob', 'N/A'),
            'status': first_ppt.get('status')
        }
        
    return render_template('doctor/dashboard.html', 
                         appointments=appointments,
                         active_queue=active_queue,
                         stats=stats,
                         today_appointments=today_appointments,
                         next_patient=next_patient,
                         now_date=ist_now.strftime('%d %b, %Y'),
                         alerts=[{'group': 'O-', 'units': 2}])

@app.route('/doctor/patients')
def doctor_patients_list():
    if session.get('role') != 'doctor': return redirect(url_for('login'))
    
    # Fetch appointments to derive patient list
    appointments = get_doctor_appointments(session['user_id'])
    
    # Deduplicate patients
    patient_map = {}
    for appt in appointments:
        pid = appt.get('patient_id')
        if pid and pid != 'N/A' and pid not in patient_map:
            patient_map[pid] = {
                'name': appt.get('patient_name', 'Unknown'),
                'id': pid
            }
            
    patients = list(patient_map.values())
    return render_template('doctor/patients_list.html', patients=patients)

@app.route('/doctor/appointments')
def doctor_appointments_list():
    if session.get('role') != 'doctor': return redirect(url_for('login'))
    appointments = get_doctor_appointments(session['user_id'])
    return render_template('doctor/appointments_list.html', appointments=appointments)

@app.route('/doctor/vault/<patient_id>', methods=['GET', 'POST'])
def doctor_view_vault(patient_id):
    if session.get('role') != 'doctor':
        flash('Unauthorized', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['file']
        description = request.form.get('description', 'Medical Report')
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            
            # Save file locally for demo viewing
            import os
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file.save(os.path.join(upload_folder, filename))
            
            # In a real app, upload to S3 here. For demo, we store metadata.
            file_url = f"https://s3.amazonaws.com/medtrack-vault/{filename}" # Keep mock URL for consistency
            
            # Args: patient_email, file_name, file_type, file_path, analysis
            if add_to_medical_vault(patient_id, filename, 'Report', file_url, description):
                flash('File uploaded successfully', 'success')
            else:
                flash('Error uploading file', 'error')
            return redirect(url_for('doctor_view_vault', patient_id=patient_id))

    records = get_patient_vault(patient_id)
    return render_template('patient/vault.html', records=records, patient_id=patient_id)

@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        doctor_email = request.form.get('doctor_email')
        appointment_date = request.form.get('appointment_date')
        symptoms = request.form.get('symptoms')
        
        appointment_id = create_appointment(
            session['user_id'], 
            doctor_email, 
            appointment_date, 
            symptoms
        )
        
        if appointment_id:
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('patient_dashboard'))
        else:
            flash('Error booking appointment.', 'error')
    
    
    # Mock Locations for the dropdown
    locations = {
        'Andhra Pradesh': {'Visakhapatnam': ['MedTrack Vizag'], 'Vijayawada': ['MedTrack Vijayawada']},
        'Arunachal Pradesh': {'Itanagar': ['MedTrack Itanagar']},
        'Assam': {'Guwahati': ['MedTrack Guwahati']},
        'Bihar': {'Patna': ['MedTrack Patna']},
        'Chhattisgarh': {'Raipur': ['MedTrack Raipur']},
        'Goa': {'Panaji': ['MedTrack Panaji']},
        'Gujarat': {'Ahmedabad': ['MedTrack Ahmedabad', 'MedTrack Gandhi Nagar'], 'Surat': ['MedTrack Surat']},
        'Haryana': {'Gurugram': ['MedTrack Cyber City'], 'Faridabad': ['MedTrack Faridabad']},
        'Himachal Pradesh': {'Shimla': ['MedTrack Shimla']},
        'Jharkhand': {'Ranchi': ['MedTrack Ranchi']},
        'Karnataka': {'Bangalore': ['MedTrack Tech Park', 'MedTrack City'], 'Mysore': ['MedTrack Mysore']},
        'Kerala': {'Kochi': ['MedTrack Kochi'], 'Thiruvananthapuram': ['MedTrack Trivandrum']},
        'Madhya Pradesh': {'Bhopal': ['MedTrack Bhopal'], 'Indore': ['MedTrack Indore']},
        'Maharashtra': {'Mumbai': ['MedTrack Central', 'MedTrack South'], 'Pune': ['MedTrack Pune Core'], 'Nagpur': ['MedTrack Nagpur']},
        'Manipur': {'Imphal': ['MedTrack Imphal']},
        'Meghalaya': {'Shillong': ['MedTrack Shillong']},
        'Mizoram': {'Aizawl': ['MedTrack Aizawl']},
        'Nagaland': {'Kohima': ['MedTrack Kohima']},
        'Odisha': {'Bhubaneswar': ['MedTrack Bhubaneswar']},
        'Punjab': {'Chandigarh': ['MedTrack Chandigarh'], 'Ludhiana': ['MedTrack Ludhiana']},
        'Rajasthan': {'Jaipur': ['MedTrack Jaipur'], 'Udaipur': ['MedTrack Udaipur']},
        'Sikkim': {'Gangtok': ['MedTrack Gangtok']},
        'Tamil Nadu': {'Chennai': ['MedTrack Chennai', 'MedTrack OMR'], 'Coimbatore': ['MedTrack Coimbatore']},
        'Telangana': {'Hyderabad': ['MedTrack HITEC', 'MedTrack Secunderabad']},
        'Tripura': {'Agartala': ['MedTrack Agartala']},
        'Uttar Pradesh': {'Lucknow': ['MedTrack Lucknow'], 'Noida': ['MedTrack Noida'], 'Varanasi': ['MedTrack Varanasi']},
        'Uttarakhand': {'Dehradun': ['MedTrack Dehradun']},
        'West Bengal': {'Kolkata': ['MedTrack Kolkata', 'MedTrack Salt Lake']},
        'Delhi': {'New Delhi': ['MedTrack AIIMS Link', 'MedTrack North']},
        'Jammu and Kashmir': {'Srinagar': ['MedTrack Srinagar']},
        'Ladakh': {'Leh': ['MedTrack Leh']},
        'Puducherry': {'Puducherry': ['MedTrack Pondicherry']},
        'Andaman and Nicobar Islands': {'Port Blair': ['MedTrack Port Blair']},
        'Chandigarh': {'Chandigarh': ['MedTrack Chandigarh City']},
        'Dadra and Nagar Haveli and Daman and Diu': {'Daman': ['MedTrack Daman']},
        'Lakshadweep': {'Kavaratti': ['MedTrack Kavaratti']}
    }

    doctors = get_all_doctors()
    # Normalize doctors for the template JS (ensure department key exists)
    for d in doctors:
        d['department'] = d.get('specialization', 'General')
        d['availability'] = d.get('status', 'Available')

    return render_template('patient/book.html', doctors=doctors, locations=locations)

@app.route('/ai_chat', methods=['GET', 'POST'])
def ai_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        data = request.get_json()
        message = data.get('message', '')
        
        # Get AI response
        response = get_chatbot_response(session['user_id'], message)
        
        return jsonify({
            'success': True,
            'response': response
        })
    
    return render_template('patient/assistant.html')

@app.route('/analyze_report', methods=['POST'])
def analyze_report():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('ai_chat'))
    
    file = request.files['file']
    symptoms = request.form.get('symptoms', '')
    
    # Demo Analysis Result
    analysis_result = {
        'prediction': 'Normal Range',
        'confidence': '94%',
        'summary': 'Based on the uploaded document and symptoms, your results appear to be within normal range. The AI analysis suggests no immediate concerns.',
        'modality_analysis': {
            'text_features': 'All key health indicators are within expected thresholds',
            'image_features': 'No anomalies detected in visual scan'
        }
    }
    
    return render_template('patient/assistant.html', analysis_result=analysis_result)

@app.route('/patient_assistant')
def patient_assistant():
    return redirect(url_for('ai_chat'))

@app.route('/patient_chat')
def patient_chat():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    departments = ['Cardiology', 'Neurology', 'Orthopedics', 'Pediatrics', 'General Medicine']
    return render_template('patient/chat.html', departments=departments)

@app.route('/doctor/chat')
def doctor_chat_view():
    if session.get('role') != 'doctor': return redirect(url_for('login'))
    departments = ['Cardiology', 'Neurology', 'Orthopedics', 'Pediatrics', 'General Medicine']
    return render_template('doctor/chat.html', departments=departments)

@app.route('/patient_vault', methods=['GET', 'POST'])
def patient_vault():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        description = request.form.get('description', 'Patient Upload')
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
            
        if file:
            filename = secure_filename(file.filename)
            
            # Save file locally for demo viewing
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file.save(os.path.join(upload_folder, filename))
            
            # Mock URL for demo
            file_url = f"https://s3.amazonaws.com/medtrack-vault/{filename}"
            
            # Add to vault
            if add_to_medical_vault(session['user_id'], filename, 'Patient Upload', file_url, description):
                flash('Medical record uploaded successfully', 'success')
            else:
                flash('Error uploading file', 'error')
                
            return redirect(url_for('patient_vault'))
    
    vault_items = get_patient_vault(session['user_id'])
    return render_template('patient/vault.html', records=vault_items)

@app.route('/patient_invoices')
def patient_invoices():
    """Display all invoices for the logged-in patient"""
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    patient_invoices_list = get_patient_invoices(user_id)
    
    # Calculate totals
    total_amount = sum(float(inv.get('amount', 0)) for inv in patient_invoices_list)
    unpaid_amount = sum(float(inv.get('amount', 0)) for inv in patient_invoices_list if inv.get('status') == 'unpaid')
    paid_amount = sum(float(inv.get('amount', 0)) for inv in patient_invoices_list if inv.get('status') == 'paid')
    
    return render_template('patient/invoices.html', 
                         invoices=patient_invoices_list,
                         total_amount=total_amount,
                         unpaid_amount=unpaid_amount,
                         paid_amount=paid_amount)


@app.route('/pay_invoice/<invoice_id>')
def pay_invoice(invoice_id):
    """Process invoice payment"""
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Update invoice status to paid
        invoices_table.update_item(
            Key={'invoice_id': invoice_id},
            UpdateExpression="SET #s = :status_val",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':status_val': 'paid'}
        )
        
        flash('Payment successful! Invoice marked as paid.', 'success')
        
        # Send confirmation email
        send_email_notification(
            session['user_id'],
            "MedTrack - Payment Confirmed",
            f"Your payment for invoice {invoice_id} has been processed successfully. Thank you!"
        )
        
    except Exception as e:
        logger.error(f"Payment error: {e}")
        flash('Payment processing failed. Please try again.', 'error')
    
    return redirect(url_for('patient_invoices'))

@app.route('/claim_insurance/<invoice_id>')
def claim_insurance_route(invoice_id):
    """Submit insurance claim for invoice"""
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Use existing claim_insurance function
        success = claim_insurance(invoice_id)
        
        if success:
            flash('Insurance claim submitted successfully! Processing typically takes 3-5 business days.', 'success')
            
            # Send confirmation
            send_email_notification(
                session['user_id'],
                "MedTrack - Insurance Claim Submitted",
                f"Your insurance claim for invoice {invoice_id} has been submitted. You will be notified once processed."
            )
        else:
            flash('Insurance claim submission failed. Please contact support.', 'error')
            
    except Exception as e:
        logger.error(f"Insurance claim error: {e}")
        flash('Error submitting insurance claim. Please try again.', 'error')
    
    return redirect(url_for('patient_invoices'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # In a real app, this would serve from S3 or local storage
    # For demo, we might not have the file, but we need the route to exist
    import os
    upload_folder = os.path.join(os.getcwd(), 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return send_from_directory(upload_folder, filename)

@app.route('/upload_medical_file', methods=['POST'])
def upload_medical_file():
    if 'user_id' not in session or session.get('role') != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Determine file type
    file_type = 'image' if filename.lower().endswith(('.png', '.jpg', '.jpeg')) else 'document'
    
    # Add to vault
    vault_id = add_to_medical_vault(
        session['user_id'], 
        filename, 
        file_type, 
        file_path
    )
    
    if vault_id:
        return jsonify({'success': True, 'vault_id': vault_id})
    else:
        return jsonify({'error': 'Failed to add to vault'}), 500

@app.route('/blood_bank')
def blood_bank():
    blood_stock = get_blood_stock()
    return render_template('blood_bank.html', blood_stock=blood_stock)

@app.route('/invoices')
def invoices():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    patient_invoices = get_patient_invoices(session['user_id'])
    return render_template('patient/invoices.html', invoices=patient_invoices)

# ============================================
# CHAT API ROUTES (Added for 24/7 Support)
# ============================================

@app.route('/api/chat/send', methods=['POST'])
def api_chat_send():
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    msg_text = data.get('message')
    dept = data.get('dept', 'General')
    
    if not msg_text: return jsonify({'status': 'error', 'message': 'Empty message'}), 400

    message_id = generate_id("MSG")
    chat_item = {
        'message_id': message_id,
        'id': message_id, # Alias for frontend
        'sender_email': session['user_id'],
        'sender': session.get('user_name', 'Patient'),
        'dept': dept,
        'message': msg_text,
        'reply': None,
        'created_at': get_current_datetime(),
        'time': datetime.now().strftime('%H:%M'),
        'role': session.get('role', 'patient')
    }
    
    # Use the table directly to support custom schema (dept, reply)
    chat_messages_table.put_item(Item=chat_item)
    return jsonify({'status': 'success'})

@app.route('/api/doctor/reply', methods=['POST'])
def api_doctor_reply():
    if session.get('role') != 'doctor': return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    chat_id = data.get('chat_id')
    reply_text = data.get('reply')
    
    if not chat_id or not reply_text: return jsonify({'status': 'error', 'message': 'Missing data'}), 400
    
    # Update logic
    chat_messages_table.update_item(
        Key={'message_id': chat_id},
        UpdateExpression="set reply = :r",
        ExpressionAttributeValues={':r': reply_text}
    )
    return jsonify({'status': 'success'})

@app.route('/api/chat/get')
def api_chat_get():
    dept = request.args.get('dept')
    
    # Scan all messages (Demo efficiency)
    response = chat_messages_table.scan()
    items = response.get('Items', [])
    messages = [deserialize_item(i) for i in items]
    
    # Filter by dept if provided
    if dept and dept != 'All':
        messages = [m for m in messages if m.get('dept') == dept]
        
    # Sort by time
    messages.sort(key=lambda x: x.get('created_at', ''))
    
    return jsonify({'status': 'success', 'messages': messages})

# ============================================
# AI ASSISTANT & MOOD APIs
# ============================================

@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    message = data.get('message', '')
    
    # Call Bedrock or Fake it for Demo if Bedrock fails
    try:
        reply = get_chatbot_response(session['user_id'], message)
    except Exception as e:
        reply = "I am currently unable to connect to the AI brain. Please try again later."
        
    return jsonify({'reply': reply})


@app.route('/debug/sns')
def debug_sns():
    """Manual trigger to test SNS"""
    if 'user_id' not in session:
        return "Please login first to test SNS with your email."
        
    email = session['user_id']
    try:
        # 1. Force Subscribe
        subscribe_email(email)
        
        # 2. Send Test
        send_email_notification(
            email, 
            "MedTrack SNS Test", 
            f"This is a test message sent at {get_current_datetime()} to verify your connection."
        )
        return f"SNS Test Sent to {email}. Check your inbox (and spam) for a 'Subscription Confirmation' link or the test message."
    except Exception as e:
        return f"SNS Failure: {e}"


# ============================================
# APPOINTMENT REQUEST API ROUTES
# ============================================

@app.route('/api/appointment_request/send', methods=['POST'])
def send_appointment_request():
    """Doctor sends an appointment request to a patient"""
    if 'user_id' not in session or session.get('role') != 'doctor':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        patient_email = data.get('patient_email')
        proposed_date = data.get('proposed_date')
        reason = data.get('reason', '')
        
        if not patient_email or not proposed_date:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        request_id = create_appointment_request(
            doctor_email=session['user_id'],
            patient_email=patient_email,
            proposed_date=proposed_date,
            reason=reason
        )
        
        if request_id:
            return jsonify({
                'status': 'success',
                'message': 'Appointment request sent successfully',
                'request_id': request_id
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send request'}), 500
            
    except Exception as e:
        logger.error(f"Error in send_appointment_request: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/appointment_request/accept/<request_id>', methods=['POST'])
def accept_request(request_id):
    """Patient accepts an appointment request"""
    if 'user_id' not in session or session.get('role') != 'patient':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        # Verify the request belongs to this patient
        req = get_appointment_request(request_id)
        if not req:
            return jsonify({'status': 'error', 'message': 'Request not found'}), 404
        
        if req['patient_email'] != session['user_id']:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        if accept_appointment_request(request_id):
            flash('Appointment request accepted successfully!', 'success')
            return jsonify({
                'status': 'success',
                'message': 'Appointment request accepted and appointment created'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to accept request'}), 500
            
    except Exception as e:
        logger.error(f"Error in accept_request: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/appointment_request/decline/<request_id>', methods=['POST'])
def decline_request(request_id):
    """Patient declines an appointment request"""
    if 'user_id' not in session or session.get('role') != 'patient':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        # Verify the request belongs to this patient
        req = get_appointment_request(request_id)
        if not req:
            return jsonify({'status': 'error', 'message': 'Request not found'}), 404
        
        if req['patient_email'] != session['user_id']:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        if decline_appointment_request(request_id, reason):
            flash('Appointment request declined.', 'info')
            return jsonify({
                'status': 'success',
                'message': 'Appointment request declined'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to decline request'}), 500
            
    except Exception as e:
        logger.error(f"Error in decline_request: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/appointment_request/list')
def list_appointment_requests():
    """Get appointment requests for the logged-in user"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        role = session.get('role')
        status_filter = request.args.get('status')  # Optional: PENDING, ACCEPTED, DECLINED
        
        if role == 'patient':
            requests = get_patient_appointment_requests(session['user_id'], status_filter)
        elif role == 'doctor':
            requests = get_doctor_appointment_requests(session['user_id'], status_filter)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid role'}), 403
        
        return jsonify({
            'status': 'success',
            'requests': requests
        })
        
    except Exception as e:
        logger.error(f"Error in list_appointment_requests: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500




@app.route('/debug_data')
def debug_data():
    """Temporary route to debug data visibility issues"""
    from datetime import timedelta
    
    # 1. Get Server Time Details
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    today_str_ist = ist_now.strftime('%Y-%m-%d')
    
    # 2. Fetch Appointments
    raw_appts = []
    try:
        # Check if using DynamoDB boto3 Table resource
        if hasattr(appointments_table, 'scan'):
            response = appointments_table.scan()
            raw_appts = response.get('Items', [])
            # Deserialize decimals if needed
            raw_appts = [deserialize_item(a) for a in raw_appts]
        # Check if using simple list (fallback)
        elif isinstance(appointments_table, list):
            raw_appts = appointments_table
        # Check if using custom MockTable
        elif hasattr(appointments_table, 'items'):
            raw_appts = appointments_table.items
    except Exception as e:
        raw_appts = [{"error": str(e)}]

    # 3. Analyze why they might be hidden from dashboard
    analysis = []
    for appt in raw_appts:
        appt_date = appt.get('appointment_date', '')
        status = appt.get('status', '')
        
        is_today = str(appt_date).startswith(today_str_ist)
        is_active = status in ['BOOKED', 'CONFIRMED', 'CHECKED-IN', 'CONSULTING']
        
        analysis.append({
            'id': appt.get('appointment_id'),
            'date_stored': str(appt_date),
            'status': status,
            'server_today_ist': today_str_ist,
            'is_considered_today': is_today,
            'is_considered_active': is_active,
            'visible_on_dashboard': is_today and is_active
        })

    return jsonify({
        'server_time_utc': str(utc_now),
        'server_time_ist': str(ist_now),
        'dashboard_filter_date': today_str_ist,
        'all_appointments': raw_appts,
        'visibility_analysis': analysis
    })

if __name__ == '__main__':
    print("--- MedTrack AWS Setup Complete ---")
    print("Initializing DynamoDB Tables...")
    try:
        create_tables()
    except Exception as e:
        print(f"Warning: Could not create tables (Check AWS Credentials): {e}")

    print("Starting MedTrack Server with AWS Integration...")
    print(f"Server started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app.run(host='0.0.0.0', port=5000, debug=True)
