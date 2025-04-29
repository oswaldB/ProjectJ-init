from flask import Flask, Blueprint, render_template, redirect, send_from_directory, request, jsonify, send_file
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import pandas as pd
import os
import datetime
from services.s3_service import (
    restore_local_to_s3, save_issue_to_storage, save_issue_changes,
    get_changes_from_global_db, list_issues, get_issue, get_max_from_global_db,
    delete_object
)

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Email handling
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

def process_issue_data(issue_data):
    processed_data = {}
    for key, value in issue_data.items():
        if isinstance(value, list):
            processed_data[key] = ', '.join(value)
        elif isinstance(value, dict):
            processed_data.update(value)
        else:
            processed_data[key] = value
    return processed_data

def sendConfirmationEmail(email_address, subject, issue):
    logger.info(f"Sending email to {email_address}")
    issue_data = process_issue_data(issue)
    style = """
    <style>
        table {
            border-collapse: collapse;
            font-family: 'Helvetica';
            font-size: 12px;
        }
        th { font-weight: normal }
        th, td {
            border: 1px solid #ccc;
            padding: 5px;
            text-align: left;
        }
        td {
            font-family: Helvetica;
            font-size: 12px;
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
    email = Email(to=email_address, subject=subject, content=content)
    return email.send()

# Routes
@app.route('/api/jaffar/save', methods=['POST'])
def api_jaffar_save():
    try:
        data = request.json
        if not data or 'id' not in data:
            return jsonify({"error": "Missing required data"}), 400

        issue_id = data['id']
        status = data.get('status', 'draft')
        logger.info(f"Saving issue {issue_id} with status {status}")

        # Extract changes before saving main issue
        changes = data.pop('changes', [])

        # Save main issue
        if not save_issue_to_storage(issue_id, status, data):
            return jsonify({"error": "Failed to save issue"}), 500

        # Save changes if present
        if changes:
            save_issue_changes(issue_id, changes)

        if data.get('author') and status == 'new':
            sendConfirmationEmail(data['author'], data['id'], data)

        return jsonify(data)
    except Exception as e:
        logger.error(f"Failed to save issue: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/issues/list', methods=['GET'])
def api_issues_list():
    try:
        issues = list_issues()
        return jsonify(issues)
    except Exception as e:
        logger.error(f"Error in list_issues: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/issues/<issue_id>', methods=['GET'])
def api_get_issue(issue_id):
    issue = get_issue(issue_id)
    if issue:
        return jsonify(issue)
    return jsonify({'error': 'Issue not found'}), 404

@app.route('/api/jaffar/config')
def api_jaffar_config():
    try:
        config = get_max_from_global_db('jaffarConfig')
        if not config:
            return jsonify({"error": "No config found"}), 404
        return jsonify(config)
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jaffar/delete', methods=['DELETE'])
def api_jaffar_delete():
    try:
        data = request.json
        if not data or 'key' not in data:
            return jsonify({"error": "Missing key"}), 400

        if delete_object(data['key']):
            return jsonify({"status": "success"})
        return jsonify({"error": "Failed to delete object"}), 500
    except Exception as e:
        logger.error(f"Failed to delete: {e}")
        return jsonify({"error": str(e)}), 500

from routes.jaffar_routes import jaffar_bp
from routes.sultan_routes import sultan_bp

app.register_blueprint(jaffar_bp)
app.register_blueprint(sultan_bp, url_prefix='/sultan')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)