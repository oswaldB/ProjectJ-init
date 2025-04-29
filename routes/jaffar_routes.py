from flask import Blueprint, render_template, redirect, request, jsonify
import datetime
import json
import os
import logging
from services.email_service import send_confirmation_if_needed
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, CircularRefEncoder, get_max_from_global_db, delete, save_in_global_db

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

        # Save to S3
        logger.info("Starting S3 save")
        try:
            s3.put_object(
                Bucket=BUCKET_NAME, 
                Key=key, 
                Body=json_data.encode('utf-8'), 
                ContentType='application/json'
            )
            logger.info("S3 save completed successfully")
        except Exception as s3_error:
            logger.error(f"S3 save failed: {s3_error}")
            raise

        # Save locally
        logger.info("Starting local save")
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        logger.info(f"Local path generated: {local_path}")
        
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
        logger.info("Local save completed successfully")

        return True
    except Exception as e:
        logger.error(f"Failed to save issue {issue_id}: {e}")
        raise

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

@jaffar_bp.route('/api/config')
def api_jaffar_config():
    try:
        config = get_max_from_global_db('jaffarConfig')
        return jsonify(config)
    except Exception as e:
        logger.error(f"Failed to load Jaffar config: {e}")
        return jsonify({"error": "Config not found"}), 404

@jaffar_bp.route('/api/issues/list', methods=['GET'])
def list_issues():
    issues = []
    try:
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
        return jsonify(issues)
    except Exception as e:
        logger.error(f"Error in list_issues: {e}")
        return jsonify({"error": str(e)}), 500

@jaffar_bp.route('/api/issues/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    for status in ['draft', 'new']:
        try:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            return jsonify(json.loads(response['Body'].read().decode('utf-8')))
        except s3.exceptions.NoSuchKey:
            continue
    return jsonify({'error': 'Issue not found'}), 404

@jaffar_bp.route('/api/issues/<issue_id>/comments', methods=['POST'])
def add_comment(issue_id):
    comment = request.json
    for status in ['draft', 'new']:
        key = f'jaffar/issues/{status}/{issue_id}.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            issue = json.loads(response['Body'].read().decode('utf-8'))
            if 'comments' not in issue:
                issue['comments'] = []
            issue['comments'].append(comment)
            s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(issue, ensure_ascii=False))
            return jsonify(issue)
        except s3.exceptions.NoSuchKey:
            continue
    return jsonify({'error': 'Issue not found'}), 404

@jaffar_bp.route('/api/acknowledge', methods=['POST'])
def api_acknowledge():
    data = request.json
    issue_id = data.get('issueId')
    email = data.get('email')

    for folder in ['draft', 'new']:
        s3_key = f'jaffar/issues/{folder}/{issue_id}.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            issue = json.loads(response['Body'].read().decode('utf-8'))

            if 'acknowledgeEscalation' not in issue:
                issue['acknowledgeEscalation'] = []

            issue['acknowledgeEscalation'].append({
                'email': email,
                'date': datetime.datetime.now().isoformat()
            })

            s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=json.dumps(issue))
            return jsonify({'status': 'success'})
        except s3.exceptions.NoSuchKey:
            continue
        except Exception as e:
            logger.error(f"Error processing acknowledgement: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Issue not found'}), 404