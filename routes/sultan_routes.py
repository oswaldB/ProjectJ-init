
from flask import Blueprint, render_template, redirect

sultan_bp = Blueprint('sultan', __name__)

@sultan_bp.route('/login')
def login():
    return render_template('sultan/login.html')

@sultan_bp.route('/')
def index():
    return render_template('sultan/base.html')

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
