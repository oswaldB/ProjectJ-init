
import json
import os
import logging
from config import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, CircularRefEncoder

logger = logging.getLogger(__name__)

def get_max_from_global_db(prefix):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        if 'Contents' in response:
            max_value = max(response['Contents'], key=lambda x: x['LastModified'])
            response = s3.get_object(Bucket=BUCKET_NAME, Key=max_value['Key'])
            return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to get max from DB: {e}")
        return None

def load_from_global_db(key):
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to load from DB: {e}")
        return None

def save_in_global_db(key, obj):
    json_object = json.dumps(obj, separators=(',', ':'), cls=CircularRefEncoder)
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_object)
        full_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(json_object)
        return True
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return False

def delete(key):
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        full_path = os.path.join(LOCAL_BUCKET_DIR, key)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        logger.error(f"Failed to delete {key}: {e}")
