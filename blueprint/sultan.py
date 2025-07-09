from flask import Blueprint, render_template, request, jsonify, redirect
import json
import logging
import uuid
from services.s3_service import (
    save_in_global_db,
    get_one_from_global_db,
    get_max_from_global_db,
    list_folder_with_filter,
    get_sultan_object,
    save_sultan_object,
    delete_sultan_object,
    list_sultan_objects
)

logger = logging.getLogger(__name__)

# Create Sultan blueprint with prefix
sultan_bp = Blueprint('sultan', __name__, url_prefix='/pc-analytics-jaffar/sultan')

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
    return render_template('/sultan/escalation/index.html')

@sultan_bp.route('/escalation/create')
def escalation_create():
    new_id = f"Escalation-{uuid.uuid4()}"
    # Structure vide ou par défaut
    escalation = []
    save_sultan_object('escalations', new_id, escalation)
    # Redirige vers la page d'édition
    return redirect(f"/pc-analytics-jaffar/sultan/escalation/edit/{new_id}")

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
    return render_template('sultan/templates/edit2.html')

@sultan_bp.route('/templates/edit-datatable/<template_id>')
def template_edit_datatable(template_id):
    return render_template('sultan/templates/edit-datatable.html')

@sultan_bp.route('/dashboard/<dashboard_id>')
def dashboard_edit(dashboard_id):
    return render_template('sultan/dashboards/edit.html', dashboard_id=dashboard_id)

@sultan_bp.route('/dashboards')
def dashboards_list():
    return render_template('sultan/dashboards/index.html')

@sultan_bp.route('/workflows')
def workflows_list():
    return render_template('sultan/workflows/index.html')

@sultan_bp.route('/workflows/edit/<workflow_id>')
def workflow_edit(workflow_id):
    return render_template('sultan/workflows/edit.html')

# API Routes
@sultan_bp.route('/api/dashboard/<dashboard_id>', methods=['GET'])
def api_dashboard_get(dashboard_id):
    """Get a dashboard config from S3"""
    try:
        dashboard = get_sultan_object('dashboards', dashboard_id)
        if dashboard:
            return jsonify(dashboard)
        else:
            return jsonify({"error": "Dashboard not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get dashboard {dashboard_id}: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/dashboard/create', methods=['POST'])
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

        save_sultan_object('dashboards', dashboard_id, dashboard)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/dashboards/list')
def api_dashboards_list():
    """List all dashboards"""
    try:
        dashboards = list_sultan_objects('dashboards')
        return jsonify(dashboards)
    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/emailgroups/list')
def api_emailgroups_list():
    try:
        emailgroups = list_sultan_objects('emailgroups')
        return jsonify(emailgroups)
    except Exception as e:
        logger.error(f"Failed to list emailgroups: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/sites/list')
def api_sites_list():
    try:
        sites = list_sultan_objects('sites')
        return jsonify(sites)
    except Exception as e:
        logger.error(f"Failed to list sites: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/escalation/list')
def api_escalation_list():
    try:
        escalations = list_sultan_objects('escalations')
        escalation_names = [f"{escalation.get('id', '')}.json" for escalation in escalations if escalation.get('id')]
        return jsonify(escalation_names)
    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/escalation/save', methods=['POST'])
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

        save_sultan_object('escalations', escalation_id, escalations)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save escalation: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/escalation/<escalation_id>')
def api_escalation_get(escalation_id):
    try:
        escalation = get_sultan_object('escalations', escalation_id)
        if escalation is not None:
            return jsonify(escalation)
        else:
            return jsonify({"error": "Escalation not found"}), 404
    except Exception as e:
        logger.error(f"Failed to load escalation {escalation_id}: {e}")
        return jsonify({"error": str(e)}), 404

@sultan_bp.route('/api/forms', methods=['GET'])
def api_forms():
    try:
        forms = list_sultan_objects('forms')
        return jsonify(forms)
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/forms/<form_id>', methods=['GET'])
def api_form_by_id(form_id):
    """Fetch a specific form by its ID"""
    try:
        form = get_sultan_object('forms', form_id)
        if form:
            return jsonify(form)
        else:
            return jsonify({"error": "Form not found"}), 404
    except Exception as e:
        logger.error(f"Failed to fetch form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/forms/save', methods=['POST'])
def api_save_form():
    data = request.json
    form = data.get('form')
    if not form:
        return jsonify({"error": "Invalid form data"}), 400
    try:
        save_sultan_object('forms', form["id"], form)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/forms/delete/<form_id>', methods=['DELETE'])
def api_delete_form(form_id):
    try:
        delete_sultan_object('forms', form_id)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete form: {e}")
        return jsonify({"error": str(e)}), 500

# Add the missing API route for Sultan forms save
@sultan_bp.route('/api/sultan/forms/save', methods=['POST'])
def api_sultan_save_form():
    data = request.json
    form = data.get('form')
    if not form:
        return jsonify({"error": "Invalid form data"}), 400
    try:
        save_sultan_object('forms', form["id"], form)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/templates/<template_id>')
def api_template_get(template_id):
    try:
        if template_id.endswith('.json'):
            template_id = template_id[:-5]  # Remove .json extension

        template = get_sultan_object('templates', template_id)
        if template:
            return jsonify(template)
        else:
            return jsonify({
                "error": "Template not found",
                "redirect": "/pc-analytics-jaffar/sultan/templates/list"
            }), 404
    except Exception as e:
        logger.error(f"Failed to load template {template_id}: {e}")
        return jsonify({
            "error": "Template not found",
            "redirect": "/pc-analytics-jaffar/sultan/templates/list"
        }), 404

@sultan_bp.route('/api/templates/delete/<template_id>', methods=['POST'])
def api_template_delete(template_id):
    """Move a template to the 'sultan/templates/delete/' folder"""
    try:
        # Get the template first
        template = get_sultan_object('templates', template_id)
        if template:
            # Save to delete folder
            save_sultan_object('templates/delete', template_id, template)
            # Delete from main folder
            delete_sultan_object('templates', template_id)
            return jsonify({
                "status": "success",
                "message": f"Template {template_id} moved to delete folder"
            }), 200
        else:
            return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        logger.error(f"Failed to move template {template_id} to delete folder: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/api/templates', methods=['GET'])
def api_templates_list():
    """Fetch the list of templates from the S3 bucket"""
    try:
        templates = list_sultan_objects('templates')
        return jsonify(templates)
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500

@sultan_bp.route('/save/dashboard', methods=['POST'])
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

        save_sultan_object('dashboards', dashboard_id, dashboard)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save dashboard: {e}")
        return jsonify({"error": str(e)}), 500

