
from flask import Blueprint, render_template, redirect, request, jsonify
import datetime
import json
import os
import logging
from services.email_service import send_confirmation_if_needed
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, remove_circular_references, CircularRefEncoder

logger = logging.getLogger(__name__)
jaffar_bp = Blueprint('jaffar', __name__)

def save_issue_to_storage(issue_id, status, data):
    logger.info(f"Saving issue {issue_id}")
    
    # Remove changes from main data
    main_data = data.copy()
    changes = main_data.pop('changes', None)
    
    # Save issue data
    key = f'jaffar/issues/{status}/{issue_id}.json'
    cleaned_data = remove_circular_references(main_data)
    json_data = json.dumps(cleaned_data, ensure_ascii=False, cls=CircularRefEncoder)
    
    try:
        # Save to S3
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_data.encode('utf-8'))
        
        # Save locally
        local_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
            
        # Save changes if present
        if changes:
            save_issue_changes(issue_id, changes)
            
        return True
    except Exception as e:
        logger.error(f"Failed to save issue {issue_id}: {e}")
        return False

def save_issue_changes(issue_id, changes):
    changes_key = f'jaffar/issues/changes/{issue_id}-changes.json'
    try:
        json_data = json.dumps(changes, ensure_ascii=False)
        s3.put_object(Bucket=BUCKET_NAME, Key=changes_key, Body=json_data.encode('utf-8'))
        
        local_path = os.path.join(LOCAL_BUCKET_DIR, changes_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
    except Exception as e:
        logger.error(f"Failed to save changes for issue {issue_id}: {e}")

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

    save_issue(issue_id, 'draft', issue_data)
    return redirect(f'/edit/{issue_id}')

@jaffar_bp.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')

@jaffar_bp.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')
