
import boto3
import json
import logging
import os

logger = logging.getLogger(__name__)

# AWS configuration
REGION = os.environ.get('AWS_REGION') or 'eu-west-2'
BUCKET_NAME = os.environ.get('BUCKET_NAME') or 'pc-analytics-jaffar'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# Local backup configuration
LOCAL_BACKUP_ENABLED = os.environ.get('LOCAL_BACKUP_ENABLED', 'false').lower() == 'true'
LOCAL_BACKUP_DIR = os.environ.get('LOCAL_BACKUP_DIR', './local_bucket')

# Initialize S3 client
s3 = boto3.client('s3',
                  region_name=REGION,
                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def save_to_local_backup(key, data):
    """Save data to local file system if backup is enabled"""
    if not LOCAL_BACKUP_ENABLED:
        return
    
    try:
        local_path = os.path.join(LOCAL_BACKUP_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Successfully saved local backup to {local_path}")
    except Exception as e:
        logger.error(f"Failed to save local backup to {key}: {e}")

def delete_from_local_backup(key):
    """Delete file from local backup if enabled"""
    if not LOCAL_BACKUP_ENABLED:
        return
    
    try:
        local_path = os.path.join(LOCAL_BACKUP_DIR, key)
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Successfully deleted local backup {local_path}")
    except Exception as e:
        logger.error(f"Failed to delete local backup {key}: {e}")


def save_in_global_db(key, data):
    """
    Save data to S3. Supports both JSON and YAML formats.
    """
    try:
        if key.endswith('.yml'):
            content_type = 'application/x-yaml'
            content = data
        else:
            content_type = 'application/json'
            content = json.dumps(data, ensure_ascii=False)

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=content.encode('utf-8'),
                      ContentType=content_type)
        logger.info(f"Successfully saved data to {key}")
        
        # Save local backup if enabled
        save_to_local_backup(key, content)
        
    except Exception as e:
        logger.error(f"Failed to save data to {key}: {e}")
        raise


def get_one_from_global_db(filename):
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=filename)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.error(f"Error getting file from db {filename}: {e}")
        return {}


def get_max_from_global_db(filename):
    """
    Returns the content of the file ending with the highest number for a given filename prefix in S3.
    """
    max_number = -1
    max_filename = None
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=filename)
        for obj in response.get('Contents', []):
            try:
                file = obj['Key']
                parts = file.split('-')
                if len(parts) > 1:
                    number = parts[-1].split('.')[0]
                    if number.isdigit() and int(number) > max_number:
                        max_number = int(number)
                        max_filename = file
            except Exception:
                continue
        if max_filename:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=max_filename)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        else:
            return {}
    except Exception as e:
        logger.error(f"Error getting max file from db {filename}: {e}")
        return {}


def delete(key):
    """Delete an object from S3"""
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        logger.info(f"Successfully deleted {key}")
        
        # Delete from local backup if enabled
        delete_from_local_backup(key)
        
    except Exception as e:
        logger.error(f"Failed to delete {key}: {e}")
        raise


def get_one_file(key):
    """Get a single file from S3"""
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.error(f"Error getting file {key}: {e}")
        return None


def list_folder_with_filter(prefix):
    """List objects in S3 with a given prefix"""
    try:
        objects = []
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                content = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                data = json.loads(content['Body'].read().decode('utf-8'))
                objects.append(data)
            except Exception as e:
                logger.error(f"Failed to load object {obj['Key']}: {e}")
        return objects
    except Exception as e:
        logger.error(f"Failed to list objects with prefix {prefix}: {e}")
        return []


def upload_file_to_s3(file, key):
    """Upload a file to S3"""
    try:
        # Read file content for local backup
        file_content = file.read()
        file.seek(0)  # Reset file pointer for S3 upload
        
        s3.upload_fileobj(file, BUCKET_NAME, key)
        logger.info(f"Successfully uploaded file to {key}")
        
        # Save local backup if enabled
        if LOCAL_BACKUP_ENABLED:
            try:
                local_path = os.path.join(LOCAL_BACKUP_DIR, key)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(file_content)
                
                logger.info(f"Successfully saved file backup to {local_path}")
            except Exception as e:
                logger.error(f"Failed to save file backup to {key}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to upload file to {key}: {e}")
        raise


def list_sultan_objects(object_type):
    """List Sultan objects by type"""
    try:
        objects = []
        prefix = f'sultan/{object_type}/'
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                content = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                data = json.loads(content['Body'].read().decode('utf-8'))
                objects.append(data)
            except Exception as e:
                logger.error(f"Failed to load object {obj['Key']}: {e}")
        return objects
    except Exception as e:
        logger.error(f"Failed to list {object_type}: {e}")
        return []


def get_sultan_object(object_type, object_id):
    """Get a Sultan object by type and ID"""
    try:
        key = f'sultan/{object_type}/{object_id}.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.error(f"Error getting {object_type} {object_id}: {e}")
        return None


def save_sultan_object(object_type, object_id, data):
    """Save a Sultan object"""
    try:
        key = f'sultan/{object_type}/{object_id}.json'
        content = json.dumps(data, ensure_ascii=False)
        
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=content,
                      ContentType='application/json')
        logger.info(f"Successfully saved {object_type} {object_id}")
        
        # Save local backup if enabled
        save_to_local_backup(key, content)
        
        return True
    except Exception as e:
        logger.error(f"Failed to save {object_type} {object_id}: {e}")
        return False


def delete_sultan_object(object_type, object_id):
    """Delete a Sultan object"""
    try:
        key = f'sultan/{object_type}/{object_id}.json'
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        logger.info(f"Successfully deleted {object_type} {object_id}")
        
        # Delete from local backup if enabled
        delete_from_local_backup(key)
        
    except Exception as e:
        logger.error(f"Failed to delete {object_type} {object_id}: {e}")
        raise
