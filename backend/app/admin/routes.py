from datetime import datetime
from flask import request, jsonify, abort
from app.admin import admin_bp
from app import db
from flask_login import current_user
from functools import wraps
from app.utils.settings import get_int_setting, set_setting

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/reports', methods=['GET'])
@admin_required
def list_reports():
    from app.models import Report
    reports = Report.query.order_by(Report.created_at.desc()).all()
    out = []
    for r in reports:
        out.append({
            'id': r.id,
            'reporter_id': r.reporter_id,
            'target_type': r.target_type,
            'target_id': r.target_id,
            'reason': r.reason,
            'details': r.details,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
            'reviewed_at': r.reviewed_at.isoformat() if r.reviewed_at else None,
        })
    return jsonify({'reports': out})


@admin_bp.route('/audit-logs', methods=['GET'])
@admin_required
def list_audit_logs():
    from app.models import AuditLog

    limit = min(max(int(request.args.get('limit', 50)), 1), 200)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify({
        'logs': [
            {
                'id': log.id,
                'actor_id': log.actor_id,
                'action': log.action,
                'target_type': log.target_type,
                'target_id': log.target_id,
                'details': log.details,
                'created_at': log.created_at.isoformat(),
            }
            for log in logs
        ]
    }), 200


@admin_bp.route('/settings/report-threshold', methods=['GET'])
@admin_required
def get_report_threshold():
    threshold = get_int_setting('report_threshold', 5)
    return jsonify({'report_threshold': threshold}), 200


@admin_bp.route('/settings/report-threshold', methods=['PATCH'])
@admin_required
def update_report_threshold():
    from app.models import AuditLog

    data = request.get_json() or {}
    threshold = data.get('report_threshold')
    try:
        threshold_value = int(threshold)
    except (TypeError, ValueError):
        return jsonify({'error': 'validation', 'message': 'report_threshold must be an integer'}), 400
    if not (1 <= threshold_value <= 50):
        return jsonify({'error': 'validation', 'message': 'report_threshold must be between 1 and 50'}), 400

    set_setting('report_threshold', str(threshold_value))
    log = AuditLog(
        actor_id=current_user.id,
        action='admin_update_report_threshold',
        target_type='setting',
        target_id=None,
        details=f'report threshold set to {threshold_value}',
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'report_threshold': threshold_value}), 200


@admin_bp.route('/reports/<int:report_id>/action', methods=['POST'])
@admin_required
def report_action(report_id):
    from app.models import Report, AuditLog
    rpt = Report.query.get_or_404(report_id)
    data = request.get_json() or {}
    action = (data.get('action') or '').strip().lower()
    if not action:
        return jsonify({'error': 'validation', 'message': 'action required'}), 400
    if action not in {'review', 'approve', 'reject'}:
        return jsonify({'error': 'validation', 'message': 'invalid action'}), 400

    rpt.status = {
        'review': 'reviewing',
        'approve': 'accepted',
        'reject': 'rejected',
    }[action]
    rpt.reviewed_at = datetime.utcnow()
    
    details = f"admin action '{action}' taken on report {report_id}"
    log = AuditLog(actor_id=current_user.id, action='admin_report_action', target_type='report', target_id=report_id, details=details)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'report_id': report_id, 'action': action, 'status': rpt.status, 'reviewed_at': rpt.reviewed_at.isoformat()}), 200


@admin_bp.route('/users/<int:user_id>/status', methods=['PATCH'])
@admin_required
def admin_change_user_status(user_id):
    from app.models import User, AuditLog
    user = User.query.get_or_404(user_id)
    
    data = request.get_json() or {}
    is_active = data.get('is_active')
    
    if is_active is None:
        return jsonify({'error': 'validation', 'message': 'is_active is required'}), 400
        
    new_status = bool(is_active)
    if user.is_active and not new_status:
        user.session_version += 1
        user.active_session_token = None
    user.is_active = new_status
    
    details = f"admin set user {user_id} active status to {user.is_active}"
    log = AuditLog(actor_id=current_user.id, action='admin_change_user_status', target_type='user', target_id=user_id, details=details)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'user_id': user_id, 'is_active': user.is_active}), 200


@admin_bp.route('/products/<int:item_id>/status', methods=['PATCH'])
@admin_required
def admin_change_item_status(item_id):
    from app.models import Item, AuditLog
    item = Item.query.get_or_404(item_id)
    
    data = request.get_json() or {}
    status = data.get('status')
    
    if not status:
        return jsonify({'error': 'validation', 'message': 'status is required'}), 400
        
    status = status.strip().lower()
    if status not in ('available', 'reserved', 'sold', 'blocked', 'deleted'):
        return jsonify({'error': 'validation', 'message': 'invalid status'}), 400
        
    item.status = status
    
    details = f"admin set item {item_id} status to {item.status}"
    log = AuditLog(actor_id=current_user.id, action='admin_change_item_status', target_type='item', target_id=item_id, details=details)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'item_id': item_id, 'status': item.status}), 200
