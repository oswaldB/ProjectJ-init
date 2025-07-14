
from flask import Blueprint, render_template

dashboards_preview_bp = Blueprint('dashboards_preview', __name__, url_prefix='/dashboards')

@dashboards_preview_bp.route('/<dashboard_id>')
def view_dashboard(dashboard_id):
    return render_template('dashboards/index.html')
