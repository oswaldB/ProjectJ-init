"""
App name: pc_analytics_jaffar
"""
import boto3
import json
import logging
from flask import Flask, Response, redirect, request, jsonify, render_template, flash
import pandas as pd
from typing import Dict
import os
import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

# Import blueprints
from blueprint.sultan import sultan_bp
from blueprint.jaffar import jaffar_blueprint
from blueprint.forms import forms_blueprint
from blueprint.jaffar_api import jaffar_api_blueprint
from blueprint.dashboard import dashboard_bp
from blueprint.workflow import workflow_bp
from blueprint.agents import agents_bp

# Import services
from services.s3_service import save_in_global_db, get_one_from_global_db, get_max_from_global_db

# Initialize Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(sultan_bp)
app.register_blueprint(jaffar_blueprint)
app.register_blueprint(forms_blueprint)
app.register_blueprint(jaffar_api_blueprint)
app.register_blueprint(dashboard_bp)
app.register_blueprint(workflow_bp)
app.register_blueprint(agents_bp)

logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Initialize a thread pool executor for handling email tasks
email_executor = ThreadPoolExecutor(max_workers=5)


# Custom health check
def custom_health_check():
    return Response(status=200, response="Custom health check OK")


class CircularRefEncoder(json.JSONEncoder):

    def default(self, obj):
        try:
            return super().default(obj)
        except:
            return str(obj)


# Email Service Functions
def sendConfirmationEmail(email_address: str, subject: str,
                          issue: dict) -> bool:
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
        to=[
            email_address,
            "global.control.remediation.programme@noexternalmail.hsbc.com"
        ],
        subject=subject,
        content=content,
    )
    email.send()
    return True


def flatten_dict(dd: Dict, separator='_', prefix=''):
    """
    Flattens a nested dictionary and concatenates the keys with a separator.
    """
    return {
        f"{prefix}{separator}{k}" if prefix else k: v
        for kk, vv in dd.items()
        for k, v in flatten_dict(vv, separator, kk).items()
    } if isinstance(dd, dict) else {
        prefix: dd
    }


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


# Main routes now handled by blueprints

@app.route('/')
def root_redirect():
    return redirect('/pc-analytics-jaffar/')

@app.route('/api/jaffar/templates/list')
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

        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=data.encode('utf-8'),
                      ContentType=content_type)
        logger.info(f"Successfully saved data to {key}")
    except Exception as e:
        logger.error(f"Failed to save data to {key}: {e}")
        raise
# AWS configuration - Replace with your actual AWS credentials and region
REGION = os.environ.get('AWS_REGION') or 'eu-west-2'
BUCKET_NAME = os.environ.get('BUCKET_NAME') or 'pc-analytics-jaffar'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# Initialize S3 client
s3 = boto3.client('s3',
                  region_name=REGION,
                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


def delete(key):
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)


class Email:

    def __init__(self, to, subject, content):
        self.to = to
        self.subject = subject
        self.content = content

    def send(self):
        client = boto3.client(
            'ses',
            region_name=REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

        try:
            response = client.send_email(
                Destination={
                    'ToAddresses': self.to,
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': 'UTF-8',
                            'Data': self.content,
                        },
                    },
                    'Subject': {
                        'Charset': 'UTF-8',
                        'Data': self.subject,
                    },
                },
                Source="palms.reporting@noexternalmail.hsbc.com",
            )
            print(f"Email sent! Message ID: {response['MessageId']}")
        except Exception as e:
            print(f"Error sending email: {e}")


def get_one_from_global_db(filename):
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=filename)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.error(f"Error getting file from db {filename}: {e}")
        return {}


def get_max_from_global_db(filename):
    """
    Returns the content of the file ending with the highest number for a given filename prefix in S3.
    For example, if you have myconfig-1.json, myconfig-2.json, this function will return the content of myconfig-2.json.
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
        if max_filename:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=max_filename)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        else:
            return {}
    except Exception as e:
        logger.error(f"Error getting max file from db {filename}: {e}")
        return {}


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


# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))