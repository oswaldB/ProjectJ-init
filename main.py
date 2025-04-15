from flask import Flask, Blueprint, render_template, redirect, send_from_directory, request, jsonify
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import json
import re
import pandas as pd
import boto3
from moto import mock_aws
import os

app = Flask(__name__)
logger = logging.getLogger(__name__)

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
    pass  # Bucket may already exist

restore_local_to_s3()


class Email:

    def __init__(self, to, subject, content):
        self.to = to if isinstance(to, list) else [to]
        self.subject = subject
        self.content = content

    def send(self):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = "jaffar@hsbc.com"
        msg['To'] = ", ".join(self.to)
        html_part = MIMEText(self.content, 'html')
        msg.attach(html_part)
        try:
            with smtplib.SMTP('localhost') as server:
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


def flatten_dict(dd, separator='_', prefix=''):
    return {
        f"{prefix}{separator}{k}" if prefix else k: v
        for kk, vv in dd.items()
        for k, v in flatten_dict(vv, separator, kk).items()
    } if isinstance(dd, dict) else {
        prefix: dd
    }


def process_issue_data(issue_data):
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


def save_in_global_db(key, obj):
    json_object = json.dumps(obj, separators=(',', ':'))
    try:
        # S3 save
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_object)

        # Local save
        full_path = os.path.join(LOCAL_BUCKET_DIR, key)
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(json_object)
        return True
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return False


def get_one_from_global_db(key):
    try:
        # Try S3 first
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except:
        # Fallback to local
        try:
            local_path = os.path.join(LOCAL_BUCKET_DIR, key)
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.loads(f.read())
        except Exception as e:
            logger.error(f"Failed to get data: {e}")
            raise


def get_max_from_global_db(key):
    files = []
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME,
                                      Prefix='jaffar/configs/')
        for obj in response.get('Contents', []):
            files.append(obj['Key'])

        max_number = -1
        max_object = None
        for file in files:
            remaining_parts = file[len('jaffar/configs/'):]
            match = re.match(r'(\d+)-' + key, remaining_parts)
            if match:
                number = int(match.group(1))
                if number > max_number:
                    max_number = number
                    max_object = file
        if max_object is not None:
            return get_one_from_global_db(max_object)
        else:
            return "No objects with the given key and a digit at the beginning found."
    except Exception as e:
        logger.error(f"Error in get_max_from_global_db: {e}")
        return None


def get_max_filename_from_global_db(key):
    files = []
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME,
                                      Prefix='jaffar/configs/')
        for obj in response.get('Contents', []):
            files.append(obj['Key'])

        max_number = -1
        max_object = None
        for file in files:
            remaining_parts = file[len('jaffar/configs/'):]
            match = re.match(r'(\d+)-' + key, remaining_parts)
            if match:
                number = int(match.group(1))
                if number > max_number:
                    max_number = number
                    max_object = file
        if max_object is not None:
            return max_object
        else:
            return "No objects with the given key and a digit at the beginning found."
    except Exception as e:
        logger.error(f"Error in get_max_filename_from_global_db: {e}")
        return None


def delete(key):
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    #Local delete
    full_path = os.path.join(LOCAL_BUCKET_DIR, key)
    if os.path.exists(full_path):
        os.remove(full_path)
    return


