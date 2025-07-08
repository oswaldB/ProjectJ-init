"""
App name: pc_analytics_jaffar
"""
import boto3
import json
import logging
from flask import Response, redirect, request, jsonify, render_template, flash
from stratpy.engine import Blueprint, settings
from stratpy.utils.email import Email
import pandas as pd
from typing import Dict
import os
import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
from apps.pc_analytics_jaffar.blueprints.clones import clones_blueprint
import requests
from apps.pc_analytics_jaffar.blueprints.forms import forms_blueprint
from apps.pc_analytics_jaffar.blueprints.sultan import sultan_blueprint
from apps.pc_analytics_jaffar.blueprints.flows import flows_bp
from apps.pc_analytics_jaffar.services.s3_service import (
    get_max_from_global_db,
    save_in_global_db,
    delete,
    get_max_filename_from_global_db,
    save_issue_to_storage,
    save_issue_changes,
    get_changes_from_global_db,
    move_draft_to_deleted
)

logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize a thread pool executor for handling email tasks
email_executor = ThreadPoolExecutor(max_workers=5)

# Custom health check
def custom_health_check():
    return Response(status=200, response="Custom health check OK")


app = Blueprint(__name__, health_check_func=custom_health_check)

# S3 bucket configuration
endpoint = settings.SG_URL
access_key = settings.SG_ID_KEY
secret_key = settings.SG_SECRET
BUCKET_NAME = settings.SG_BUCKET

logger.info(f"BUCKET_NAME: {BUCKET_NAME}")

storage_obj_config = {
    "aws_access_key_id": access_key,
    "aws_secret_access_key": secret_key,
    "endpoint_url": endpoint
}
s3 = boto3.client("s3", **storage_obj_config)


class CircularRefEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except:
            return str(obj)

# Email Service Functions
def sendConfirmationEmail(email_address: str, subject: str, issue: dict) -> bool:
    """
    Send the confirmation email to the author email address.
    """
    logger.info(f"Sending email to {email_address}")

    issue_data = process_issue_data(issue)

    style = """
    <style>
            table {
                border-collapse: collapse;
                font-family: 'Helvetica';
                font-size:   12px;
            }
            th {
                font-weight: normal
            }
            th, td {
                border: 1px solid #ccc;
                padding: 5px;
                text-align: left;
            }
            td {
                font-family: Helvetica;
                font-size:   12px;
                text-decoration: none;
            }
    </style>
    """
    df = pd.DataFrame(data=issue_data, index=[0])
    df = df.fillna(' ').T

    message = f"""
    <p>Hello,</p>
    <p>Jaffar here!</p>
    <p>I recieved your issue number: {subject}.</p>
    <hr>
    <p><strong>Description of the issue</strong></p>
    <hr>
    <br>
    {df.to_html()}
    <br>
    <br>
    <p>If it requires escalation, you will get another email very soon.</p>.
    <br>
    <br>
    <p>All the best,</p>
    """

    content = style + message

    print(content)

    # create an email
    email = Email(
        to=[email_address, "global.control.remediation.programme@noexternalmail.hsbc.com"],
        subject=subject,
        content=content,
    )
    email.send()
    return True


def flatten_dict(dd: Dict, separator='_', prefix=''):
    """
    Flattens a nested dictionary and concatenates the keys with a separator.
    """
    return {f"{prefix}{separator}{k}" if prefix else k: v
            for kk, vv in dd.items()
            for k, v in flatten_dict(vv, separator, kk).items()
            } if isinstance(dd, dict) else {prefix: dd}


def process_issue_data(issue_data):
    """
    Converts list-type values to strings and flattens nested dictionaries.
    """
    processed_data = {}
    for key, value in issue_data.items():
        if isinstance(value, list):
            processed_data[key] = ', '.join(value)
        elif isinstance(value, dict):
            flattened_dict = flatten_dict(value)
            processed_data.update(flattened_dict)
        else:
            processed_data[key] = value

    return processed_data


# Jaffar Section

def validate_save_request(data):
    if not data or 'id' not in data:
        logger.error("Missing required data in save request")
        return False
    return True


@app.route('/')
def index():
    return render_template('jaffar/index.html')


@app.route('/grid')
def grid():
    return render_template('jaffar/grid.html')


@app.route('/dashboard/<dashboard_id>')
def dashboard_grid(dashboard_id):
    return render_template('jaffar/dashboard.html')


@app.route('/edit')
def edit():
    return render_template('jaffar/edit.html')


@app.route('/acknowledge')
def acknowledge():
    return render_template('jaffar/acknowledge.html')


@app.route('/search')
def search_page():
    return render_template('jaffar/search.html')


@app.route('/new-issue', methods=['POST'])
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


@app.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')


@app.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')


