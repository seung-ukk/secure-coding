from flask import request, jsonify
from app.admin import admin_bp


@admin_bp.route('/reports', methods=['GET'])
def list_reports():
    # TODO: restrict to admin role
    return jsonify({'reports': []})


@admin_bp.route('/reports/<int:report_id>/action', methods=['POST'])
def report_action(report_id):
    data = request.get_json() or {}
    return jsonify({'report_id': report_id, 'action': data.get('action')}), 200
