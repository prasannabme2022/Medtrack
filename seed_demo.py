"""
MedTrack — Demo Accounts Seed Script
=====================================
Run this ONCE on EC2 to create the demo patient, doctor, and admin accounts.

Usage:
    cd /home/ec2-user/Medtrack
    python3.9 seed_demo.py

Creates:
    Patient : patient@example.com  / password123
    Doctor  : doctor@example.com   / password123
    Admin   : admin@medtrack.com   / admin123  (hardcoded in login, no DB entry needed)
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()

# ── Import the app functions ─────────────────────────────────────────────────
try:
    from aws_setup import (
        get_patient, create_patient,
        get_doctor,  create_doctor,
        logger
    )
except Exception as e:
    print(f"❌ Failed to import aws_setup: {e}")
    sys.exit(1)

PASS = "✅"
SKIP = "⚠️ "
FAIL = "❌"

print()
print("=" * 55)
print("  MedTrack — Demo Account Seeder")
print("=" * 55)

results = {}

# ── 1. Seed Patient ──────────────────────────────────────────────────────────
print("\n[1/2] Creating demo patient account...")
try:
    existing = get_patient("patient@example.com")
    if existing:
        print(f"{SKIP} Patient already exists: patient@example.com")
        results['Patient'] = 'already exists'
    else:
        ok = create_patient(
            email        = "patient@example.com",
            password     = "password123",
            name         = "Demo Patient",
            phone        = "+91-9876543210",
            address      = "123 MedTrack Street, Health City",
            dob          = "1990-06-15",
            blood_group  = "O+"
        )
        if ok:
            print(f"{PASS} Patient created: patient@example.com / password123")
            results['Patient'] = 'created'
        else:
            print(f"{FAIL} Failed to create patient")
            results['Patient'] = 'failed'
except Exception as e:
    print(f"{FAIL} Error: {e}")
    results['Patient'] = f'error: {e}'

# ── 2. Seed Doctor ───────────────────────────────────────────────────────────
print("\n[2/2] Creating demo doctor account...")
try:
    existing = get_doctor("doctor@example.com")
    if existing:
        print(f"{SKIP} Doctor already exists: doctor@example.com")
        results['Doctor'] = 'already exists'
    else:
        ok = create_doctor(
            email          = "doctor@example.com",
            password       = "password123",
            name           = "Dr. Demo Doctor",
            phone          = "+91-9876543211",
            specialization = "General Medicine",
            license_number = "MED-DEMO-001"
        )
        if ok:
            print(f"{PASS} Doctor created: doctor@example.com / password123")
            results['Doctor'] = 'created'
        else:
            print(f"{FAIL} Failed to create doctor")
            results['Doctor'] = 'failed'
except Exception as e:
    print(f"{FAIL} Error: {e}")
    results['Doctor'] = f'error: {e}'

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print("  SEED RESULTS")
print("=" * 55)
for account, status in results.items():
    icon = PASS if status in ('created', 'already exists') else FAIL
    print(f"  {icon}  {account:<10} {status}")
print()
print("  Admin account is hardcoded:")
print("  Email   : admin@medtrack.com")
print("  Password: admin123")
print()
print("  Login at: http://YOUR_EC2_IP:5000/login")
print("=" * 55)
print()

all_ok = all(v in ('created', 'already exists') for v in results.values())
sys.exit(0 if all_ok else 1)
