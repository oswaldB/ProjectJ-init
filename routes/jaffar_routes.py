
from flask import Blueprint, render_template, redirect, request, jsonify
import datetime
from services.s3_service import save_issue_to_storage, save_issue_changes, get_changes_from_global_db
from services.email_service import send_confirmation_if_needed

jaffar_bp = Blueprint('jaffar', __name__)

@jaffar_bp.route('/')
def index():
    return render_template('jaffar/index.html')

@jaffar_bp.route('/edit')
def edit():
    return render_template('jaffar/edit.html')

@jaffar_bp.route('/acknowledge')
def acknowledge():
    return render_template('jaffar/acknowledge.html')

@jaffar_bp.route('/new-issue')
def new_issue():
    now = datetime.datetime.now()
    issue_id = f'JAFF-ISS-{int(now.timestamp() * 1000)}'
    user_email = request.form.get('user_email') or request.args.get('user_email')

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

@jaffar_bp.route('/edit/<issue_id>')
def edit_with_id(issue_id):
    return render_template('jaffar/edit.html')

@jaffar_bp.route('/issue/<issue_id>')
def view_issue(issue_id):
    return render_template('jaffar/issue.html')
