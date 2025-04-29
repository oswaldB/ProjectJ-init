
from flask import Blueprint, render_template, redirect, request, jsonify
import datetime
import json
import os
import logging
from services.email_service import send_confirmation_if_needed
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, remove_circular_references, CircularRefEncoder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
jaffar_bp = Blueprint('jaffar', __name__)

def validate_save_request(data):
    if not data or 'id' not in data:
        logger.error("Missing required data in save request")
        return False
    return True

def save_issue_to_storage(issue_id, status, data):
    logger.info(f"Entering save_issue_to_storage for issue {issue_id}")
    key = f'jaffar/issues/{status}/{issue_id}.json'
    logger.info(f"Generated storage key: {key}")

    try:
        logger.info("Starting JSON serialization")
        json_data = json.dumps(data, ensure_ascii=False, cls=CircularRefEncoder)
        logger.info("JSON serialization completed")

        logger.info("Starting S3 save")
        s3.put_object(
            Bucket=BUCKET_NAME, 
            Key=key, 
            Body=json_data.encode('utf-8'), 
            ContentType='application/json'
        )
        logger.info("S3 save completed successfully")

        logger.info("Starting local save")
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        logger.info(f"Local path generated: {local_path}")
        
        logger.info("Creating directories if needed")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        logger.info("Writing file locally")
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info("Local save completed successfully")

        logger.info(f"Issue {issue_id} saved successfully to both S3 and local storage")
        return True
    except Exception as e:
        logger.error(f"Failed to save issue {issue_id}: {e}")
        return False

def save_issue_changes(issue_id, new_changes):
    logger.info(f"Starting to save changes for issue {issue_id}")
    
    if not isinstance(new_changes, list):
        logger.info(f"Converting changes to list for issue {issue_id}")
        new_changes = [new_changes]
        
    if not new_changes:
        logger.info(f"No changes to save for issue {issue_id}")
        return

    key = f'jaffar/issues/changes/{issue_id}-changes.json'
    logger.info(f"Generated changes file path: {key}")

    try:
        # Try to load existing changes
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            existing_changes = json.loads(response['Body'].read().decode('utf-8'))
            logger.info(f"Loaded {len(existing_changes)} existing changes")
            
            if not isinstance(existing_changes, list):
                existing_changes = [existing_changes]
                
            # Add only new changes that aren't already in the history
            for change in new_changes:
                if change not in existing_changes:
                    existing_changes.append(change)
                    logger.info("Added new change to history")
                    
        except Exception as e:
            logger.info(f"No existing changes found: {e}")
            existing_changes = new_changes

        json_data = json.dumps(existing_changes, ensure_ascii=False)
        logger.info(f"Successfully serialized {len(existing_changes)} changes to JSON")

        # Save to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        logger.info("Successfully saved to S3")

        # Save locally
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info(f"Successfully saved locally to {local_path}")

    except Exception as e:
        logger.error(f"Error saving changes: {e}")

def get_changes_from_global_db(issue_id):
    changes_key = f'jaffar/issues/changes/{issue_id}-changes.json'

    try:
        # Get changes from S3
        response = s3.get_object(Bucket=BUCKET_NAME, Key=changes_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except s3.exceptions.NoSuchKey:
        logger.info(f"No changes found for issue {issue_id}")
        return []
    except Exception as e:
        logger.error(f"Failed to get changes for {issue_id}: {e}")
        return []

@jaffar_bp.route('/')
def index():
    return render_template('jaffar/index.html')

@jaffar_bp.route('/edit')
def edit():
    return render_template('jaffar/edit.html')

@jaffar_bp.route('/acknowledge')
def acknowledge():
    return render_template('jaffar/acknowledge.html')

@jaffar_bp.route('/new-issue')
def new_issue():
    now = datetime.datetime.now()
    issue_id = f'JAFF-ISS-{int(now.timestamp() * 1000)}'
    user_email = request.form.get('user_email') or request.args.get('user_email')

    if not user_email:
        return redirect('/login')

    issue_data = {
        'id': issue_id,
        'author': user_email,
        'status': 'draft',
        'created_at': now.isoformat(),
        'updated_at': now.isoformat()
    }

    save_issue_to_storage(issue_id, 'draft', issue_data)
    return redirect(f'/edit/{issue_id}')

@jaffar_bp.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')

@jaffar_bp.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')
