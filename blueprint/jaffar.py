
from flask import Blueprint, render_template, jsonify, request, redirect
import logging
import json
import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
from services.s3_service import (
    save_in_global_db,
    delete,
    get_max_from_global_db,
    get_one_file,
    list_folder_with_filter
)
from services.email_service import Email
import boto3
import os

# Initialize S3 client
REGION = os.environ.get('AWS_REGION') or 'eu-west-2'
BUCKET_NAME = os.environ.get('BUCKET_NAME') or 'pc-analytics-jaffar'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

s3 = boto3.client('s3',
                  region_name=REGION,
                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

logger = logging.getLogger(__name__)

# Create Jaffar blueprint with prefix
jaffar_blueprint = Blueprint('jaffar', __name__, url_prefix='/pc-analytics-jaffar')

@jaffar_blueprint.route('/')
def index():
    return render_template('jaffar/index.html')

@jaffar_blueprint.route('/grid')
def grid():
    return render_template('jaffar/grid.html')

@jaffar_blueprint.route('/edit')
def edit():
    return render_template('jaffar/edit.html')

@jaffar_blueprint.route('/acknowledge')
def acknowledge():
    return render_template('jaffar/acknowledge.html')

@jaffar_blueprint.route('/search')
def search_page():
    return render_template('jaffar/search.html')

@jaffar_blueprint.route('/new-issue', methods=['POST'])
def new_issue():
    """
    Create a new issue with a provided description.
    """
    try:
        data = request.json
        description = data.get('description', '').strip()

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        now = datetime.datetime.now()
        issue_id = f'JAFF-ISS-{int(now.timestamp() * 1000)}'

        issue_data = {
            'id': issue_id,
            'author': data.get('author', 'system'),
            'status': 'draft',
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'issue-description': description
        }

        save_issue_to_storage(issue_id, 'draft', issue_data)
        return jsonify({'status': 'success', 'issue_id': issue_id}), 201
    except Exception as e:
        logger.error(f"Failed to create new issue: {e}")
        return jsonify({'error': str(e)}), 500

@jaffar_blueprint.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')

@jaffar_blueprint.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')

@jaffar_blueprint.route('/feedback')
def feedback():
    return render_template('jaffar/feedbacks.html')

@jaffar_blueprint.route('/login')
def login():
    return render_template('jaffar/login.html')

@jaffar_blueprint.route('/escalation')
def escalation():
    issue_id = request.args.get('issueId')
    issue = None
    if issue_id:
        # Cherche l'issue dans tous les statuts
        for status in ['draft', 'new', 'open', 'failed']:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                issue = json.loads(response['Body'].read().decode('utf-8'))
                break
            except Exception:
                continue
    
    # Récupère le template email ayant le plus grand nombre
    template_key = get_max_filename_from_global_db("templates")
    template_subject = ""
    template_message = ""
    if template_key:
        try:
            content = s3.get_object(
                Bucket=BUCKET_NAME,
                Key=template_key)['Body'].read().decode('utf-8')
            template_data = json.loads(content)
            # On suppose que le template est un tableau ou un objet avec subject/message
            if isinstance(template_data, list) and template_data:
                template = template_data[0]
            elif isinstance(template_data, dict):
                template = template_data
            else:
                template = {}
            # Utilise la fonction pour peupler les variables
            populated = populate_template_vars(template, issue)
            template_subject = populated["subject"]
            template_message = populated["body"]
        except Exception:
            pass
    return render_template('jaffar/escalation.html',
                           issue=issue,
                           template_subject=template_subject,
                           template_message=template_message)

@jaffar_blueprint.route('/remediation-board')
def remediation_board():
    return render_template('jaffar/remediation_board.html')

@jaffar_blueprint.route('/close/<issue_id>')
def close_issue_form(issue_id):
    """
    Render the close issue form.
    """
    return render_template('jaffar/close.html', issue_id=issue_id)

# Helper functions
def save_issue_to_storage(issue_id, status, data):
    """
    Saves the issue data as a JSON file in S3.
    """
    try:
        key = f'jaffar/issues/{status}/{issue_id}.json'
        json_data = json.dumps(data, ensure_ascii=False)
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json_data.encode('utf-8'),
                      ContentType='application/json')
        logger.info(f"Issue {issue_id} saved to {key}")
    except Exception as e:
        logger.error(f"Failed to save issue {issue_id}: {e}")
        raise

def get_max_filename_from_global_db(filename):
    """
    Returns the filename ending with the highest number for a given filename prefix in S3.
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
        return max_filename
    except Exception as e:
        logger.error(f"Error getting max filename from db {filename}: {e}")
        return None

def populate_template_vars(template: dict, issue: dict) -> dict:
    """
    Remplace les variables {{var}} dans le subject et le body du template par les valeurs de l'issue.
    Supporte les clés imbriquées avec {{foo.bar}}.
    Si une valeur est un tableau, elle est convertie en chaîne de caractères.
    """

    def get_value(key, data):
        parts = key.split('.')
        value = data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return ''
        if isinstance(value, list):
            return ', '.join(map(str, value))
        return value if value is not None else ''

    def replace_vars(text, data):
        if not text:
            return text
        return re.sub(r'{{\s*([\w\-\_\.]+)\s*}}',
                      lambda m: str(get_value(m.group(1), data)), text)

    return {
        "subject": replace_vars(template.get("subject", ""), issue or {}),
        "body": replace_vars(template.get("body", ""), issue or {})
    }
