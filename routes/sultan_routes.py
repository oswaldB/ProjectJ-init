
from flask import Blueprint, render_template, redirect, request, jsonify, send_file
import json
import logging
from main import s3, BUCKET_NAME, save_in_global_db, delete

logger = logging.getLogger(__name__)
sultan_bp = Blueprint('sultan', __name__)

@sultan_bp.route('/')
def index():
    return render_template('sultan/base.html')

@sultan_bp.route('/login')
def login():
    return render_template('sultan/login.html')

@sultan_bp.route('/forms')
def forms_list():
    return render_template('sultan/forms/index.html')

@sultan_bp.route('/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')

@sultan_bp.route('/escalation')
def escalation_list():
    return redirect('/sultan/escalation/edit/new')

@sultan_bp.route('/escalation/edit/<escalation_id>')
def escalation_edit(escalation_id):
    return render_template('sultan/escalation/edit.html')

@sultan_bp.route('/emailgroups')
def emailgroups_list():
    return render_template('sultan/emailgroups/index.html')

@sultan_bp.route('/emailgroups/edit/<emailgroup_id>')
def emailgroup_edit(emailgroup_id):
    return render_template('sultan/emailgroups/edit.html')

@sultan_bp.route('/sites')
def sites_list():
    return render_template('sultan/sites/index.html')

@sultan_bp.route('/sites/edit/<site_id>')
def site_edit(site_id):
    return render_template('sultan/sites/edit.html')

@sultan_bp.route('/templates')
def templates_list():
    return render_template('sultan/templates/index.html')

@sultan_bp.route('/templates/edit/<template_id>')
def template_edit(template_id):
    return render_template('sultan/templates/edit.html')

# API Routes
@sultan_bp.route('/api/emailgroups/list')
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

@sultan_bp.route('/api/sites/list')
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

@sultan_bp.route('/api/escalation/list')
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
