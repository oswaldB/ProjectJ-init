import json
import os
import boto3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"

# Initialize S3 client with mock credentials for local development
# Replace this with a proper mocking library in a production environment.
mock = mock() # Placeholder - needs a real mock implementation
mock.start() # Placeholder - needs a real mock implementation

s3 = boto3.client(
    's3',
    aws_access_key_id='mock',
    aws_secret_access_key='mock',
    region_name='us-east-1'
)


def restore_local_to_s3():
    for root, _, files in os.walk(LOCAL_BUCKET_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            s3_key = os.path.relpath(local_path, LOCAL_BUCKET_DIR)
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
                try:
                    s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=content)
                except Exception as e:
                    logger.error(f"Failed to restore {s3_key} to S3: {e}")

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
        logger.error(f"Failed to save issue: {e}")
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
        logger.error(f"Failed to save changes: {e}")
        return False

def get_changes_from_global_db(issue_id):
    prefix = f'jaffar/issues/changes/{issue_id}'
    changes = []

    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                change = json.loads(content)
                changes.append(change)
            except Exception as e:
                logger.error(f"Failed to load change {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list changes: {e}")

    return changes

def list_issues():
    issues = []
    for status in ['draft', 'new']:
        prefix = f'jaffar/issues/{status}/'
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            if 'Contents' in response:
                for obj in response['Contents']:
                    try:
                        response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                        issue = json.loads(response['Body'].read().decode('utf-8'))
                        issues.append(issue)
                    except Exception as e:
                        logger.error(f"Error loading issue {obj['Key']}: {e}")
        except Exception as e:
            logger.error(f"Error listing issues for status {status}: {e}")
    return issues

def get_issue(issue_id):
    for status in ['draft', 'new']:
        try:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except s3.exceptions.NoSuchKey:
            continue
    return None

import re
def get_max_from_global_db(key):
    prefix = 'jaffar/configs/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        max_number = -1
        max_object = None

        for obj in response.get('Contents', []):
            remaining_parts = obj['Key'][len(prefix):]
            match = re.match(r'(\d+)-' + key, remaining_parts)
            if match:
                number = int(match.group(1))
                if number > max_number:
                    max_number = number
                    max_object = obj['Key']

        if max_object:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=max_object)
            return json.loads(response['Body'].read().decode('utf-8'))

    except Exception as e:
        logger.error(f"Error in get_max_from_global_db: {e}")
    return None

def delete_object(key):
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        if os.path.exists(local_path):
            os.remove(local_path)
        return True
    except Exception as e:
        logger.error(f"Failed to delete object {key}: {e}")
        return False