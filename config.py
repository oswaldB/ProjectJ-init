
import boto3
import json
import os
from moto import mock_aws

# Local storage configuration
LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"
LOCAL_BACKUP_ENABLED = True
os.makedirs(LOCAL_BUCKET_DIR, exist_ok=True)

# Initialize mocked AWS
mock = mock_aws()
mock.start()

# Create S3 client and bucket
s3 = boto3.client('s3', region_name='us-east-1')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
except:
    pass

class CircularRefEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except:
            return str(obj)

def restore_local_to_s3():
    for root, _, files in os.walk(LOCAL_BUCKET_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            s3_key = os.path.relpath(local_path, LOCAL_BUCKET_DIR)
            try:
                # Try to read as text first (for JSON files)
                if file.endswith('.json'):
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=content)
                else:
                    # Read as binary for other files (PDFs, etc.)
                    with open(local_path, 'rb') as f:
                        content = f.read()
                        s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=content)
            except Exception as e:
                print(f"Failed to restore {s3_key} to S3: {e}")

# Initialize S3 with local data
restore_local_to_s3()
