---
description: Deploy MedTrack to AWS EC2 (pull latest code and restart server)
---

## Prerequisites
- SSH access to the EC2 instance
- AWS credentials already configured on EC2
- `.env` file already present at `/home/ec2-user/Medtrack/.env`

## Steps

1. SSH into EC2
```bash
ssh -i your-key.pem ec2-user@YOUR_EC2_PUBLIC_IP
```

// turbo
2. Navigate to the project directory
```bash
cd /home/ec2-user/Medtrack
```

// turbo
3. Pull the latest code from GitHub
```bash
git pull origin main
```

// turbo
4. Kill any existing running server process
```bash
pkill -f aws_setup.py || true
```

// turbo
5. Wait 1 second for the process to fully stop
```bash
sleep 1
```

// turbo
6. Start the server in the background
```bash
nohup python3 aws_setup.py > app.log 2>&1 &
echo "Server PID: $!"
```

// turbo
7. Wait and verify the server started successfully
```bash
sleep 3 && tail -25 app.log
```

## Expected Output
```
--- MedTrack AWS Setup Complete ---
Initializing DynamoDB Tables...
Starting MedTrack Server with AWS Integration...
Server started at YYYY-MM-DD HH:MM:SS
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

## One-liner (steps 2–7)
```bash
cd /home/ec2-user/Medtrack && git pull origin main && pkill -f aws_setup.py; sleep 1 && nohup python3 aws_setup.py > app.log 2>&1 & sleep 3 && tail -25 app.log
```
