from flask import request, jsonify
from app.reports import reports_bp
from app import db
from app.models import Report, Item, User
from flask_login import login_required, current_user


@reports_bp.route('', methods=['POST'])
@login_required
def create_report():
    data = request.get_json() or {}
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    reason = data.get('reason')
    details = data.get('details')
    if target_type not in ('item', 'user') or not target_id or not reason:
        return jsonify({'error': 'validation'}), 400
    # basic existence check
    if target_type == 'item' and not Item.query.get(target_id):
        return jsonify({'error': 'not_found'}), 404
    if target_type == 'user' and not User.query.get(target_id):
        return jsonify({'error': 'not_found'}), 404
    rpt = Report(reporter_id=current_user.id, target_type=target_type, target_id=target_id, reason=reason, details=details)
    db.session.add(rpt)
    db.session.commit()
    # simple aggregation
    count = Report.query.filter_by(target_type=target_type, target_id=target_id).count()
    return jsonify({'report_id': rpt.id, 'target_type': target_type, 'target_id': target_id, 'current_count_for_target': count}), 201
