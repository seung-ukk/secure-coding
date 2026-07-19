from flask import request, jsonify, abort
from app.admin import admin_bp
from app import db
from flask_login import current_user
from functools import wraps

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
            'created_at': r.created_at.isoformat()
        })
    return jsonify({'reports': out})


@admin_bp.route('/reports/<int:report_id>/action', methods=['POST'])
@admin_required
def report_action(report_id):
    from app.models import Report, AuditLog
    rpt = Report.query.get_or_404(report_id)
    data = request.get_json() or {}
    action = data.get('action')
    if not action:
        return jsonify({'error': 'validation', 'message': 'action required'}), 400
    
    details = f"admin action '{action}' taken on report {report_id}"
    log = AuditLog(actor_id=current_user.id, action='admin_report_action', target_type='report', target_id=report_id, details=details)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'report_id': report_id, 'action': action, 'status': 'processed'}), 200


@admin_bp.route('/users/<int:user_id>/status', methods=['PATCH'])
@admin_required
def admin_change_user_status(user_id):
    from app.models import User, AuditLog
    user = User.query.get_or_404(user_id)
    
    data = request.get_json() or {}
    is_active = data.get('is_active')
    
    if is_active is None:
        return jsonify({'error': 'validation', 'message': 'is_active is required'}), 400
        
    user.is_active = bool(is_active)
    
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


