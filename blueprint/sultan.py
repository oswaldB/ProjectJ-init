
from flask import Blueprint, render_template, request, jsonify, redirect
import json
import logging
import uuid
from services.s3_service import (
    save_in_global_db,
    get_one_from_global_db,
    get_max_from_global_db,
    list_folder_with_filter
)
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

# Create Sultan blueprint with prefix
sultan_blueprint = Blueprint('sultan', __name__, url_prefix='/pc-analytics-jaffar/sultan')

@sultan_blueprint.route('/')
def index():
    return render_template('sultan/base.html')

@sultan_blueprint.route('/login')
def login():
    return render_template('sultan/login.html')

@sultan_blueprint.route('/forms')
def forms_list():
    return render_template('sultan/forms/index.html')

@sultan_blueprint.route('/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')

@sultan_blueprint.route('/escalation')
def escalation_list():
    return render_template('/sultan/escalation/index.html')

@sultan_blueprint.route('/escalation/create')
def escalation_create():
    new_id = f"Escalation-{uuid.uuid4()}"
    # Structure vide ou par défaut
    escalation = []
    key = f"sultan/escalations/{new_id}.json"
    s3.put_object(Bucket=BUCKET_NAME,
                  Key=key,
                  Body=json.dumps(escalation, ensure_ascii=False),
                  ContentType='application/json')
    # Redirige vers la page d'édition
    return redirect(f"/pc-analytics-jaffar/sultan/escalation/edit/{new_id}")

@sultan_blueprint.route('/escalation/edit/<escalation_id>')
def escalation_edit(escalation_id):
    return render_template('sultan/escalation/edit.html')

@sultan_blueprint.route('/emailgroups')
def emailgroups_list():
    return render_template('sultan/emailgroups/index.html')

@sultan_blueprint.route('/emailgroups/edit/<emailgroup_id>')
def emailgroup_edit(emailgroup_id):
    return render_template('sultan/emailgroups/edit.html')

@sultan_blueprint.route('/sites')
def sites_list():
    return render_template('sultan/sites/index.html')

@sultan_blueprint.route('/sites/edit/<site_id>')
def site_edit(site_id):
    return render_template('sultan/sites/edit.html')

@sultan_blueprint.route('/templates')
def templates_list():
    return render_template('sultan/templates/index.html')

@sultan_blueprint.route('/templates/edit/<template_id>')
def template_edit(template_id):
    return render_template('sultan/templates/edit2.html')

@sultan_blueprint.route('/templates/edit-datatable/<template_id>')
def template_edit_datatable(template_id):
    return render_template('sultan/templates/edit-datatable.html')

@sultan_blueprint.route('/dashboard/<dashboard_id>')
def dashboard_edit(dashboard_id):
    return render_template('sultan/dashboards/edit.html', dashboard_id=dashboard_id)

@sultan_blueprint.route('/dashboards')
def dashboards_list():
    return render_template('sultan/dashboards/index.html')

@sultan_blueprint.route('/workflows')
def workflows_list():
    return render_template('sultan/workflows/index.html')

@sultan_blueprint.route('/workflows/edit/<workflow_id>')
def workflow_edit(workflow_id):
    return render_template('sultan/workflows/edit.html')

# API Routes
@sultan_blueprint.route('/api/dashboard/<dashboard_id>', methods=['GET'])
def api_dashboard_get(dashboard_id):
    """Get a dashboard config from S3"""
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

@sultan_blueprint.route('/api/dashboard/create', methods=['POST'])
def api_dashboard_create():
    """Create a new dashboard config"""
    try:
        data = request.json
        dashboard_id = data.get('dashboard_id')
        dashboard = data.get('dashboard', {})
        if not dashboard_id:
            return jsonify({"error": "Missing dashboard_id"}), 400
        
        if 'name' not in dashboard:
            dashboard['name'] = dashboard_id
        
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
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(dashboard, ensure_ascii=False),
                      ContentType='application/json')
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_blueprint.route('/api/dashboards/list')
def api_dashboards_list():
    """List all dashboards"""
    dashboards = []
    prefix = 'sultan/dashboards/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue
            try:
                content = s3.get_object(Bucket=BUCKET_NAME,
                                        Key=key)['Body'].read().decode('utf-8')
                dashboard = json.loads(content)
                dashboards.append(dashboard)
            except Exception as e:
                logger.error(f"Failed to load dashboard {key}: {e}")
    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(dashboards)

@sultan_blueprint.route('/api/emailgroups/list')
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

@sultan_blueprint.route('/api/sites/list')
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

@sultan_blueprint.route('/api/escalation/list')
def api_escalation_list():
    escalation_names = []
    prefix = 'sultan/escalations/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                key = obj['Key']
                name = key.split('/')[-1]
                escalation_names.append(name)
            except Exception as e:
                logger.error(f"Failed to process escalation {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(escalation_names)

@sultan_blueprint.route('/api/escalation/save', methods=['POST'])
def api_escalation_save():
    try:
        data = request.json
        
        if isinstance(data, dict):
            escalation_id = data.get('id')
            escalations = data.get('escalations')
        elif isinstance(data, list):
            escalations = data
            escalation_id = request.args.get('id')
        else:
            return jsonify({"error": "Invalid payload"}), 400
        
        if not escalation_id or not isinstance(escalations, list):
            return jsonify({"error": "Missing escalation ID or escalations array"}), 400
        
        key = f"sultan/escalations/{escalation_id}.json"
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(escalations, ensure_ascii=False),
                      ContentType='application/json')
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save escalation: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_blueprint.route('/api/escalation/<escalation_id>')
def api_escalation_get(escalation_id):
    key = f"sultan/escalations/{escalation_id}.json"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load escalation {escalation_id}: {e}")
        return jsonify({"error": str(e)}), 404

