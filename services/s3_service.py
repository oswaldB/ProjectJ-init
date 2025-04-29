
import json
import os
import boto3
from datetime import datetime

LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"

s3 = boto3.client('s3', region_name='us-east-1')

def save_issue_to_storage(issue_id, status, data):
    folder = status if status else 'draft'
    key = f'jaffar/issues/{folder}/{issue_id}.json'
    
    try:
        content = json.dumps(data, indent=2)
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=content)
        
        # Local save
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Failed to save issue: {e}")
        return False

def save_issue_changes(issue_id, changes):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    key = f'changes/{issue_id}-{timestamp}.json'
    
    try:
        content = json.dumps(changes, indent=2)
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=content)
        
        # Local save
        local_path = os.path.join(LOCAL_BUCKET_DIR, 'changes', f'{issue_id}-{timestamp}.json')
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Failed to save changes: {e}")
        return False

def get_changes_from_global_db(issue_id):
    changes = []
    prefix = f'jaffar/issues/changes/{issue_id}'
    
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                change = json.loads(content)
                changes.append(change)
            except Exception as e:
                print(f"Failed to load change {obj['Key']}: {e}")
    except Exception as e:
        print(f"Failed to list changes: {e}")
    
    return changes
