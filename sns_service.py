import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MedTrack-SNS")

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

class SNSService:
    def __init__(self):
        self.enabled = False
        self.client = None
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Check if AWS usage is intended (env vars present)
        if BOTO3_AVAILABLE and 'AWS_ACCESS_KEY_ID' in os.environ:
            try:
                self.client = boto3.client('sns', region_name=self.region)
                self.enabled = True
                logger.info("✅ AWS SNS Client Initialized Successfully")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize AWS SNS: {e}")
        else:
            logger.info("ℹ️ AWS SNS not configured (Missing Boto3 or Keys). Running in SIMULATION mode.")

    def send_notification(self, message, subject="MedTrack Alert", phone_number=None, topic_arn=None):
        """
        Sends a notification via AWS SNS.
        If phone_number is provided, sends SMS.
        If topic_arn is provided, publishes to topic.
        Otherwise, logs locally.
        """
        
        if not self.enabled:
            # Simulation Mode
            print(f"\n[SIMULATED SNS] Subject: {subject}")
            print(f"[SIMULATED SNS] To: {phone_number or topic_arn or 'Log'}")
            print(f"[SIMULATED SNS] Message: {message}\n")
            return {"status": "simulated", "id": "mock-id-123"}
            
        try:
            if phone_number:
                response = self.client.publish(
                    PhoneNumber=phone_number,
                    Message=message,
                    Subject=subject
                )
            elif topic_arn:
                response = self.client.publish(
                    TopicArn=topic_arn,
                    Message=message,
                    Subject=subject
                )
            else:
                logger.warning("No destination provided for notification")
                return None
                
            logger.info(f"✅ Notification Sent: {response.get('MessageId')}")
            return response
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"❌ AWS SNS Error: {e}")
            return {"error": str(e)}

# Singleton
sns_client = SNSService()
