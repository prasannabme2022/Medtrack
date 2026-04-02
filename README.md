# 🏥 MedTrack - Cloud-Enabled Healthcare Management System

[![AWS](https://img.shields.io/badge/AWS-DynamoDB%20%7C%20SNS%20%7C%20EC2-orange)](https://aws.amazon.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 📋 Overview

**MedTrack** is a comprehensive, cloud-native healthcare management system built with Flask and AWS services. It provides a seamless experience for patients, doctors, and administrators to manage appointments, medical records, blood bank operations, and real-time health consultations.

### 🌟 Key Features

#### For Patients 🧑‍⚕️
- **Patient Dashboard** - View appointments, medical history, and health metrics
- **Appointment Booking** - Schedule appointments with specialized doctors
- **AI Medical Assistant** - 24/7 chatbot for health queries and symptom checking
- **Medical Vault** - Securely store and manage medical reports (images & documents)
- **AI Report Analysis** - Automated analysis of medical reports using ML
- **Mood Tracking** - Log daily mood for mental health monitoring
- **Invoice Management** - View and manage medical bills
- **Insurance Claims** - Submit and track insurance claims
- **Patient-Doctor Chat** - Real-time communication with healthcare providers

#### For Doctors 👨‍⚕️
- **Doctor Dashboard** - Manage appointments and patient queue
- **Patient History** - Access complete patient medical records
- **Diagnosis & Prescription** - Add diagnosis and prescriptions to appointments
- **AI Assistance** - ML-powered diagnosis suggestions
- **Chat with Patients** - Respond to patient queries
- **Appointment Status Management** - Update appointment workflow

#### For Administrators 🔧
- **Blood Bank Management** - Track and manage blood inventory (8 blood groups)
- **Capacity Management** - Monitor and update hospital capacity
- **User Management** - Manage patients and doctors
- **System Monitoring** - Real-time notifications via AWS SNS

---

## 🏗️ Architecture

### Technology Stack

**Backend:**
- **Flask 3.0.0** - Python web framework
- **Python 3.9+** - Core programming language
- **Werkzeug** - WSGI utilities and security

**AWS Services:**
- **Amazon DynamoDB** - NoSQL database (8 tables)
- **Amazon SNS** - Real-time notifications
- **Amazon EC2** - Application hosting
- **IAM** - Identity and access management

**Machine Learning:**
- **scikit-learn** - Symptom prediction & diagnosis
- **TensorFlow** - Deep learning for medical image analysis
- **NumPy** - Numerical computations
- **Pillow** - Image processing

**Security:**
- **Werkzeug Security** - Password hashing (PBKDF2)
- **Flask Sessions** - Secure session management
- **python-dotenv** - Environment variable management

---

## 📊 Database Schema

### DynamoDB Tables

| Table Name | Primary Key | Description |
|------------|-------------|-------------|
| `medtrack_patients` | email | Patient profiles and medical info |
| `medtrack_doctors` | email | Doctor profiles and specializations |
| `medtrack_appointments` | appointment_id | Appointment scheduling and status |
| `medtrack_medical_vault` | vault_id | Medical files metadata |
| `medtrack_blood_bank` | blood_group | Blood inventory management |
| `medtrack_invoices` | invoice_id | Billing and insurance |
| `medtrack_chat_messages` | message_id | Patient-doctor messaging |
| `medtrack_mood_logs` | mood_id | Mood tracking for patients |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- AWS Account with:
  - DynamoDB access
  - SNS access
  - IAM credentials
- Git

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/prasannabme2022/AWS-Captone-project.git
cd AWS-Captone-project
```

#### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Full version (with TensorFlow - ~700MB)
pip install -r requirements.txt

# Lightweight version (without TensorFlow - ~200MB)
pip install -r requirements-lite.txt
```

#### 4. Configure AWS Credentials

Create a `.env` file in the root directory:

```env
# Flask Configuration
SECRET_KEY=your-super-secret-key-change-in-production
FLASK_ENV=development

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key

# SNS Configuration
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:medtrack_notifications
```

#### 5. Initialize DynamoDB Tables

```bash
python aws_setup.py
```

This will create all 8 DynamoDB tables required for the application.

#### 6. Run the Application

```bash
# Development mode
python aws_setup.py

# Production mode with Waitress
waitress-serve --host=0.0.0.0 --port=5000 aws_setup:app

# Production mode with Gunicorn (Linux/Mac)
gunicorn -w 4 -b 0.0.0.0:5000 aws_setup:app
```

Access the application at: `http://localhost:5000`

---

## ☁️ AWS Deployment

### EC2 Deployment

#### 1. Launch EC2 Instance
- AMI: Amazon Linux 2 or Ubuntu 20.04
- Instance Type: t2.micro (free tier) or t2.small
- Security Group: Open ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

#### 2. Connect to EC2

```bash
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

#### 3. Install Dependencies

```bash
# Update system
sudo yum update -y  # Amazon Linux
# OR
sudo apt update && sudo apt upgrade -y  # Ubuntu

# Install Python and pip
sudo yum install python3 python3-pip git -y  # Amazon Linux
# OR
sudo apt install python3 python3-pip git -y  # Ubuntu

# Install nginx (optional - for reverse proxy)
sudo yum install nginx -y  # Amazon Linux
# OR
sudo apt install nginx -y  # Ubuntu
```

#### 4. Deploy Application

```bash
# Clone repository
git clone https://github.com/prasannabme2022/AWS-Captone-project.git
cd AWS-Captone-project

# Install Python dependencies
pip3 install -r requirements-lite.txt

# Configure environment variables
nano .env
# Add your AWS credentials and configuration

# Run with Waitress (recommended for production)
waitress-serve --host=0.0.0.0 --port=5000 aws_setup:app
```

#### 5. Configure Nginx (Optional)

```bash
sudo nano /etc/nginx/conf.d/medtrack.conf
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo systemctl restart nginx
```

---

## 🔐 Security Best Practices

1. **Environment Variables** - Never commit `.env` file to Git
2. **AWS IAM** - Use least privilege access for IAM roles
3. **Password Hashing** - Werkzeug PBKDF2 SHA-256 hashing
4. **HTTPS** - Use SSL/TLS certificates in production
5. **Session Security** - Change `SECRET_KEY` in production
6. **DynamoDB** - Enable encryption at rest
7. **SNS** - Secure topic access with IAM policies

---

## 📁 Project Structure

```
AWS-Captone-project/
├── aws_setup.py              # Main Flask app with AWS integration
├── app.py                    # Original application (legacy)
├── database.py               # In-memory database (development)
├── database_dynamo.py        # DynamoDB adapter
├── ml_engine.py              # ML models for diagnosis
├── image_diagnostic.py       # Medical image analysis
├── signal_diagnostic.py      # Medical signal processing
├── sns_service.py            # SNS notification service
├── requirements.txt          # Full dependencies
├── requirements-lite.txt     # Lightweight dependencies
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose setup
├── Procfile                  # Heroku deployment
├── .gitignore               # Git ignore rules
├── deployment.md            # Deployment guide
├── static/                  # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── images/
├── templates/               # HTML templates
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── patient_dashboard.html
│   ├── doctor_dashboard.html
│   └── ...
├── uploads/                 # Medical file uploads
└── models/                  # ML model files
```

---

## 🧪 Testing

### Test ML Features

```bash
python test_ml_feature.py
```

### Verify Symptom Prediction

```bash
python verify_symptoms.py
```

---

## 📊 ML Models

### Symptom Prediction Model
- **Algorithm:** Random Forest Classifier
- **Features:** Age, gender, symptoms, vital signs
- **Accuracy:** ~85%
- **File:** `models/symptom_model.pkl`

### Medical Image Analysis
- **Framework:** TensorFlow 2.13
- **Use Case:** X-ray, CT scan analysis
- **File:** `image_diagnostic.py`

---

## 📧 Notifications

SNS notifications are sent for:
- ✅ New patient/doctor registration
- ✅ Appointment bookings
- ✅ Appointment status updates
- ✅ Invoice generation
- ✅ Insurance claims
- ✅ Blood bank updates

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Prasanna B**
- GitHub: [@prasannabme2022](https://github.com/prasannabme2022)
- Project: [AWS Capstone Project - MedTrack](https://github.com/prasannabme2022/AWS-Captone-project)

---

## 🙏 Acknowledgments

- AWS for cloud infrastructure
- Flask community for the excellent framework
- TensorFlow team for ML capabilities
- All contributors and testers

---

## 📞 Support

For issues or questions:
1. Open an [issue](https://github.com/prasannabme2022/AWS-Captone-project/issues)
2. Check existing [documentation](deployment.md)
3. Review AWS DynamoDB and SNS documentation

---

## 🗺️ Roadmap

- [ ] Add Docker Kubernetes deployment
- [ ] Implement video consultations
- [ ] Add payment gateway integration
- [ ] Mobile app (React Native)
- [ ] Advanced AI diagnostics with deep learning
- [ ] Multi-language support
- [ ] Telemedicine features
- [ ] Electronic Health Records (EHR) integration

---

**Made with ❤️ for better healthcare management**
