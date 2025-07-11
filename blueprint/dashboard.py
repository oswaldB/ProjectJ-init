from flask import Blueprint, render_template, request, jsonify
from services.s3_service import list_sultan_objects, get_sultan_object, save_sultan_object, delete_sultan_object

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/sultan/dashboard')

@dashboard_bp.route('/')
def index():
    return render_template('sultan/dashboards/index.html')

@dashboard_bp.route('/edit/<dashboard_id>')
def edit(dashboard_id):
    return render_template('sultan/dashboards/edit.html')

@dashboard_bp.route('/<dashboard_id>')
def view_dashboard(dashboard_id):
    return render_template('sultan/dashboards/edit.html')

@dashboard_bp.route('/api/list')
def api_list():
    try:
        dashboards = list_sultan_objects('dashboards')
        return jsonify(dashboards)
    except Exception as e:
        return jsonify([]), 500

@dashboard_bp.route('/api/<dashboard_id>')
def api_get(dashboard_id):
    try:
        dashboard = get_sultan_object('dashboards', dashboard_id)
        return jsonify(dashboard or {})
    except Exception as e:
        return jsonify({}), 404

@dashboard_bp.route('/api/save', methods=['POST'])
def api_save():
    try:
        data = request.json
        dashboard_id = data.get('id')
        if save_sultan_object('dashboards', dashboard_id, data):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to save dashboard"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_bp.route('/api/delete/<dashboard_id>', methods=['DELETE'])
def api_delete(dashboard_id):
    try:
        delete_sultan_object('dashboards', dashboard_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500