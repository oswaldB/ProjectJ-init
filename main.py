from flask import Flask, Blueprint, render_template, redirect, request, jsonify
import json
import logging
import boto3
from moto import mock_aws
import os
import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
logger = logging.getLogger(__name__)
email_executor = ThreadPoolExecutor(max_workers=2)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Local storage configuration
LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"
os.makedirs(LOCAL_BUCKET_DIR, exist_ok=True)


# Initialize mocked AWS
def restore_local_to_s3():
    for root, _, files in os.walk(LOCAL_BUCKET_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            s3_key = os.path.relpath(local_path, LOCAL_BUCKET_DIR)
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
                try:
                    s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=content)
                except Exception as e:
                    logger.error(f"Failed to restore {s3_key} to S3: {e}")


mock = mock_aws()
mock.start()

# Create S3 client and bucket
s3 = boto3.client('s3', region_name='us-east-1')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
except:
    pass

restore_local_to_s3()


class CircularRefEncoder(json.JSONEncoder):

    def default(self, obj):
        try:
            return super().default(obj)
        except:
            return str(obj)


# Database Service Functions
def get_max_from_global_db(prefix):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        if 'Contents' in response:
            max_value = max(response['Contents'],
                            key=lambda x: x['LastModified'])
            response = s3.get_object(Bucket=BUCKET_NAME, Key=max_value['Key'])
            return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to get max from DB: {e}")
        return None


def save_in_global_db(key, obj):
    json_object = json.dumps(obj,
                             separators=(',', ':'),
                             cls=CircularRefEncoder)
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
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    full_path = os.path.join(LOCAL_BUCKET_DIR, key)
    if os.path.exists(full_path):
        os.remove(full_path)


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


def get_max_filename_from_global_db(suffix):
    prefix = 'jaffar/configs/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        max_num = 0
        max_key = None
        
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].endswith(suffix):
                    num = int(obj['Key'].split('/')[-1].split('-')[0])
                    if num > max_num:
                        max_num = num
                        max_key = obj['Key']
        return max_key
    except Exception as e:
        logger.error(f"Failed to get max filename: {e}")
        return None

def save_issue_to_storage(issue_id, status, data):
    logger.info(f"Entering save_issue_to_storage for issue {issue_id}")
    
    # Check if issue already exists in 'new' status
    new_key = f'jaffar/issues/new/{issue_id}.json'
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=new_key)
        if status == 'draft':
            # If issue exists in 'new', update it there instead of creating draft
            key = new_key
        else:
            key = f'jaffar/issues/{status}/{issue_id}.json'
    except:
        key = f'jaffar/issues/{status}/{issue_id}.json'
    
    logger.info(f"Generated storage key: {key}")

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

    try:
        # Check if this is a first save
        is_new_issue = True
        try:
            for st in ['draft', 'new']:
                try:
                    s3.head_object(Bucket=BUCKET_NAME, Key=f'jaffar/issues/{st}/{issue_id}.json')
                    is_new_issue = False
                    break
                except:
                    continue
        except:
            pass

        if is_new_issue:
            # Add creation activity
            activity = {
                "type": "system",
                "content": "Issue created",
                "timestamp": datetime.datetime.now().isoformat(),
                "author": data.get('author', 'system')
            }
            # Save the creation activity separately
            save_issue_changes(issue_id, activity)

        logger.info("Starting JSON serialization")
        json_data = json.dumps(data,
                               ensure_ascii=False,
                               cls=CircularRefEncoder)
        logger.info("JSON serialization completed")

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json_data.encode('utf-8'),
                      ContentType='application/json')
        logger.info("S3 save completed successfully")

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
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            existing_changes = json.loads(
                response['Body'].read().decode('utf-8'))
            logger.info(f"Loaded {len(existing_changes)} existing changes")

            if not isinstance(existing_changes, list):
                existing_changes = [existing_changes]

            for change in new_changes:
                if change not in existing_changes:
                    existing_changes.append(change)
                    logger.info("Added new change to history")

        except Exception as e:
            logger.info(f"No existing changes found: {e}")
            existing_changes = new_changes

        json_data = json.dumps(existing_changes, ensure_ascii=False)
        logger.info(
            f"Successfully serialized {len(existing_changes)} changes to JSON")

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json_data.encode('utf-8'),
                      ContentType='application/json')
        logger.info("Successfully saved to S3")

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
        response = s3.get_object(Bucket=BUCKET_NAME, Key=changes_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except s3.exceptions.NoSuchKey:
        logger.info(f"No changes found for issue {issue_id}")
        return []
    except Exception as e:
        logger.error(f"Failed to get changes for {issue_id}: {e}")
        return []


# Jaffar Routes
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
    user_email = request.form.get('user_email') or request.args.get(
        'user_email')

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
def list_issues():
    issues = []
    try:
        for status in ['draft', 'new']:
            prefix = f'jaffar/issues/{status}/'
            try:
                response = s3.list_objects_v2(Bucket=BUCKET_NAME,
                                              Prefix=prefix)
                if 'Contents' in response:
                    for obj in response['Contents']:
                        try:
                            response = s3.get_object(Bucket=BUCKET_NAME,
                                                     Key=obj['Key'])
                            issue = json.loads(
                                response['Body'].read().decode('utf-8'))
                            # Remove changes field to reduce payload size
                            if 'changes' in issue:
                                del issue['changes']
                            issues.append(issue)
                        except Exception as e:
                            logger.error(
                                f"Error loading issue {obj['Key']}: {e}")
            except Exception as e:
                logger.error(f"Error listing issues for status {status}: {e}")
        return jsonify(issues)
    except Exception as e:
        logger.error(f"Error in list_issues: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/jaffar/issues/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    for status in ['draft', 'new']:
        try:
            key = f'jaffar/issues/{status}/{issue_id}.json'
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            return jsonify(json.loads(response['Body'].read().decode('utf-8')))
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
    escalations = []
    prefix = 'sultan/escalations/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                escalation = json.loads(content)
                escalations.append(escalation)
            except Exception as e:
                logger.error(f"Failed to load escalation {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(escalations)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)