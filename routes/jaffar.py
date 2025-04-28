
from flask import Blueprint, request, jsonify, render_template, redirect
from services.storage import save_in_global_db, get_one_from_global_db, delete
import datetime
import json
import logging

logger = logging.getLogger(__name__)
jaffar = Blueprint('jaffar', __name__)

@jaffar.route('/')
def index():
    return render_template('jaffar/index.html')

@jaffar.route('/edit')
def edit():
    return render_template('jaffar/edit.html')

@jaffar.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')

@jaffar.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')

@jaffar.route('/api/jaffar/issues/list', methods=['GET'])
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
