
import logging
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, remove_circular_references, CircularRefEncoder
import json
import os

logger = logging.getLogger(__name__)

def save_issue(issue_id, status, data):
    logger.info(f"Saving issue {issue_id}")
    key = f'jaffar/issues/{status}/{issue_id}.json'
    
    # Clean and serialize data
    cleaned_data = remove_circular_references(data)
    json_data = json.dumps(cleaned_data, ensure_ascii=False, cls=CircularRefEncoder)
    
    try:
        # Save to S3
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_data.encode('utf-8'))
        
        # Save locally
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
        return True
    except Exception as e:
        logger.error(f"Failed to save issue {issue_id}: {e}")
        return False
