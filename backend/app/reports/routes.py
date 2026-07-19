from flask import request, jsonify
from app.reports import reports_bp
from app import db
from app.models import Report, Item, User
from flask_login import login_required, current_user


def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


@reports_bp.route('', methods=['POST'])
@login_required
def create_report():
    data = _get_request_data()
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    reason = data.get('reason')
    details = data.get('details')
    
    if target_type not in ('item', 'user') or not target_id or not reason:
        return jsonify({'error': 'validation'}), 400
        
    # Prevent self-reporting and check existence
    if target_type == 'user':
        if int(target_id) == current_user.id:
            return jsonify({'error': 'validation', 'message': 'Cannot report yourself'}), 400
        target = User.query.get(target_id)
        if not target:
            return jsonify({'error': 'not_found'}), 404
    else: # item
        target = Item.query.get(target_id)
        if not target:
            return jsonify({'error': 'not_found'}), 404
        if target.owner_id == current_user.id:
            return jsonify({'error': 'validation', 'message': 'Cannot report your own item'}), 400

    # Prevent duplicate reports from the same user
    existing = Report.query.filter_by(reporter_id=current_user.id, target_type=target_type, target_id=target_id).first()
    if existing:
        return jsonify({'error': 'conflict', 'message': 'You have already reported this target'}), 409

    rpt = Report(reporter_id=current_user.id, target_type=target_type, target_id=target_id, reason=reason, details=details)
    db.session.add(rpt)
    db.session.commit()

    # Calculate actual unique report count
    count = Report.query.filter_by(target_type=target_type, target_id=target_id).count()
    
    # Auto-blocking logic (Threshold: 5 reports)
    if count >= 5:
        if target_type == 'item':
            target.status = 'blocked'
        else: # user
            target.is_active = False
        db.session.commit()

    return jsonify({
        'report_id': rpt.id,
        'target_type': target_type,
        'target_id': target_id,
        'current_count_for_target': count,
        'target_status': target.status if target_type == 'item' else ('active' if target.is_active else 'inactive')
    }), 201