@sultan_blueprint.route('/api/forms', methods=['GET'])
def api_forms():
    forms = []
    try:
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

@sultan_blueprint.route('/api/forms/<form_id>', methods=['GET'])
def api_form_by_id(form_id):
    """Fetch a specific form by its ID"""
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

@sultan_blueprint.route('/api/forms/save', methods=['POST'])
def api_save_form():
    data = request.json
    form = data.get('form')
    if not form:
        return jsonify({"error": "Invalid form data"}), 400
    key = f'sultan/forms/{form["id"]}.json'
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(form))
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_blueprint.route('/api/forms/delete/<form_id>', methods=['DELETE'])
def api_delete_form(form_id):
    key = f'sultan/forms/{form_id}.json'
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete form: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_blueprint.route('/api/templates/<template_id>')
def api_template_get(template_id):
    try:
        if template_id.endswith('.json'):
            key = f'sultan/templates/{template_id}'
        else:
            key = f'sultan/templates/{template_id}.json'
        
        content = s3.get_object(Bucket=BUCKET_NAME,
                                Key=key)['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load template {template_id}: {e}")
        return jsonify({
            "error": "Template not found",
            "redirect": "/pc-analytics-jaffar/sultan/templates/list"
        }), 404

@sultan_blueprint.route('/api/templates/delete/<template_id>', methods=['POST'])
def api_template_delete(template_id):
    """Move a template to the 'sultan/templates/delete/' folder"""
    try:
        source_key = f'sultan/templates/{template_id}.json'
        destination_key = f'sultan/templates/delete/{template_id}.json'
        
        s3.copy_object(Bucket=BUCKET_NAME,
                       CopySource={
                           'Bucket': BUCKET_NAME,
                           'Key': source_key
                       },
                       Key=destination_key)
        
        s3.delete_object(Bucket=BUCKET_NAME, Key=source_key)
        
        return jsonify({
            "status": "success",
            "message": f"Template {template_id} moved to delete folder"
        }), 200
    except Exception as e:
        logger.error(f"Failed to move template {template_id} to delete folder: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_blueprint.route('/api/templates/save', methods=['POST'])
def api_template_save():
    data = request.json
    template = data.get('template')
    
    if not template:
        return jsonify({"error": "Template required"}), 400
    
    try:
        template['author'] = data.get('author', 'system')
        template['email'] = data.get('email', 'system')
        template_array = [template]
        template_path = f'sultan/templates/{template["id"]}.json'
        save_in_global_db(template_path, template_array)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save template: {e}")
        return jsonify({"error": "Failed to save template"}), 500

@sultan_blueprint.route('/api/templates/duplicate', methods=['POST'])
def api_template_duplicate():
    data = request.json
    template_id = data.get('id')
    
    try:
        template = get_one_from_global_db(f'sultan/templates/{template_id}.json')
        new_template = template.copy()
        new_template['id'] = f'templates-{str(uuid.uuid4())}'
        new_template['name'] = f'{template["name"]} (Copy)'
        
        save_in_global_db(f'sultan/templates/{new_template["id"]}.json', new_template)
        return jsonify(new_template)
    except Exception as e:
        logger.error(f"Failed to duplicate template: {e}")
        return jsonify({"error": "Failed to duplicate template"}), 500

@sultan_blueprint.route('/api/templates', methods=['GET'])
def api_templates_list():
    """Fetch the list of templates from the S3 bucket"""
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

@sultan_blueprint.route('/save/dashboard', methods=['POST'])
def save_dashboard():
    """Save a dashboard configuration to S3"""
    try:
        data = request.json
        dashboard = data.get('dashboard')
        dashboard_id = data.get('dashboard_id') or (dashboard and dashboard.get('id'))
        
        if not dashboard or not dashboard_id:
            return jsonify({"error": "Missing dashboard or dashboard_id"}), 400
        
        form_id = dashboard.get('form_id') or dashboard.get('selectedFormKey')
        form_name = dashboard.get('form_name')
        source_id = dashboard.get('source_id') or form_id
        config_filters = dashboard.get('configFilters', {})
        
        if form_id:
            dashboard['form_id'] = form_id
        if form_name:
            dashboard['form_name'] = form_name
        if source_id:
            dashboard['source_id'] = source_id
        if config_filters:
            dashboard['configFilters'] = config_filters
        
        key = f'sultan/dashboards/{dashboard_id}.json'
        s3.put_object(Bucket=BUCKET_NAME,
                      Key=key,
                      Body=json.dumps(dashboard, ensure_ascii=False),
                      ContentType='application/json')
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save dashboard: {e}")
        return jsonify({"error": str(e)}), 500
