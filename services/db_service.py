
import json
import os
import logging
from config import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, CircularRefEncoder

logger = logging.getLogger(__name__)

# Basic CRUD operations
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

def list_objects(prefix):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        return response.get('Contents', [])
    except Exception as e:
        logger.error(f"Failed to list objects with prefix {prefix}: {e}")
        return []

def object_exists(key):
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except:
        return False

# Issue-specific operations
def get_issue(issue_id):
    for status in ['draft', 'new']:
        try:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            return load_from_global_db(key)
        except:
            continue
    return None

def list_issues():
    issues = []
    for status in ['draft', 'new']:
        prefix = f'jaffar/issues/{status}/'
        objects = list_objects(prefix)
        for obj in objects:
            try:
                issue = load_from_global_db(obj['Key'])
                if issue and 'changes' in issue:
                    del issue['changes']  # Remove changes to reduce payload
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.error(f"Error loading issue {obj['Key']}: {e}")
    return issues

def save_issue(issue_id, status, data):
    # Check if issue already exists in 'new' status
    new_key = f'jaffar/issues/new/{issue_id}.json'
    if object_exists(new_key) and status == 'draft':
        key = new_key
    else:
        key = f'jaffar/issues/{status}/{issue_id}.json'
    
    # Add config array
    config = []
    configs = {
        "escalation": get_max_filename_from_global_db("escalationRules.json"),
        "questions": get_max_filename_from_global_db("jaffarConfig.json"),
        "templates": get_max_filename_from_global_db("templates.json"),
        "rules": get_max_filename_from_global_db("rules.json")
    }
    
    for key_name, value in configs.items():
        if value:
            config.append({key_name: value})
    
    data['config'] = config
    return save_in_global_db(key, data)

def get_issue_changes(issue_id):
    key = f'jaffar/issues/changes/{issue_id}-changes.json'
    try:
        return load_from_global_db(key) or []
    except:
        return []

def save_issue_changes(issue_id, new_changes):
    if not isinstance(new_changes, list):
        new_changes = [new_changes]
    
    if not new_changes:
        return
    
    key = f'jaffar/issues/changes/{issue_id}-changes.json'
    
    try:
        existing_changes = load_from_global_db(key) or []
        if not isinstance(existing_changes, list):
            existing_changes = [existing_changes]
        
        for change in new_changes:
            if change not in existing_changes:
                existing_changes.append(change)
        
        save_in_global_db(key, existing_changes)
    except Exception as e:
        logger.error(f"Error saving changes: {e}")

def get_max_filename_from_global_db(suffix):
    prefix = 'jaffar/configs/'
    try:
        objects = list_objects(prefix)
        max_num = 0
        max_key = None
        
        for obj in objects:
            if obj['Key'].endswith(suffix):
                num = int(obj['Key'].split('/')[-1].split('-')[0])
                if num > max_num:
                    max_num = num
                    max_key = obj['Key']
        return max_key
    except Exception as e:
        logger.error(f"Failed to get max filename: {e}")
        return None

# Sultan module operations
def list_sultan_objects(module_type):
    """Generic function to list Sultan objects (escalations, sites, emailgroups, etc.)"""
    objects = []
    prefix = f'sultan/{module_type}/'
    try:
        s3_objects = list_objects(prefix)
        for obj in s3_objects:
            try:
                content = load_from_global_db(obj['Key'])
                if content:
                    objects.append(content)
            except Exception as e:
                logger.error(f"Failed to load {module_type} {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list {module_type}: {e}")
    return objects

def get_sultan_object(module_type, object_id):
    """Generic function to get a Sultan object"""
    key = f'sultan/{module_type}/{object_id}.json'
    return load_from_global_db(key)

def save_sultan_object(module_type, object_id, data):
    """Generic function to save a Sultan object"""
    key = f'sultan/{module_type}/{object_id}.json'
    return save_in_global_db(key, data)

def delete_sultan_object(module_type, object_id):
    """Generic function to delete a Sultan object"""
    key = f'sultan/{module_type}/{object_id}.json'
    return delete(key)

# Feedback operations
def get_feedback_list():
    key = 'users_feedbacks/ideas.json'
    try:
        return load_from_global_db(key) or []
    except:
        return []

def save_feedback_list(ideas):
    key = 'users_feedbacks/ideas.json'
    return save_in_global_db(key, ideas)
