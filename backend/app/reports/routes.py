from flask import request, jsonify
from flask import current_app
from app.reports import reports_bp
from app import db
from app.models import Report, Item, User
from flask_login import login_required, current_user
from app.utils.settings import get_int_setting

ALLOWED_REPORT_REASONS = {
    'fraud',
    'abuse',
    'spam',
    'illegal_item',
    'prohibited_item',
    'hate_speech',
    'other',
}


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
    reason = (data.get('reason') or '').strip().lower()
    details = (data.get('details') or '').strip()
    
    if target_type not in ('item', 'user') or not target_id or not reason:
        return jsonify({'error': 'validation'}), 400
    if reason not in ALLOWED_REPORT_REASONS:
        return jsonify({'error': 'validation', 'message': 'invalid report reason'}), 400
    if len(reason) > 100:
        return jsonify({'error': 'validation', 'message': 'report reason is too long'}), 400
    if not details:
        return jsonify({'error': 'validation', 'message': 'report details are required'}), 400
    if len(details) > 1000:
        return jsonify({'error': 'validation', 'message': 'report details must be 1000 characters or fewer'}), 400
        
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

    rpt = Report(
        reporter_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        details=details,
        status='submitted',
    )
    db.session.add(rpt)
    db.session.commit()

    # Calculate actual unique report count
    count = Report.query.filter_by(target_type=target_type, target_id=target_id).count()
    
    # Auto-blocking logic
    threshold = get_int_setting(
        'report_threshold',
        current_app.config.get('AUTO_BLOCK_REPORT_THRESHOLD', 5),
    )
    if count >= threshold:
        if target_type == 'item':
            target.status = 'blocked'
        else: # user
            target.is_active = False
            target.session_version += 1
            target.active_session_token = None
        db.session.commit()

    return jsonify({
        'report_id': rpt.id,
        'target_type': target_type,
        'target_id': target_id,
        'report_status': rpt.status,
        'current_count_for_target': count,
        'target_status': target.status if target_type == 'item' else ('active' if target.is_active else 'inactive')
    }), 201
