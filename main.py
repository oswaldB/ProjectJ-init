from flask import Flask, Blueprint, render_template, redirect, request, jsonify
import json
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor
from blueprint.workflow import workflow_bp
from config import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, CircularRefEncoder
from services.db_service import (
    get_max_from_global_db, save_in_global_db, delete, load_from_global_db,
    list_issues, get_issue, save_issue, save_issue_changes, get_issue_changes,
    list_sultan_objects, get_sultan_object, save_sultan_object, delete_sultan_object,
    get_feedback_list, save_feedback_list, object_exists
)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.register_blueprint(workflow_bp)
logger = logging.getLogger(__name__)
email_executor = ThreadPoolExecutor(max_workers=2)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Email Service Functions
def send_confirmation_if_needed(issue_data):
    try:
        logger.info(
            f"Processing confirmation email for issue: {issue_data.get('id', 'unknown')}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        return False

# Jaffar Routes
def validate_save_request(data):
    if not data or 'id' not in data:
        logger.error("Missing required data in save request")
        return False
    return True


# Jaffar Routes
@app.route('/tutorial')
def tutorial():
    return render_template('jaffar/tutorial.html')

@app.route('/')
def index():
    return render_template('jaffar/index.html')

@app.route('/grid')
def grid():
    return render_template('jaffar/grid.html')


@app.route('/edit')
def edit():
    return render_template('jaffar/edit.html')


@app.route('/acknowledge')
def acknowledge():
    return render_template('jaffar/acknowledge.html')


@app.route('/new-issue')
def new_issue():
    now = datetime.datetime.now()
    issue_id = f'JAFF-ISS-{int(now.timestamp() * 1000)}'

    issue_data = {
        'id': issue_id,
        'author': 'oswald.bernard@gmail.com',
        'status': 'draft',
        'created_at': now.isoformat(),
        'updated_at': now.isoformat()
    }

    save_issue_to_storage(issue_id, 'draft', issue_data)
    return redirect(f'/edit/{issue_id}')


@app.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')


@app.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')


@app.route('/api/jaffar/config')
def api_jaffar_config():
    try:
        config = get_max_from_global_db('jaffar/configs/2-jaffarConfig.json')
        if not config:
            logger.error("No config found")
            return jsonify({"error": "Config not found"}), 404
        return jsonify(config)
    except Exception as e:
        logger.error(f"Failed to load Jaffar config: {e}")
        return jsonify({"error": "Config not found"}), 404


@app.route('/api/jaffar/issues/list', methods=['GET'])
def api_list_issues():
    try:
        issues = list_issues()
        return jsonify(issues)
    except Exception as e:
        logger.error(f"Error in list_issues: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/issues/<issue_id>', methods=['GET'])
def api_get_issue(issue_id):
    try:
        issue = get_issue(issue_id)
        if issue:
            return jsonify(issue)
        return jsonify({'error': 'Issue not found'}), 404
    except Exception as e:
        logger.error(f"Error getting issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/jaffar/issues/<issue_id>/changes', methods=['GET'])
def api_get_issue_changes(issue_id):
    try:
        changes = get_issue_changes(issue_id)
        return jsonify(changes)
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

        # Save locally
        local_path = os.path.join(LOCAL_BUCKET_DIR, changes_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(json_data)

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
        # Check if issue exists in new status
        new_key = f'jaffar/issues/new/{issue_id}.json'
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=new_key)
            issue_data = json.loads(response['Body'].read().decode('utf-8'))
            # Update version if exists
            current_version = issue_data.get('version', 0)
            issue_data['version'] = current_version + 1
            issue_data['updated_at'] = datetime.datetime.now().isoformat()
        except:
            # Get from draft if not in new
            draft_key = f'jaffar/issues/draft/{issue_id}.json'
            response = s3.get_object(Bucket=BUCKET_NAME, Key=draft_key)
            issue_data = json.loads(response['Body'].read().decode('utf-8'))
            issue_data['status'] = 'submitted'
            issue_data['submitted_at'] = datetime.datetime.now().isoformat()
            issue_data['version'] = 1
            issue_data['author'] = 'oswald.bernard@gmail.com'
            delete(draft_key)

        # Save to new folder
        save_issue_to_storage(issue_id, 'new', issue_data)

        # Log system activity
        activity = {
            "type": "system",
            "content": f"Issue submitted (version {issue_data['version']})",
            "timestamp": datetime.datetime.now().isoformat(),
            "author": issue_data.get('author', 'system')
        }
        save_issue_changes(issue_id, activity)

        # Send confirmation email
        email_executor.submit(send_confirmation_if_needed, issue_data)

        return jsonify({
            'status': 'success',
            'redirect': f'/issue/{issue_id}',
            'message': 'Submitted!'
        })

    except Exception as e:
        logger.error(f"Failed to submit issue {issue_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/jaffar/save', methods=['POST'])
def api_save_issue():
    try:
        data = request.json
        if not validate_save_request(data):
            return jsonify({"error": "Invalid request data"}), 400

        issue_id = data.get('id')
        status = data.get('status', 'draft')

        # Extract changes before saving issue
        changes = data.pop('changes', None)

        # Check if this is a first save
        is_new_issue = not object_exists(f'jaffar/issues/draft/{issue_id}.json') and not object_exists(f'jaffar/issues/new/{issue_id}.json')

        # Save the issue without changes
        if save_issue(issue_id, status, data):
            # Track changes if any exist
            if changes:
                save_issue_changes(issue_id, changes)

            # Add creation activity for new issues
            if is_new_issue:
                activity = {
                    "type": "system",
                    "content": "Issue created",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "author": data.get('author', 'system')
                }
                save_issue_changes(issue_id, activity)

            # Send confirmation email for new issues
            if status == 'new':
                email_executor.submit(send_confirmation_if_needed, data)

            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Failed to save issue"}), 500
    except Exception as e:
        logger.error(f"Error saving issue: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/feedback/list')
def api_list_feedback():
    try:
        ideas = get_feedback_list()
        return jsonify(ideas)
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/feedback/submit', methods=['POST'])
def api_submit_feedback():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Missing text"}), 400

        ideas = get_feedback_list()
        new_idea = {
            'id': f'IDEA-{int(datetime.datetime.now().timestamp() * 1000)}',
            'text': data['text'],
            'description': data.get('description', ''),
            'author': 'oswald.bernard@gmail.com',
            'date': datetime.datetime.now().isoformat(),
            'votes': 0
        }
        ideas.append(new_idea)

        if save_feedback_list(ideas):
            return jsonify({"status": "success"})
        return jsonify({"error": "Failed to save feedback"}), 500
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
                    'author': 'oswald.bernard@gmail.com',
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
    return render_template('jaffar/feedback.html')

@app.route('/api/jaffar/acknowledge', methods=['POST'])
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
                'email':
                email,
                'date':
                datetime.datetime.now().isoformat()
            })

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


# Sultan Routes
@app.route('/sultan/')
def sultan_index():
    return render_template('sultan/base.html')


@app.route('/sultan/forms')
def forms_list():
    return render_template('sultan/forms/index.html')


@app.route('/sultan/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')


@app.route('/sultan/escalation')
def escalation_list():
    return redirect('/sultan/escalation/edit/new')


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
    return render_template('sultan/templates/edit.html')


@app.route('/sultan/workflows')
def workflows_list():
    return render_template('sultan/workflows/index.html')


@app.route('/sultan/workflows/edit/<workflow_id>')
def workflow_edit(workflow_id):
    return render_template('sultan/workflows/edit.html')


@app.route('/api/sultan/emailgroups/list')
def api_emailgroups_list():
    try:
        emailgroups = list_sultan_objects('emailgroups')
        return jsonify(emailgroups)
    except Exception as e:
        logger.error(f"Failed to list emailgroups: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sultan/sites/list')
def api_sites_list():
    try:
        sites = list_sultan_objects('sites')
        return jsonify(sites)
    except Exception as e:
        logger.error(f"Failed to list sites: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sultan/escalation/list')
def api_escalation_list():
    try:
        escalations = list_sultan_objects('escalations')
        return jsonify(escalations)
    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sultan/forms/list')
def api_forms_list():
    try:
        forms = list_sultan_objects('forms')
        return jsonify(forms)
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sultan/forms/<form_id>')
def api_form_get(form_id):
    try:
        form = get_sultan_object('forms', form_id)
        if form:
            return jsonify(form)
        return jsonify({'error': 'Form not found'}), 404
    except Exception as e:
        logger.error(f"Error getting form {form_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sultan/templates')
def api_templates_list():
    try:
        templates = list_sultan_objects('templates')
        return jsonify(templates)
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/templates/save', methods=['POST'])
def api_templates_save():
    try:
        data = request.json
        template = data.get('template')

        if not template or 'id' not in template:
            return jsonify({"error": "Invalid template data"}), 400

        template['last_modified'] = datetime.datetime.now().isoformat()
        template['user_email'] = 'oswald.bernard@gmail.com'

        key = f'sultan/templates/{template["id"]}.json'
        save_in_global_db(key, template)

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save template: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/templates/delete/<template_id>', methods=['DELETE'])
def api_templates_delete(template_id):
    try:
        key = f'sultan/templates/{template_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        return jsonify({"error": str(e)}), 500@app.route('/api/sultan/templates/duplicate', methods=['POST'])
def api_templates_duplicate():
    try:
        data = request.json
        original_id = data.get('id')

        if not original_id:
            return jsonify({"error": "Missing template ID"}), 400

        # Get original template
        original_key = f'sultan/templates/{original_id}.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=original_key)
        original_template = json.loads(response['Body'].read().decode('utf-8'))

        # Create duplicate with new ID
        new_id = f'templates-{int(datetime.datetime.now().timestamp() * 1000)}'
        new_template = original_template.copy()
        new_template['id'] = new_id
        new_template['name'] = f"{original_template.get('name', 'Template')} (Copy)"
        new_template['status'] = 'draft'
        new_template['last_modified'] = datetime.datetime.now().isoformat()
        new_template['user_email'] = 'oswald.bernard@gmail.com'

        # Save duplicate
        new_key = f'sultan/templates/{new_id}.json'
        save_in_global_db(new_key, new_template)

        return jsonify(new_template)
    except Exception as e:
        logger.error(f"Failed to duplicate template: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/workflows/list')
def api_workflows_list():
    workflows = []
    prefix = 'sultan/workflows/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                workflow_data = json.loads(content)

                # Handle backward compatibility
                if 'workflows' in workflow_data and workflow_data['workflows']:
                    # Old format - extract workflows and add metadata
                    for old_workflow in workflow_data['workflows']:
                        old_workflow['last_modified'] = workflow_data.get('last_modified', '')
                        old_workflow['user_email'] = workflow_data.get('user_email', '')
                        workflows.append(old_workflow)
                else:
                    # New format - add directly
                    workflows.append(workflow_data)
            except Exception as e:
                logger.error(f"Failed to load workflow {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(workflows)


@app.route('/api/sultan/workflows/<workflow_id>')
def api_workflow_get(workflow_id):
    try:
        # If workflow_id is 'new', create a new empty workflow
        if workflow_id == 'new':
            timestamp = int(datetime.datetime.now().timestamp() * 1000)
            new_workflow_id = f'workflows-{timestamp}'

            # Create empty workflow structure with ID at root level
            workflow_data = {
                'id': new_workflow_id,
                'name': 'New Workflow',
                'description': '',
                'last_modified': datetime.datetime.now().isoformat(),
                'user_email': 'oswald.bernard@gmail.com',
                'blocks': [{
                    'id': f'block-{timestamp}',
                    'type': 'trigger',
                    'position': {'x': 100, 'y': 100},
                    'formId': '',
                    'event': 'on_submit'
                }]
            }

            # Save to S3
            key = f'sultan/workflows/{new_workflow_id}.json'
            save_in_global_db(key, workflow_data)

            return jsonify(workflow_data)

        # Regular workflow loading
        key = f'sultan/workflows/{workflow_id}.json'
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        workflow_data = json.loads(response['Body'].read().decode('utf-8'))

        # Handle backward compatibility with old format
        if 'workflows' in workflow_data and workflow_data['workflows']:
            # Old format - extract first workflow and add metadata
            old_workflow = workflow_data['workflows'][0]
            old_workflow['last_modified'] = workflow_data.get('last_modified', '')
            old_workflow['user_email'] = workflow_data.get('user_email', '')
            return jsonify(old_workflow)

        # New format - return as is
        return jsonify(workflow_data)
    except s3.exceptions.NoSuchKey:
        return jsonify({'error': 'Workflow not found'}), 404
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/workflows/save', methods=['POST'])
def api_workflows_save():
    try:
        data = request.json

        if not data:
            return jsonify({"error": "Invalid workflow data"}), 400

        # Use the workflow ID for the filename, or generate new timestamp
        workflow_id = data.get('id', f'workflows-{int(datetime.datetime.now().timestamp() * 1000)}')
        key = f'sultan/workflows/{workflow_id}.json'

        # Add metadata directly to workflow data
        data['last_modified'] = datetime.datetime.now().isoformat()
        data['user_email'] = 'oswald.bernard@gmail.com'
        data['id'] = workflow_id

        workflow_data = data

        save_in_global_db(key, workflow_data)

        return jsonify({"status": "success", "key": key})
    except Exception as e:
        logger.error(f"Failed to save workflows: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sultan/workflows/delete/<workflow_id>', methods=['DELETE'])
def api_workflows_delete(workflow_id):
    try:
        key = f'sultan/workflows/{workflow_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return jsonify({"error": str(e)}), 500

# Dashboard Blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/sultan/dashboard')

@dashboard_bp.route('/')
def dashboard_index():
    return render_template('sultan/dashboards/index.html')

@dashboard_bp.route('/edit/<dashboard_id>')
def dashboard_edit(dashboard_id):
    return render_template('sultan/dashboards/edit.html')

# Register blueprints
app.register_blueprint(dashboard_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)