
import boto3
import json
import os
import logging
from moto import mock_aws

logger = logging.getLogger(__name__)

LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"

mock = mock_aws()
mock.start()

s3 = boto3.client('s3', region_name='us-east-1')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
except:
    pass

def save_in_global_db(key, obj):
    json_object = json.dumps(obj, separators=(',', ':'))
    try:
        # S3 save
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_object)

        # Local save
        full_path = os.path.join(LOCAL_BUCKET_DIR, key)
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(json_object)
        return True
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return False

def get_one_from_global_db(key):
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except:
        try:
            local_path = os.path.join(LOCAL_BUCKET_DIR, key)
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.loads(f.read())
        except Exception as e:
            logger.error(f"Failed to get data: {e}")
            raise

def delete(key):
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    full_path = os.path.join(LOCAL_BUCKET_DIR, key)
    if os.path.exists(full_path):
        os.remove(full_path)