def sendConfirmationEmail(email_address, subject, issue):
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
    <p>If it requires escalation, you will get another email very soon.</p>
    <br>
    <br>
    <p>All the best,</p>
    """
    content = style + message
    email = Email(
        to=email_address,
        subject=subject,
        content=content,
    )
    return email.send()


# Routes
@app.route('/login')
def login():
    if request.path == '/login':
        return render_template('login.html')
    return redirect('/')


def require_auth(f):
    from functools import wraps
    from flask import request, redirect, url_for

    @wraps(f)
    def decorated(*args, **kwargs):
        if request.path == '/login':
            return f(*args, **kwargs)

        if not request.headers.get('user_email') and not request.cookies.get(
                'user_email'):
            current_path = request.path
            return redirect(f'/login?redirect={current_path}')
        return f(*args, **kwargs)

    return decorated


@app.route('/')
def index():
    return render_template('jaffar/index.html')


@app.route('/sultan/login')
def sultan_login():
    return render_template('sultan/login.html')


@app.route('/sultan')
def sultan():
    return render_template('sultan/base.html')


@app.route('/sultan/<path:path>')
def sultan_pages(path):
    return render_template(f'sultan/{path}')


@app.route('/questions')
def questions():
    return render_template('sultan/pages/jaffar-questions-studio.html')


@app.route('/questions/import')
def questions_import():
    return render_template('sultan/questions/import.html')


@app.route('/questions/export')
def questions_export():
    return render_template('components/questions/export.html')


@app.route('/sultan/forms')
def forms_list():
    return render_template('sultan/forms/index.html')


@app.route('/sultan/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')

@app.route('/sultan/escalation')
def escalation_list():
    return render_template('sultan/escalation/index.html')

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
    draft_prefix = 'sultan/configs/draft/escalations/'

    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=draft_prefix)
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

@app.route('/api/sultan/escalation/<escalation_id>')
def api_escalation_get(escalation_id):
    try:
        if escalation_id.endswith('.json'):
            key = f'sultan/configs/draft/escalations/{escalation_id}'
        else:
            key = f'sultan/configs/draft/escalations/{escalation_id}.json'

        content = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load escalation {escalation_id}: {e}")
        return jsonify({"error": "Escalation not found"}), 404

@app.route('/api/sultan/escalation/duplicate', methods=['POST'])
def api_escalation_duplicate():
    data = request.json
    escalation_id = data.get('id')
    
    try:
        # Get original escalation
        escalation = get_one_from_global_db(f'sultan/configs/draft/escalations/{escalation_id}.json')
        
        # Create new escalation with unique ID
        import uuid
        new_escalation = escalation.copy()
        new_escalation['id'] = f'escalation-{str(uuid.uuid4())}'
        new_escalation['name'] = f'{escalation["name"]} (Copy)'
        
        # Save new escalation
        save_in_global_db(f'sultan/configs/draft/escalations/{new_escalation["id"]}.json', new_escalation)
        
        return jsonify(new_escalation)
    except Exception as e:
        logger.error(f"Failed to duplicate escalation: {e}")
        return jsonify({"error": "Failed to duplicate escalation"}), 500

@app.route('/api/sultan/escalation/delete/<escalation_id>', methods=['DELETE'])
def api_escalation_delete(escalation_id):
    try:
        key = f'sultan/configs/draft/escalations/{escalation_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete escalation: {e}")
        return jsonify({"error": "Failed to delete escalation"}), 500

@app.route('/api/sultan/escalation/save', methods=['POST'])
def api_escalation_save():
    data = request.json
    escalation = data.get('escalation')

    if not escalation:
        return jsonify({"error": "Escalation required"}), 400

    try:
        escalation_path = f'sultan/configs/draft/escalations/{escalation["id"]}.json'
        save_in_global_db(escalation_path, escalation)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save escalation: {e}")
        return jsonify({"error": "Failed to save escalation"}), 500

@app.route('/api/sultan/emailgroups/<emailgroup_id>')
def api_emailgroup_get(emailgroup_id):
    try:
        if emailgroup_id.endswith('.json'):
            key = f'sultan/emailgroups/{emailgroup_id}'
        else:
            key = f'sultan/emailgroups/{emailgroup_id}.json'

        content = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load email group {emailgroup_id}: {e}")
        return jsonify({"error": "Email group not found"}), 404

@app.route('/api/sultan/emailgroups/save', methods=['POST'])
def api_emailgroup_save():
    data = request.json
    emailgroup = data.get('emailgroup')

    if not emailgroup:
        return jsonify({"error": "Email group required"}), 400

    try:
        emailgroup_path = f'sultan/emailgroups/{emailgroup["id"]}.json'
        save_in_global_db(emailgroup_path, emailgroup)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save email group: {e}")
        return jsonify({"error": "Failed to save email group"}), 500

@app.route('/api/sultan/emailgroups/delete/<emailgroup_id>', methods=['DELETE'])
def api_emailgroup_delete(emailgroup_id):
    try:
        key = f'sultan/emailgroups/{emailgroup_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete email group: {e}")
        return jsonify({"error": "Failed to delete email group"}), 500

@app.route('/api/sultan/sites/<site_id>')
def api_site_get(site_id):
    try:
        if site_id.endswith('.json'):
            key = f'sultan/sites/{site_id}'
        else:
            key = f'sultan/sites/{site_id}.json'

        content = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load site {site_id}: {e}")
        return jsonify({"error": "Site not found"}), 404

@app.route('/api/sultan/sites/save', methods=['POST'])
def api_site_save():
    data = request.json
    site = data.get('site')
    
    if not site:
        return jsonify({"error": "Site required"}), 400

    try:
        site_path = f'sultan/sites/{site["id"]}.json'
        save_in_global_db(site_path, site)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save site: {e}")
        return jsonify({"error": "Failed to save site"}), 500

@app.route('/api/sultan/sites/delete/<site_id>', methods=['DELETE'])
def api_site_delete(site_id):
    try:
        key = f'sultan/sites/{site_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete site: {e}")
        return jsonify({"error": "Failed to delete site"}), 500

@app.route('/sultan/templates')
def templates_list():
    return render_template('sultan/templates/index.html')

@app.route('/sultan/templates/edit/<template_id>')
def template_edit(template_id):
    return render_template('sultan/templates/edit.html')


@app.route('/api/sultan/forms')
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


@app.route('/api/sultan/forms/<form_id>')
def api_form_get(form_id):
    try:
        if form_id.endswith('.json'):
            key = f'sultan/forms/{form_id}'
        else:
            key = f'sultan/forms/{form_id}.json'

        content = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load form {form_id}: {e}")
        return jsonify({
            "error": "Form not found",
            "redirect": "/sultan/forms/list"
        }), 404


@app.route('/api/sultan/forms/delete/<form_id>', methods=['DELETE'])
def api_form_delete(form_id):
    try:
        form_path = f'sultan/forms/{form_id}.json'
        delete(form_path)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete form: {e}")
        return jsonify({"error": "Failed to delete form"}), 500

@app.route('/api/sultan/forms/save', methods=['POST'])
def api_form_save():
    data = request.json
    form = data.get('form')

    if not form:
        return jsonify({"error": "Form required"}), 400

    try:
        form_path = f'sultan/forms/{form["id"]}.json'
        save_in_global_db(form_path, form)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": "Failed to save form"}), 500


@app.route('/api/sultan/templates')
@app.route('/api/sultan/templates/list')  # Keep old route for backward compatibility
def api_templates_list():
    templates = []
    prefix = 'sultan/templates/'

    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                template = json.loads(content)

                # Add last_modified from metadata
                metadata = s3.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                template['last_modified'] = metadata['LastModified']

                templates.append(template)
            except Exception as e:
                logger.error(f"Failed to load template {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify(templates)


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


@app.route('/api/sultan/templates/delete/<template_id>', methods=['DELETE'])
def api_template_delete(template_id):
    try:
        key = f'sultan/templates/{template_id}.json'
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        return jsonify({"error": "Failed to delete template"}), 500


@app.route('/api/sultan/templates/save', methods=['POST'])
def api_template_save():
    data = request.json
    template = data.get('template')

    if not template:
        return jsonify({"error": "Template required"}), 400

    try:
        template_path = f'sultan/templates/{template["id"]}.json'
        save_in_global_db(template_path, template)
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
        
        # Create new template with unique ID using uuid
        import uuid
        new_template = template.copy()
        new_template['id'] = f'templates-{str(uuid.uuid4())}'
        new_template['name'] = f'{template["name"]} (Copy)'
        
        # Save new template
        save_in_global_db(f'sultan/templates/{new_template["id"]}.json', new_template)
        
        return jsonify(new_template)
    except Exception as e:
        logger.error(f"Failed to duplicate template: {e}")
        return jsonify({"error": "Failed to duplicate template"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)