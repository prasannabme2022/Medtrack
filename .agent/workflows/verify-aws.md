---
description: Verify all 7 AWS services (DynamoDB, SNS, S3, Rekognition, Textract, Comprehend Medical, Bedrock) are connected and working
---

## Prerequisites
- `.env` file present in the medtrack directory with all AWS credentials
- `verify_aws.py` script present in the medtrack directory
- Python 3.x and required packages installed (`boto3`, `python-dotenv`)

## Steps

// turbo
1. Change to the medtrack project directory
```bash
cd c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack
```

// turbo
2. Run the AWS connection verifier script
```bash
python verify_aws.py
```

## Expected Output (All Green)
```
================================================================
  MedTrack — AWS Service Connection Report
  Region: us-east-1
================================================================
  ✅  DynamoDB          All 9 MedTrack tables present
  ✅  SNS               Topic verified — 1 confirmed subscription(s)
  ✅  S3                Bucket 'medtrack-ai-inputs' — Encryption: AES256
  ✅  Rekognition       API reachable — detect_labels ready
  ✅  Comprehend Medical 3 entities in test
  ✅  Textract          Client initialized — detect_document_text ready
  ✅  Bedrock (Claude)  Model replied: 'CONNECTED'
================================================================

  🟢  ALL 7 SERVICES CONNECTED — App is ready for production!
```

## If a Service Fails

| Error | Fix |
|---|---|
| `NoCredentialsError` | Check `.env` has `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` |
| `AccessDeniedException` | Attach the required IAM policy to your user |
| `Bedrock model not found` | Go to Bedrock Console → Model access → enable Claude |
| `S3 NoSuchBucket` | Create bucket named `medtrack-ai-inputs` |
| `SNS error` | Check `SNS_TOPIC_ARN` in `.env` is correct |