@app.route('/api/jaffar/templates/list')
def api_jaffar_templates_list():
    templates = []
    prefix = 'jaffar/configs/templates-'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                content = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])['Body'].read().decode('utf-8')
                # On suppose que chaque fichier est un objet ou un tableau d'un objet
                data = json.loads(content)
                if isinstance(data, list):
                    for t in data:
                        if 'id' in t and 'name' in t:
                            templates.append({'id': t['id'], 'name': t['name']})
                elif isinstance(data, dict) and 'id' in data and 'name' in data:
                    templates.append({'id': data['id'], 'name': data['name']})
            except Exception as e:
                logger.error(f"Failed to load template {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(templates)


@app.route('/api/jaffar/config')
def api_jaffar_config():
    try:
        config = get_max_from_global_db('jaffarConfig')
        if not config:
            logger.error("No config found")
            return jsonify({"error": "Config not found"}), 404
        return jsonify(config)
    except Exception as e:
        logger.error(f"Failed to load Jaffar config: {e}")
        return jsonify({"error": "Config not found"}), 404


@app.route('/api/jaffar/issues/list', methods=['GET'])
def list_issues():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        status_param = request.args.get('status')
        if status_param:
            statuses = [status_param]
        else:
            statuses = ['draft', 'new', 'open', 'failed']
        all_keys = []
        # 1. Récupère toutes les clés des issues (sans charger les fichiers)
        for status in statuses:
            prefix = f'jaffar/issues/{status}/'
            try:
                response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('/'):
                        continue
                    all_keys.append((key, obj.get('LastModified')))
            except Exception as e:
                logger.error(f"Error listing issues for status {status}: {e}")

        # 2. Trie les clés par date de modification décroissante
        all_keys.sort(key=lambda x: x[1] or '', reverse=True)
        total = len(all_keys)
        start = (page - 1) * page_size
        end = start + page_size
        page_keys = all_keys[start:end]

        # 3. Charge seulement les fichiers de la page courante
        issues = []
        for key, _ in page_keys:
            try:
                issue = json.loads(response_obj['Body'].read().decode('utf-8'))
                if 'changes' in issue:
                    del issue['changes']
                # Ensure comments property exists
                if 'comments' not in issue:
                    issue['comments'] = []
                issues.append(issue)
            except Exception as e:
                logger.error(f"Error loading issue {key}: {e}")

        return jsonify({
            "issues": issues,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        logger.error(f"Error in list_issues: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/issues/list2', methods=['GET'])
def list_issues_v2():
    """
    Version améliorée : pagination, filtrage et tri côté serveur.
    Utilise les paramètres :
      - page, page_size
      - sort_col, sort_dir
      - filter_<col> (ex: filter_status, filter_author, ...)
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        sort_col = request.args.get('sort_col')
        sort_dir = request.args.get('sort_dir', 'asc')
        # Récupère tous les filtres de type filter_<col>
        filters = {k[7:]: v for k, v in request.args.items() if k.startswith('filter_') and v}

        all_keys = []
        for status in ['draft', 'new', 'open', 'failed']:
            prefix = f'jaffar/issues/{status}/'
            try:
                response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('/'):
                        continue
                    all_keys.append((key, obj.get('LastModified')))
            except Exception as e:
                logger.error(f"Error listing issues for status {status}: {e}")

        # Trie par date de modification décroissante (par défaut)
        all_keys.sort(key=lambda x: x[1] or '', reverse=True)

        # Charge tous les fichiers (pour filtrage/tri)
        issues = []
        for key, _ in all_keys:
            try:
                issue = json.loads(response_obj['Body'].read().decode('utf-8'))
                if 'changes' in issue:
                    del issue['changes']
                # Ensure comments property exists
                if 'comments' not in issue:
                    issue['comments'] = []
                issues.append(issue)
            except Exception as e:
                logger.error(f"Error loading issue {key}: {e}")

        # Filtrage par colonnes
        for col, val in filters.items():
            issues = [iss for iss in issues if val.lower() in str(iss.get(col, '')).lower()]

        # Tri par colonne si demandé
        if sort_col:
            issues.sort(
                key=lambda x: (x.get(sort_col) or '').lower() if isinstance(x.get(sort_col), str) else x.get(sort_col),
                reverse=(sort_dir == 'desc')
            )

        total = len(issues)
        start = (page - 1) * page_size
        end = start + page_size
        page_issues = issues[start:end]

        return jsonify({
            "issues": page_issues,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        logger.error(f"Error in list_issues_v2: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/issues/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    for status in ['draft', 'new', 'open', 'failed','closed']:
        try:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            issue = json.loads(response['Body'].read().decode('utf-8'))
            # Ensure comments property exists
            if 'comments' not in issue:
                issue['comments'] = []
            return jsonify(issue)
        except s3.exceptions.NoSuchKey:
            continue
    return jsonify({'error': 'Issue not found'}), 404


@app.route('/api/jaffar/issues/<issue_id>/changes', methods=['GET'])
def get_issue_changes(issue_id):
    try:
        key = f'jaffar/issues/changes/{issue_id}-changes.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return jsonify(json.loads(response['Body'].read().decode('utf-8')))
    except s3.exceptions.NoSuchKey:
        return jsonify([])
    except Exception as e:
        logger.error(f"Failed to get changes for {issue_id}: {e}")
        return jsonify([])


@app.route('/api/jaffar/issues/<issue_id>/comments', methods=['POST'])
def add_comment(issue_id):
    comment = request.json
    if 'timestamp' not in comment:
        comment['timestamp'] = datetime.datetime.now().isoformat()

    changes_key = f'jaffar/issues/changes/{issue_id}-changes.json'

    try:
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=changes_key)
            changes = json.loads(response['Body'].read().decode('utf-8'))
            if not isinstance(changes, list):
                changes = [changes]
        except s3.exceptions.NoSuchKey:
            changes = []

        changes.append(comment)

        json_data = json.dumps(changes, ensure_ascii=False)
        s3.put_object(Bucket=BUCKET_NAME, Key=changes_key, Body=json_data.encode('utf-8'))

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save comment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/submit', methods=['POST'])
def submit_issue():
    data = request.json
    issue_id = data.get('issueId')

    if not issue_id:
        return jsonify({'error': 'Missing issue ID'}), 400

    try:
        # Retrieve issue data
        issue_data = get_issue_data(issue_id)

        # Update the issue data
        update_issue_data(issue_data)

        # Save the updated issue data
        save_issue_to_storage(issue_id, 'open', issue_data)

        # Log the submission activity
        log_activity(issue_id, issue_data)

        # Send a confirmation email to the author
        send_confirmation_email(issue_data)

        # Trigger the escalation process
        # trigger_escalation(issue_id)

        return jsonify({
            'status': 'success',
            'redirect': f'/pc-analytics-jaffar/issue/{issue_id}',
            'message': 'Submitted!'
        })

    except Exception as e:
        logger.error(f"Failed to submit issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500


def get_issue_data(issue_id):
    """
    Récupère les données de l'issue depuis S3.
    """
    try:
        for folder in ['new', 'draft', 'open']:
            key = f'jaffar/issues/{folder}/{issue_id}.json'
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                issue_data = json.loads(response['Body'].read().decode('utf-8'))
                if folder == 'draft':
                    issue_data['status'] = 'submitted'
                    issue_data['submitted_at'] = datetime.datetime.now().isoformat()
                    issue_data['version'] = 0
                    delete(key)  # Supprimer le brouillon après récupération
                return issue_data
            except s3.exceptions.NoSuchKey:
                continue
        raise s3.exceptions.NoSuchKey(f"Issue {issue_id} not found in any folder")
    except Exception as e:
        logger.error(f"Failed to retrieve issue data for {issue_id}: {e}")
        raise


def update_issue_data(issue_data):
    """
    Met à jour les données de l'issue avec les informations nécessaires.
    """
    current_version = issue_data.get('version', 0)
    issue_data['version'] = current_version + 1
    issue_data['updated_at'] = datetime.datetime.now().isoformat()
    issue_data['status'] = 'submitted'


def log_activity(issue_id, issue_data):
    """
    Enregistre une activité système pour la soumission de l'issue.
    """
    activity = {
        "type": "system",
        "content": f"Issue submitted (version {issue_data['version']})",
        "timestamp": datetime.datetime.now().isoformat(),
        "author": issue_data.get('author', 'system'),
        "submitted_by": issue_data.get('author', 'system')
    }
    save_issue_changes(issue_id, activity)


def send_confirmation_email(issue_data):
    """
    Envoie un e-mail de confirmation à l'auteur de l'issue.
    """
    email_address = issue_data.get('author', 'system').rsplit(' - ', 1)[-1].strip()
    sendConfirmationEmail(email_address, f"Issue Submitted: {issue_data['id']}", issue_data)


def trigger_escalation(issue_id):
    """
    Calls the escalation API with the issue ID.
    """
    try:
        escalation_service_url = settings.NOW_ESCALATION_ENDPOINT
        issue_id = f"{issue_id}.json"
        escalation_response = requests.get(escalation_service_url, params={"issueId": issue_id})
        if escalation_response.status_code == 200:
            logger.info(f"Successfully called escalation service for issue {issue_id}.")
        else:
            logger.error(f"Failed to call escalation service for issue {issue_id}: {escalation_response.status_code} - {escalation_response.text}")
    except Exception as e:
        logger.error(f"Error while calling escalation service for issue {issue_id}: {e}")


@app.route('/api/jaffar/save', methods=['POST'])
def save_issue():
    try:
        data = request.json
        if not validate_save_request(data):
            return jsonify({"error": "Invalid request data"}), 400

        issue_id = data.get('id')
        status = data.get('status', 'draft')
        # Extract changes before saving issue
        changes = data.pop('changes', None)

        # Save the issue without changes
        save_issue_to_storage(issue_id, status, data)

        # Track changes if any exist
        if changes:
            save_issue_changes(issue_id, changes)

        # Send confirmation email for new issues
        if status == 'new':
            email_executor.submit(send_confirmation_if_needed, data)

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error saving issue: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/acknowledge', methods=['POST'])
def api_acknowledge():
    data = request.json
    issue_id = data.get('issueId')
    author = data.get('author')

    for folder in ['draft', 'new']:
        s3_key = f'jaffar/issues/{folder}/{issue_id}.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            issue = json.loads(response['Body'].read().decode('utf-8'))

            if 'acknowledge-escalation' not in issue:
                issue['acknowledge-escalation'] = []

            issue['acknowledge-escalation'].append({
                'author': author,
                'date': datetime.datetime.now().isoformat()
            })

            # Log the acknowledge activity
            activity = {
                "type": "system",
                "content": f"Issue acknowledged by {author}",
                "timestamp": datetime.datetime.now().isoformat(),
                "author": author
            }
            save_issue_changes(issue_id, activity)

            s3.put_object(Bucket=BUCKET_NAME,
                          Key=s3_key,
                          Body=json.dumps(issue))
            return jsonify({'status': 'success'})
        except s3.exceptions.NoSuchKey:
            continue
        except Exception as e:
            logger.error(f"Error processing acknowledgement: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Issue not found'}), 404


@app.route('/api/jaffar/issues/<issue_id>/delete', methods=['POST'])
def move_draft_to_deleted(issue_id):
    """
    Move a draft issue to the 'issues/delete' folder in S3.
    """
    try:
        # Define the source and destination keys
        source_key = f'jaffar/issues/draft/{issue_id}.json'
        destination_key = f'jaffar/issues/delete/{issue_id}.json'

        # Copy the object to the 'delete' folder
        s3.copy_object(
            Bucket=BUCKET_NAME,
            CopySource={'Bucket': BUCKET_NAME, 'Key': source_key},
            Key=destination_key
        )

        # Delete the original draft
        s3.delete_object(Bucket=BUCKET_NAME, Key=source_key)

        return jsonify({'status': 'success', 'message': f'Draft {issue_id} moved to delete folder'}), 200
    except Exception as e:
        logger.error(f"Failed to move draft {issue_id} to delete folder: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test')
def user():
    return render_template('test-directory.html')


@app.route('/api/jaffar/similarity-search', methods=['POST'])
def similarity_search():
    """
    Call the similarity search API with the provided issue details.
    """
    try:
        data = request.json
        logger.info(f"Received similarity search request with payload: {data}")

        payload = {
            "input_id": data.get("input_id"),
            "description": data.get("description"),
            "s3_bucket": BUCKET_NAME,
            "s3_key": "jaffar/issues/embeddings/embeddings.parquet",
            "similarity_threshold": 0.7
        }
        logger.info(f"Constructed payload for similarity search API: {payload}")

        response = requests.post(
            "https://palms-jaffar-similaritysearch-api-uat.ikp102s.cloud.uk.hsbc/similarity",
            json=payload
        )

        logger.info(f"Similarity search API response status: {response.status_code}")
        logger.info(f"Similarity search API response body: {response.text}")

        if response.status_code != 200:
            logger.error(f"Similarity search API failed with status {response.status_code}")
            return jsonify({"error": "Failed to fetch similar issues"}), response.status_code

        return jsonify(response.json()), 200
    except Exception as e:
        logger.error(f"Error in similarity search: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while searching for similar issues"}), 500


@app.route('/api/jaffar/feedback/list')
def list_feedback():
    try:
        key = 'users_feedbacks/ideas.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            return jsonify(json.loads(response['Body'].read().decode('utf-8')))
        except s3.exceptions.NoSuchKey:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/feedback/submit', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Missing text"}), 400

        key = 'users_feedbacks/ideas.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            ideas = json.loads(response['Body'].read().decode('utf-8'))
        except:
            ideas = []

        new_idea = {
            'id': f'IDEA-{int(datetime.datetime.now().timestamp() * 1000)}',
            'text': data['text'],
            'description': data.get('description', ''),
            'author': data.get('author', ''),
            'date': datetime.datetime.now().isoformat(),
            'votes': 0
        }
        ideas.append(new_idea)

        s3.put_object(Bucket=BUCKET_NAME, Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/feedback/vote', methods=['POST'])
def vote_feedback():
    try:
        data = request.json
        if not data or 'id' not in data or 'type' not in data:
            return jsonify({"error": "Missing data"}), 400

        key = 'users_feedbacks/ideas.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        ideas = json.loads(response['Body'].read().decode('utf-8'))

        for idea in ideas:
            if idea['id'] == data['id']:
                idea['votes'] += 1 if data['type'] == 'up' else -1
                break

        s3.put_object(Bucket=BUCKET_NAME, Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error voting on feedback: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/feedback/comment', methods=['POST'])
def add_feedback_comment():
    try:
        data = request.json
        if not data or 'ideaId' not in data or 'text' not in data:
            return jsonify({"error": "Missing data"}), 400

        key = 'users_feedbacks/ideas.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        ideas = json.loads(response['Body'].read().decode('utf-8'))

        for idea in ideas:
            if idea['id'] == data['ideaId']:
                if 'comments' not in idea:
                    idea['comments'] = []

                comment = {
                    'id': f"COMMENT-{int(datetime.datetime.now().timestamp() * 1000)}",
                    'text': data['text'],
                    'author': data.get('author', ''),  # <-- utilise l'auteur envoyé
                    'date': datetime.datetime.now().isoformat(),
                    'parentId': data.get('parentId', None),
                    'replies': []
                }

                if data.get('parentId'):
                    # Add as reply to existing comment
                    for existing_comment in idea['comments']:
                        if existing_comment['id'] == data['parentId']:
                            existing_comment['replies'].append(comment)
                            break
                else:
                    # Add as top-level comment
                    idea['comments'].append(comment)
                break

        s3.put_object(Bucket=BUCKET_NAME, Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/feedback')
def feedback():
    return render_template('jaffar/feedbacks.html')


@app.route('/login')
def tutorial():
    return render_template('jaffar/login.html')


@app.route('/api/jaffar/grid-views/save', methods=['POST'])
def save_grid_view():
    data = request.json
    user = data.get('user', 'anonymous')
    name = data.get('name')
    config = data.get('config')
    if not name or not config:
        return jsonify({'error': 'Missing name or config'}), 400
    key = f'jaffar/grid-views/{user}/{name}.json'
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(config))
    return jsonify({'status': 'success'})


@app.route('/api/jaffar/grid-views/list')
def list_grid_views():
    user = request.args.get('user', 'anonymous')
    prefix = f'jaffar/grid-views/{user}/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)<replit_final_file>
        views = []
        for obj in response.get('Contents', []):
            name = obj['Key'].split('/')[-1].replace('.json', '')
            views.append(name)
        return jsonify(views)
    except Exception as e:
        return jsonify([])


@app.route('/api/jaffar/grid-views/get')
def get_grid_view():
    user = request.args.get('user', 'anonymous')
    name = request.args.get('name')
    key = f'jaffar/grid-views/{user}/{name}.json'
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return jsonify(json.loads(obj['Body'].read().decode('utf-8')))
    except Exception:
        return jsonify({}), 404


@app.route('/escalation')
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
            content = s3.get_object(Bucket=BUCKET_NAME, Key=template_key)['Body'].read().decode('utf-8')
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


@app.route('/remediation-board')
def remediation_board():
    return render_template('jaffar/remediation_board.html')


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
        return re.sub(r'{{\s*([\w\-\_\.]+)\s*}}', lambda m: str(get_value(m.group(1), data)), text)

    return {
        "subject": replace_vars(template.get("subject", ""), issue or {}),
        "body": replace_vars(template.get("body", ""), issue or {})
    }


@app.route('/api/jaffar/escalation/send', methods=['POST'])
def api_jaffar_escalation_send():
    data = request.json
    recipients = data.get('recipients', '')
    subject = data.get('subject', '')
    message = data.get('message', '')
    issue_id = data.get('issueId', '')

    # Récupère l'issue pour peupler les variables dynamiques
    issue = None
    if issue_id:
        for status in ['draft', 'new', 'open', 'failed']:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                issue = json.loads(response['Body'].read().decode('utf-8'))
                break
            except Exception:
                continue

    # Utilise la fonction pour peupler les variables dynamiques dans subject/message
    template = {"subject": subject, "body": message}
    populated = populate_template_vars(template, issue)
    subject = populated["subject"]
    message = populated["body"]

    try:
        send_escalation_email(recipients, subject, message, issue_id)
        # Ajoute une activité système dans le fichier -changes
        if issue_id:
            activity = {
                "type": "system",
                "content": f"Escalation email sent to: {recipients}",
                "timestamp": datetime.datetime.now().isoformat(),
                "author": "system"
            }
            save_issue_changes(issue_id, activity)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Failed to send escalation email: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


def send_escalation_email(recipients, subject, message, issue_id):
    """
    Envoie un email d'escalade à la liste de destinataires + l'adresse globale.
    """
    # Nettoie et split les emails
    recipient_list = [email.strip() for email in recipients.split(',') if email.strip()]
    # Ajoute le destinataire obligatoire
    if "global.control.remediation.programme@noexternalmail.hsbc.com" not in recipient_list:
        recipient_list.append("global.control.remediation.programme@noexternalmail.hsbc.com")
    # Optionnel : Ajoute un lien vers l'issue si issue_id fourni
    if issue_id:
        issue_link = f"<br><br><a href='/pc-analytics-jaffar/issue/{issue_id}'>View Issue {issue_id}</a>"
        message += issue_link
    email = Email(
        to=recipient_list,
        subject=subject,
        content=message,
    )
    email.send()


@app.route('/api/jaffar/issues/<issue_id>/escalation', methods=['POST'])
def save_escalation(issue_id):
    """
    Save escalation details in the issue JSON.
    """
    try:
        data = request.json
        user = data.get('user', 'system')
        date = data.get('date', datetime.datetime.now().isoformat())

        for status in ['draft', 'new', 'open', 'failed']:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                issue = json.loads(response['Body'].read().decode('utf-8'))

                if 'escalation' not in issue:
                    issue['escalation'] = []

                issue['escalation'].append({
                    'user': user,
                    'date': date
                })
                logger.info(f"Issue escalation data: {issue}")
                logger.info(f"Issue located: {key}")

                s3.put_object(
                    Bucket=BUCKET_NAME,
                    Key=key,
                    Body=json.dumps(issue, ensure_ascii=False),
                    ContentType='application/json'
                )
                return jsonify({'status': 'success'})
            except s3.exceptions.NoSuchKey:
                continue
        return jsonify({'error': 'Issue not found'}), 404
    except Exception as e:
        logger.error(f"Failed to save escalation for issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/close/<issue_id>')
def close_issue_form(issue_id):
    """
    Render the close issue form.
    """
    return render_template('jaffar/close.html', issue_id=issue_id)


@app.route('/api/jaffar/issues/<issue_id>/close', methods=['POST'])
def close_issue(issue_id):
    """
    Close the issue, log the event in the changes file,
    """
    data = request.json
    reason = data.get('reason', '').strip()
    closed_by = data.get('closed_by', 'system')  # Get the user who closed the issue

    if not reason:
        return jsonify({'error': 'Reason is required'}), 400

    # Retrieve the issue
    issue_data = None
    for status in ['draft', 'new', 'open', 'failed']:
        key = f'jaffar/issues/{status}/{issue_id}.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            issue_data = json.loads(response['Body'].read().decode('utf-8'))
            break
        except s3.exceptions.NoSuchKey:
            continue

    if not issue_data:
        return jsonify({'error': 'Issue not found'}), 404

    # Update issue status and add reason
    issue_data['status'] = 'closed'
    issue_data['closed_reason'] = reason
    issue_data['closed_at'] = datetime.datetime.now().isoformat()

    # Log the close event in the changes file
    close_event = {
        "type": "system",
        "content": f"Issue closed with reason: {reason}",
        "timestamp": datetime.datetime.now().isoformat(),
        "author": closed_by  # Save the user who closed the issue
    }
    save_issue_changes(issue_id, close_event)

    # Move issue to 'closed' folder
    closed_key = f'jaffar/issues/closed/{issue_id}.json'
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=closed_key,
        Body=json.dumps(issue_data, ensure_ascii=False),
        ContentType='application/json'
    )

    # Delete the original issue
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)

    return jsonify({'status': 'success', 'message': f'Issue {issue_id} closed successfully'}), 200


# Sultan Section
@app.route('/sultan/')
def sultan_index():
    return render_template('sultan/forms/index.html')


@app.route('/sultan/login')
def sultan_login():
    return render_template('sultan/login.html')


@app.route('/sultan/forms')
def forms_list():
    return render_template('sultan/forms/index.html')


@app.route('/sultan/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')


@app.route('/sultan/escalation')
def escalation_list():
    return render_template('/sultan/escalation/index.html')


@app.route('/sultan/escalation/create')
def escalation_create():
    import uuid
    new_id = f"Escalation-{uuid.uuid4()}"
    # Structure vide ou par défaut
    escalation = []
    key = f"sultan/escalations/{new_id}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(escalation, ensure_ascii=False),
        ContentType='application/json'
    )
    # Redirige vers la page d'édition
    return redirect(f"/pc-analytics-jaffar/sultan/escalation/edit/{new_id}")


@app.route('/sultan/escalation/edit/<escalation_id>')
def escalation_edit(escalation_id):
    return render_template('sultan/escalation/edit.html')


@app.route('/sultan/emailgroups')
def emailgroups_list():
    return render_template('sultan/emailgroups/index.html')


@app.route('/sultan/emailgroups/edit/<emailgroup_id>')
def emailgroup_edit(emailgroup_id):
    return render_template('sultan/emailgroups/edit.html')


@app.route('/sultan/sites')
def sites_list():
    return render_template('sultan/sites/index.html')


@app.route('/sultan/sites/edit/<site_id>')
def site_edit(site_id):
    return render_template('sultan/sites/edit.html')


@app.route('/sultan/templates')
def templates_list():
    return render_template('sultan/templates/index.html')


@app.route('/sultan/templates/edit/<template_id>')
def template_edit(template_id):
    return render_template('sultan/templates/edit2.html')


@app.route('/sultan/templates/edit-datatable/<template_id>')
def template_edit_datatable(template_id):
    return render_template('sultan/templates/edit-datatable.html')


@app.route('/sultan/dashboard/<dashboard_id>')
def sultan_dashboard_edit(dashboard_id):
    # Render the datatable editor for a given dashboard
    return render_template('sultan/dashboards/edit.html', dashboard_id=dashboard_id)


@app.route('/api/sultan/dashboard/<dashboard_id>', methods=['GET'])
def api_sultan_dashboard_get(dashboard_id):
    """
    Get a dashboard config from S3 (sultan/dashboards/{dashboard_id}.json)
    """
    key = f'sultan/dashboards/{dashboard_id}.json'
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        dashboard = json.loads(response['Body'].read().decode('utf-8'))
        return jsonify(dashboard)
    except s3.exceptions.NoSuchKey:
        return jsonify({"error": "Dashboard not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get dashboard {dashboard_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/dashboard/create', methods=['POST'])
def api_sultan_dashboard_create():
    """
    Create a new dashboard config in S3 (sultan/dashboards/{dashboard_id}.json)
    Expects JSON: { "dashboard_id": "...", "dashboard": {...} }
    """
    try:
        data = request.json
        dashboard_id = data.get('dashboard_id')
        dashboard = data.get('dashboard', {})
        if not dashboard_id:
            return jsonify({"error": "Missing dashboard_id"}), 400
        # Ensure the dashboard has a 'name' field for display
        if 'name' not in dashboard:
            dashboard['name'] = dashboard_id
        # Save form_id, form_name, and source_id if provided
        form_id = dashboard.get('form_id') or dashboard.get('selectedFormKey')
        form_name = dashboard.get('form_name')
        source_id = dashboard.get('source_id') or form_id
        if form_id:
            dashboard['form_id'] = form_id
        if form_name:
            dashboard['form_name'] = form_name
        if source_id:
            dashboard['source_id'] = source_id
        key = f'sultan/dashboards/{dashboard_id}.json'
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(dashboard, ensure_ascii=False),
            ContentType='application/json'
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/sultan/dashboards')
def dashboards_list():
    return render_template('sultan/dashboards/index.html')


@app.route('/api/sultan/dashboards/list')
def api_sultan_dashboards_list():
    """
    List all dashboards in sultan/dashboards/
    """
    dashboards = []
    prefix = 'sultan/dashboards/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue
            try:
                content = s3.get_object(Bucket=BUCKET_NAME, Key=key)['Body'].read().decode('utf-8')
                dashboard = json.loads(content)
                dashboards.append(dashboard)
            except Exception as e:
                logger.error(f"Failed to load dashboard {key}: {e}")
    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(dashboards)


@app.route('/api/sultan/emailgroups/list')
def api_emailgroups_list():
    emailgroups = []
    prefix = 'sultan/emailgroups/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                emailgroup = json.loads(content)
                emailgroups.append(emailgroup)
            except Exception as e:
                logger.error(f"Failed to load emailgroup {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list emailgroups: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(emailgroups)


@app.route('/api/sultan/sites/list')
def api_sites_list():
    sites = []
    prefix = 'sultan/sites/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                site = json.loads(content)
                sites.append(site)
            except Exception as e:
                logger.error(f"Failed to load site {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list sites: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(sites)


@app.route('/api/sultan/escalation/list')
def api_escalation_list():
    escalation_names = []
    prefix = 'sultan/escalations/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                key = obj['Key']
                name = key.split('/')[-1]  # Extract the file name
                escalation_names.append(name)
            except Exception as e:
                logger.error(f"Failed to process escalation {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(escalation_names)


@app.route('/api/sultan/escalation/save', methods=['POST'])
def api_escalation_save():
    try:
        data = request.json

        # If data is a dict with 'id' and 'escalations'
        if isinstance(data, dict):
            escalation_id = data.get('id')
            escalations = data.get('escalations')
        # If data is a list (legacy or direct save)
        elif isinstance(data, list):
            escalations = data
            escalation_id = request.args.get('id')
        else:
            return jsonify({"error": "Invalid payload"}), 400

        # Accept empty list as valid
        if not escalation_id or not isinstance(escalations, list):
            return jsonify({"error": "Missing escalation ID or escalations array"}), 400

        key = f"sultan/escalations/{escalation_id}.json"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(escalations, ensure_ascii=False),
            ContentType='application/json'
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save escalation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/escalation/<escalation_id>')
def api_escalation_get(escalation_id):
    key = f"sultan/escalations/{escalation_id}.json"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load escalation {escalation_id}: {e}")
        return jsonify({"error": str(e)}), 404


@app.route('/api/sultan/forms', methods=['GET'])
def api_sultan_forms():
    status = request.args.get('status', 'Draft')
    forms = []  # Replace with actual logic to fetch forms based on status
    try:
        # Example logic to fetch forms
        prefix = f'sultan/forms/'
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                form = json.loads(response['Body'].read().decode('utf-8'))
                forms.append(form)
            except Exception as e:
                logger.error(f"Failed to load form {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(forms)


@app.route('/api/sultan/forms/<form_id>', methods=['GET'])
def api_sultan_form_by_id(form_id):
    """
    Fetch a specific form by its ID, regardless of its status.
    """
    try:
        key = f'sultan/forms/{form_id}.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        form = json.loads(response['Body'].read().decode('utf-8'))
        return jsonify(form)
    except s3.exceptions.NoSuchKey:
        return jsonify({"error": "Form not found"}), 404
    except Exception as e:
        logger.error(f"Failed to fetch form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/forms/save', methods=['POST'])
def api_sultan_save_form():
    data = request.json
    form = data.get('form')
    status = data.get('status', 'Draft')
    if not form:
        return jsonify({"error": "Invalid form data"}), 400
    key = f'sultan/forms/{form["id"]}.json'
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(form))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/forms/delete/<form_id>', methods=['DELETE'])
def api_sultan_delete_form(form_id):
    status = request.args.get('status', 'Draft')
    key = f'sultan/forms/{status}/{form_id}.json'
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete form: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/forms/list')  # Keep old route for backward compatibility
def api_forms_list():
    forms = []
    prefix = 'sultan/forms/'

    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                form = json.loads(content)

                # Add last_modified if not present
                metadata = s3.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                if 'last_modified' not in form:
                    form['last_modified'] = metadata['LastModified']

                forms.append(form)
            except Exception as e:
                logger.error(f"Failed to load form {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify(forms)


@app.route('/api/sultan/templates/<template_id>')
def api_template_get(template_id):
    try:
        if template_id.endswith('.json'):
            key = f'sultan/templates/{template_id}'
        else:
            key = f'sultan/templates/{template_id}.json'

        content = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load template {template_id}: {e}")
        return jsonify({
            "error": "Template not found",
            "redirect": "/sultan/templates/list"
        }), 404


@app.route('/api/sultan/templates/delete/<template_id>', methods=['POST'])
def api_template_delete(template_id):
    """
    Move a template to the 'sultan/templates/delete/' folder in S3.
    """
    try:
        # Define the source and destination keys
        source_key = f'sultan/templates/{template_id}.json'
        destination_key = f'sultan/templates/delete/{template_id}.json'

        # Copy the object to the 'delete' folder
        s3.copy_object(
            Bucket=BUCKET_NAME,
            CopySource={'Bucket': BUCKET_NAME, 'Key': source_key},
            Key=destination_key
        )

        # Delete the original template
        s3.delete_object(Bucket=BUCKET_NAME, Key=source_key)

        return jsonify({"status": "success", "message": f"Template {template_id} moved to delete folder"}), 200
    except Exception as e:
        logger.error(f"Failed to move template {template_id} to delete folder: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/templates/save', methods=['POST'])
def api_template_save():
    data = request.json
    template = data.get('template')

    if not template:
        return jsonify({"error": "Template required"}), 400

    try:
        # Add author and email from the current user
        template['author'] = data.get('author', 'system')
        template['email'] = data.get('email', 'system')

        # Wrap the template in an array
        template_array = [template]

        template_path = f'sultan/templates/{template["id"]}.json'

        save_in_global_db(template_path, template_array)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save template: {e}")
        return jsonify({"error": "Failed to save template"}), 500


@app.route('/api/sultan/templates/duplicate', methods=['POST'])
def api_template_duplicate():
    data = request.json
    template_id = data.get('id')

    try:
        # Get original template
        template = get_one_from_global_db(f'sultan/templates/{template_id}.json')
        new_template = template.copy()
        new_template['id'] = f'templates-{str(uuid.uuid4())}'
        new_template['name'] = f'{template["name"]} (Copy)'

        # Save new template
        save_in_global_db(f'sultan/templates/{new_template["id"]}.json', new_template)

        return jsonify(new_template)
    except Exception as e:
        logger.error(f"Failed to duplicate template: {e}")
        return jsonify({"error": "Failed to duplicate template"}), 500


@app.route('/api/sultan/templates', methods=['GET'])
def api_templates_list():
    """
    Fetch the list of templates from the S3 bucket.
    """
    templates = []
    prefix = 'sultan/templates/'

    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                template = json.loads(content)
                templates.append(template)
            except Exception as e:
                logger.error(f"Failed to load template {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify(templates)


@app.route('/api/pc-analytics-jaffar-svc/search')
def api_pc_analytics_jaffar_svc_search():
    """
    Search issues by description (case-insensitive substring match).
    Example: /api/pc-analytics-jaffar-svc/search?query=Flow%20Credit&limit=10
    """
    query = request.args.get('query', '').strip()
    limit = int(request.args.get('limit', 10))
    results = []

    if not query:
        return jsonify([])

    try:
        # Search in all statuses
        for status in ['draft', 'new', 'open', 'failed', 'submitted']:
            prefix = f'jaffar/issues/{status}/'
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            for obj in response.get('Contents', []):
                try:
                    issue_obj = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                    issue = json.loads(issue_obj['Body'].read().decode('utf-8'))
                    desc = issue.get('issue-description', '')
                    if query.lower() in desc.lower():
                        results.append(issue)
                        if len(results) >= limit:
                            return jsonify(results)
                except Exception:
                    continue
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in search route: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/sultan/save/dashboard', methods=['POST'])
def sultan_save_dashboard():
    """
    Save a dashboard configuration to S3 in config/dashboards/{dashboard_id}.json
    Expects JSON: { "dashboard": { ... }, "dashboard_id": "..." }
    """
    try:
        data = request.json
        dashboard = data.get('dashboard')
        dashboard_id = data.get('dashboard_id') or (dashboard and dashboard.get('id'))
        if not dashboard or not dashboard_id:
            return jsonify({"error": "Missing dashboard or dashboard_id"}), 400
        # Save form_id, form_name, source_id, and configFilters if present
        form_id = dashboard.get('form_id') or dashboard.get('selectedFormKey')
        form_name = dashboard.get('form_name')
        source_id = dashboard.get('source_id') or form_id
        config_filters = dashboard.get('configFilters', {})  # Save configFilters
        if form_id:
            dashboard['form_id'] = form_id
        if form_name:
            dashboard['form_name'] = form_name
        if source_id:
            dashboard['source_id'] = source_id
        if config_filters:
            dashboard['configFilters'] = config_filters
        key = f'sultan/dashboards/{dashboard_id}.json'
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(dashboard, ensure_ascii=False),
            ContentType='application/json'
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/dashboard/<dashboard_id>', methods=['GET'])
def api_jaffar_dashboard_get(dashboard_id):
    """
    Get a dashboard config from S3 (jaffar/config/{dashboard_id}.json)
    """
    key = f'jaffar/config/{dashboard_id}.json'
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        dashboard = json.loads(response['Body'].read().decode('utf-8'))
        return jsonify(dashboard)
    except s3.exceptions.NoSuchKey:
        return jsonify({"error": "Dashboard not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get dashboard {dashboard_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/pouchdb/init', methods=['POST'])
def initialize_pouchdb():
    """
    Initialize PouchDB data by fetching all issues and sending them in bulk, using parallelism.
    """
    try:
        page_size = int(10000000)
        all_keys = []
        for status in ['draft', 'new', 'open', 'failed', 'submitted', 'closed']:
            prefix = f'jaffar/issues/{status}/'
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            for obj in response.get('Contents', []):
                all_keys.append(obj['Key'])

        def fetch_issue(key):
            try:
                issue_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                return json.loads(issue_obj['Body'].read().decode('utf-8'))
            except Exception as e:
                logger.error(f"Failed to load issue {key}: {e}")
                return None

        all_issues = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_issue, key): key for key in all_keys}
            for future in as_completed(futures):
                issue = future.result()
                if issue is not None:
                    all_issues.append(issue)

        # Split issues into chunks for parallel processing
        chunks = [all_issues[i:i + page_size] for i in range(0, len(all_issues), page_size)]
        return jsonify({"status": "success", "chunks": chunks}), 200
    except Exception as e:
        logger.error(f"Error initializing PouchDB: {e}")
        return jsonify({"error": str(e)}), 500


def save_in_global_db(key, data):
    """
    Save data to S3. Supports both JSON and YAML formats.
    """
    try:
        if key.endswith('.yml'):
            content_type = 'application/x-yaml'
        else:
            content_type = 'application/json'
            data = json.dumps(data, ensure_ascii=False)

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=data.encode('utf-8'),
            ContentType=content_type
        )
        logger.info(f"Successfully saved data to {key}")
    except Exception as e:
        logger.error(f"Failed to save data to {key}: {e}")
        raise


# Register the forms blueprint
app.register_blueprint(forms_blueprint)

# Register the sultan blueprint
app.register_blueprint(sultan_blueprint)

app.register_blueprint(clones_blueprint)

# Register the flows blueprint
app.register_blueprint(flows_bp)