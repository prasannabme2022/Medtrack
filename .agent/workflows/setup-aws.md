---
description: Set up all required AWS services for MedTrack (DynamoDB tables, S3 bucket, SNS topic, Bedrock model access)
---

## Prerequisites
- AWS account with admin access
- AWS CLI installed and configured OR IAM user credentials ready
- `.env` file template ready to fill in

## Step 1 — Create IAM User

1. Go to AWS Console → IAM → Users → Add users
2. Name: `medtrack-app-user`
3. Select **Access key – Programmatic access**
4. Attach these managed policies:
   - `AmazonDynamoDBFullAccess`
   - `AmazonSNSFullAccess`
   - `AmazonS3FullAccess`
   - `AmazonRekognitionFullAccess`
   - `ComprehendMedicalFullAccess`
   - `AmazonTextractFullAccess`
   - `AmazonBedrockFullAccess`
5. Download the CSV with Access Key ID and Secret Access Key

## Step 2 — Create S3 Bucket

1. Go to AWS Console → S3 → Create bucket
2. Bucket name: `medtrack-ai-inputs`
3. Region: `us-east-1`
4. Block all public access: **Enabled**
5. Server-side encryption: **SSE-S3 (AES-256)**
6. Click Create bucket

## Step 3 — Create SNS Topic

1. Go to AWS Console → SNS → Topics → Create topic
2. Type: **Standard**
3. Name: `Medtrack_cloud_enabled_healthcare_management`
4. Click Create topic
5. Copy the Topic ARN (e.g. `arn:aws:sns:us-east-1:ACCOUNT_ID:Medtrack_...`)
6. Create a subscription: Protocol = **Email**, Endpoint = your email
7. Confirm the subscription from your inbox

## Step 4 — Enable Bedrock Model Access

1. Go to AWS Console → Amazon Bedrock → Model access
2. Click **Manage model access**
3. Enable: `Claude 3 Haiku` and `Claude 3 Sonnet`
4. Accept EULA and click **Request model access**
5. Wait for status → **Access granted**

## Step 5 — Configure .env File

Create/update `medtrack/.env`:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA__YOUR_KEY_HERE__
AWS_SECRET_ACCESS_KEY=__YOUR_SECRET_HERE__
AI_S3_BUCKET=medtrack-ai-inputs
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:Medtrack_cloud_enabled_healthcare_management
SECRET_KEY=your-secure-random-key-here
```

## Step 6 — Create DynamoDB Tables

// turbo
Run the app once to auto-create all 9 tables:
```bash
cd c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack
python -c "from aws_setup import create_tables; create_tables(); print('Tables created!')"
```

## Step 7 — Verify All Services

// turbo
Run the verifier:
```bash
python verify_aws.py
```

All 7 services should show ✅ CONNECTED.
