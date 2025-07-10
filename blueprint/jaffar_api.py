
from flask import Blueprint, jsonify, request
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

# Create Jaffar API blueprint with prefix
jaffar_api_blueprint = Blueprint('jaffar_api', __name__, url_prefix='/pc-analytics-jaffar/api/jaffar')

# Initialize a thread pool executor for handling email tasks
email_executor = ThreadPoolExecutor(max_workers=5)

@jaffar_api_blueprint.route('/templates/list')
def api_jaffar_templates_list():
    templates = []
    prefix = 'jaffar/configs/templates-'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                content = s3.get_object(
                    Bucket=BUCKET_NAME,
                    Key=obj['Key'])['Body'].read().decode('utf-8')
                # On suppose que chaque fichier est un objet ou un tableau d'un objet
                data = json.loads(content)
                if isinstance(data, list):
                    for t in data:
                        if 'id' in t and 'name' in t:
                            templates.append({
                                'id': t['id'],
                                'name': t['name']
                            })
                elif isinstance(data,
                                dict) and 'id' in data and 'name' in data:
                    templates.append({'id': data['id'], 'name': data['name']})
            except Exception as e:
                logger.error(f"Failed to load template {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(templates)

@jaffar_api_blueprint.route('/config')
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

@jaffar_api_blueprint.route('/issues/list', methods=['GET'])
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
                response = s3.list_objects_v2(Bucket=BUCKET_NAME,
                                              Prefix=prefix)
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
                response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
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

@jaffar_api_blueprint.route('/issues/list2', methods=['GET'])
def list_issues_v2():
    """
    Version améliorée : pagination, filtrage et tri côté serveur.
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
        filters = {
            k[7:]: v
            for k, v in request.args.items() if k.startswith('filter_') and v
        }

        all_keys = []
        for status in ['draft', 'new', 'open', 'failed']:
            prefix = f'jaffar/issues/{status}/'
            try:
                response = s3.list_objects_v2(Bucket=BUCKET_NAME,
                                              Prefix=prefix)
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
                response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
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
            issues = [
                iss for iss in issues
                if val.lower() in str(iss.get(col, '')).lower()
            ]

        # Tri par colonne si demandé
        if sort_col:
            issues.sort(
                key=lambda x: (x.get(sort_col) or '').lower()
                if isinstance(x.get(sort_col), str) else x.get(sort_col),
                reverse=(sort_dir == 'desc'))

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

@jaffar_api_blueprint.route('/issues/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    for status in ['draft', 'new', 'open', 'failed', 'closed']:
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

@jaffar_api_blueprint.route('/issues/<issue_id>/changes', methods=['GET'])
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

@jaffar_api_blueprint.route('/issues/<issue_id>/comments', methods=['POST'])
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
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=changes_key,
                      Body=json_data.encode('utf-8'))

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save comment: {e}")
        return jsonify({"error": str(e)}), 500

@jaffar_api_blueprint.route('/submit', methods=['POST'])
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

        return jsonify({
            'status': 'success',
            'redirect': f'/pc-analytics-jaffar/issue/{issue_id}',
            'message': 'Submitted!'
        })

    except Exception as e:
        logger.error(f"Failed to submit issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500

@jaffar_api_blueprint.route('/save', methods=['POST'])
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

@jaffar_api_blueprint.route('/acknowledge', methods=['POST'])
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
                'author':
                author,
                'date':
                datetime.datetime.now().isoformat()
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

@jaffar_api_blueprint.route('/issues/<issue_id>/delete', methods=['POST'])
def move_draft_to_deleted(issue_id):
    """
    Move a draft issue to the 'issues/delete' folder in S3.
    """
    try:
        # Define the source and destination keys
        source_key = f'jaffar/issues/draft/{issue_id}.json'
        destination_key = f'jaffar/issues/delete/{issue_id}.json'

        # Copy the object to the 'delete' folder
        s3.copy_object(Bucket=BUCKET_NAME,
                       CopySource={
                           'Bucket': BUCKET_NAME,
                           'Key': source_key
                       },
                       Key=destination_key)

        # Delete the original draft
        s3.delete_object(Bucket=BUCKET_NAME, Key=source_key)

        return jsonify({
            'status': 'success',
            'message': f'Draft {issue_id} moved to delete folder'
        }), 200
    except Exception as e:
        logger.error(f"Failed to move draft {issue_id} to delete folder: {e}")
        return jsonify({'error': str(e)}), 500

@jaffar_api_blueprint.route('/similarity-search', methods=['POST'])
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
        logger.info(
            f"Constructed payload for similarity search API: {payload}")

        response = requests.post(
            "https://palms-jaffar-similaritysearch-api-uat.ikp102s.cloud.uk.hsbc/similarity",
            json=payload)

        logger.info(
            f"Similarity search API response status: {response.status_code}")
        logger.info(f"Similarity search API response body: {response.text}")

        if response.status_code != 200:
            logger.error(
                f"Similarity search API failed with status {response.status_code}"
            )
            return jsonify({"error": "Failed to fetch similar issues"
                            }), response.status_code

        return jsonify(response.json()), 200
    except Exception as e:
        logger.error(f"Error in similarity search: {e}", exc_info=True)
        return jsonify(
            {"error":
             "An error occurred while searching for similar issues"}), 500

@jaffar_api_blueprint.route('/feedback/list')
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

@jaffar_api_blueprint.route('/feedback/submit', methods=['POST'])
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

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"error": str(e)}), 500

@jaffar_api_blueprint.route('/feedback/vote', methods=['POST'])
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

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error voting on feedback: {e}")
        return jsonify({"error": str(e)}), 500

@jaffar_api_blueprint.route('/feedback/comment', methods=['POST'])
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
                    'id':
                    f"COMMENT-{int(datetime.datetime.now().timestamp() * 1000)}",
                    'text': data['text'],
                    'author': data.get('author', ''),
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

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(ideas, ensure_ascii=False))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return jsonify({"error": str(e)}), 500

@jaffar_api_blueprint.route('/grid-views/save', methods=['POST'])
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

@jaffar_api_blueprint.route('/grid-views/list')
def list_grid_views():
    user = request.args.get('user', 'anonymous')
    prefix = f'jaffar/grid-views/{user}/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        views = []
        for obj in response.get('Contents', []):
            name = obj['Key'].split('/')[-1].replace('.json', '')
            views.append(name)
        return jsonify(views)
    except Exception as e:
        return jsonify([])

@jaffar_api_blueprint.route('/grid-views/get')
def get_grid_view():
    user = request.args.get('user', 'anonymous')
    name = request.args.get('name')
    key = f'jaffar/grid-views/{user}/{name}.json'
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return jsonify(json.loads(obj['Body'].read().decode('utf-8')))
    except Exception:
        return jsonify({}), 404

@jaffar_api_blueprint.route('/escalation/send', methods=['POST'])
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

@jaffar_api_blueprint.route('/issues/<issue_id>/escalation', methods=['POST'])
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

                issue['escalation'].append({'user': user, 'date': date})
                logger.info(f"Issue escalation data: {issue}")
                logger.info(f"Issue located: {key}")

                s3.put_object(Bucket=BUCKET_NAME,
                              Key=key,
                              Body=json.dumps(issue, ensure_ascii=False),
                              ContentType='application/json')
                return jsonify({'status': 'success'})
            except s3.exceptions.NoSuchKey:
                continue
        return jsonify({'error': 'Issue not found'}), 404
    except Exception as e:
        logger.error(f"Failed to save escalation for issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500

@jaffar_api_blueprint.route('/issues/<issue_id>/close', methods=['POST'])
def close_issue(issue_id):
    """
    Close the issue, log the event in the changes file,
    """
    data = request.json
    reason = data.get('reason', '').strip()
    closed_by = data.get('closed_by', 'system')

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
        "author": closed_by
    }
    save_issue_changes(issue_id, close_event)

    # Move issue to 'closed' folder
    closed_key = f'jaffar/issues/closed/{issue_id}.json'
    s3.put_object(Bucket=BUCKET_NAME,
                  Key=closed_key,
                  Body=json.dumps(issue_data, ensure_ascii=False),
                  ContentType='application/json')

    # Delete the original issue
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)

    return jsonify({
        'status': 'success',
        'message': f'Issue {issue_id} closed successfully'
    }), 200

# Helper functions
def validate_save_request(data):
    if not data or 'id' not in data:
        logger.error("Missing required data in save request")
        return False
    return True

def get_issue_data(issue_id):
    """
    Récupère les données de l'issue depuis S3.
    """
    try:
        for folder in ['new', 'draft', 'open']:
            key = f'jaffar/issues/{folder}/{issue_id}.json'
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                issue_data = json.loads(
                    response['Body'].read().decode('utf-8'))
                if folder == 'draft':
                    issue_data['status'] = 'submitted'
                    issue_data['submitted_at'] = datetime.datetime.now(
                    ).isoformat()
                    issue_data['version'] = 0
                    delete(key)  # Supprimer le brouillon après récupération
                return issue_data
            except s3.exceptions.NoSuchKey:
                continue
        raise s3.exceptions.NoSuchKey(
            f"Issue {issue_id} not found in any folder")
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
    email_address = issue_data.get('author', 'system').rsplit(' - ',
                                                              1)[-1].strip()
    sendConfirmationEmail(email_address,
                          f"Issue Submitted: {issue_data['id']}", issue_data)

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

def save_issue_changes(issue_id, changes):
    """
    Saves the issue changes as a JSON file in S3.
    """
    try:
        changes_key = f'jaffar/issues/changes/{issue_id}-changes.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=changes_key)
            existing_changes = json.loads(
                response['Body'].read().decode('utf-8'))
            if not isinstance(existing_changes, list):
                existing_changes = [existing_changes]
        except s3.exceptions.NoSuchKey:
            existing_changes = []

        if isinstance(changes, list):
            existing_changes.extend(changes)
        else:
            existing_changes.append(changes)

        json_data = json.dumps(existing_changes, ensure_ascii=False)
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=changes_key,
                      Body=json_data.encode('utf-8'),
                      ContentType='application/json')
        logger.info(f"Changes for issue {issue_id} saved to {changes_key}")
    except Exception as e:
        logger.error(f"Failed to save changes for issue {issue_id}: {e}")
        raise

def send_escalation_email(recipients, subject, message, issue_id):
    """
    Envoie un email d'escalade à la liste de destinataires + l'adresse globale.
    """
    # Nettoie et split les emails
    recipient_list = [
        email.strip() for email in recipients.split(',') if email.strip()
    ]
    # Ajoute le destinataire obligatoire
    if "global.control.remediation.programme@noexternalmail.hsbc.com" not in recipient_list:
        recipient_list.append(
            "global.control.remediation.programme@noexternalmail.hsbc.com")
    # Optionnel : Ajoute un lien vers l'issue si issue_id fourni
    if issue_id:
        issue_link = f"<br><br><a href='/pc-analytics-jaffar/issue/{issue_id}'>View Issue {issue_id}</a>"
        message += issue_link
    email = Email(
        to=recipient_list,
        subject=subject,
        content=message,
    )
    email.send()

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

def send_confirmation_if_needed(data):
    """
    Helper function to send confirmation emails if needed
    """
    pass  # Implementation needed based on your requirements

def sendConfirmationEmail(email_address: str, subject: str, issue: dict) -> bool:
    """
    Send the confirmation email to the author email address.
    """
    logger.info(f"Sending email to {email_address}")
    # Implementation based on your existing email service
    pass
