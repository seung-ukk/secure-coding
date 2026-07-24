from flask import request, jsonify, current_app, abort
from app.items import items_bp
from app import db
from app.models import Item, ItemImage, User
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os, uuid
from app.utils.security import (
    MAX_IMAGE_FILE_SIZE,
    detect_image_type,
    get_file_size,
    is_allowed_image_extension,
    is_allowed_image_mime_type,
)
from app.utils.validators import (
    validate_item_description,
    validate_item_price,
    validate_item_title,
)
from app.models import Transaction


def _serialize_item(it: Item):
    return {
        'id': it.id,
        'title': it.title,
        'description': it.description,
        'price': float(it.price),
        'status': it.status,
    }


def _validate_and_save_images(files, item_id: int):
    if not files:
        return []

    max_image_count = current_app.config.get('MAX_ITEM_IMAGE_COUNT', 5)
    if len(files) > max_image_count:
        raise ValueError(f'no more than {max_image_count} images are allowed')

    upload_folder = current_app.config.get('UPLOAD_FOLDER') or '/tmp/secure_media'
    os.makedirs(upload_folder, exist_ok=True)
    max_file_size = current_app.config.get('MAX_ITEM_IMAGE_SIZE', MAX_IMAGE_FILE_SIZE)

    saved = []
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            raise ValueError('image filename is required')

        filename = secure_filename(file_storage.filename)
        if not filename:
            raise ValueError('invalid image filename')
        if not is_allowed_image_extension(filename):
            raise ValueError('only jpg, jpeg, and png images are allowed')
        if not is_allowed_image_mime_type(file_storage.mimetype):
            raise ValueError('invalid image mime type')
        if get_file_size(file_storage.stream) > max_file_size:
            raise ValueError('image file exceeds size limit')

        detected_type = detect_image_type(file_storage.stream)
        if detected_type not in ('jpeg', 'png'):
            raise ValueError('uploaded file is not a valid image')

        extension = '.jpg' if detected_type == 'jpeg' else '.png'
        dest_name = f'{uuid.uuid4()}{extension}'
        dest_path = os.path.join(upload_folder, dest_name)
        file_storage.stream.seek(0)
        file_storage.save(dest_path)
        img = ItemImage(item_id=item_id, file_path=dest_path)
        db.session.add(img)
        saved.append(dest_name)

    return saved


@items_bp.route('', methods=['GET'])
def list_items():
    q = request.args.get('q')
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 50)
    query = Item.query.filter(Item.status.notin_(['deleted', 'blocked'])).order_by(Item.created_at.desc())
    if q:
        query = query.filter(Item.title.ilike(f"%{q}%"))
    items = query.paginate(page=page, per_page=per_page, error_out=False)
    out = []
    for it in items.items:
        out.append({'id': it.id, 'title': it.title, 'price': float(it.price), 'owner_id': it.owner_id})
    return jsonify({'items': out, 'total': items.total, 'page': page, 'per_page': per_page})


@items_bp.route('', methods=['POST'])
@login_required
def create_item():
    title_ok, title = validate_item_title(request.form.get('title'))
    if not title_ok:
        return jsonify({'error': 'validation', 'message': title}), 400

    description_ok, description = validate_item_description(request.form.get('description'))
    if not description_ok:
        return jsonify({'error': 'validation', 'message': description}), 400

    price_ok, price_val, price_message = validate_item_price(request.form.get('price'))
    if not price_ok:
        return jsonify({'error': 'validation', 'message': price_message}), 400

    item = Item(owner_id=current_user.id, title=title, description=description, price=price_val)
    db.session.add(item)
    db.session.commit()

    files = request.files.getlist('images[]')
    try:
        saved = _validate_and_save_images(files, item.id)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        db.session.delete(item)
        db.session.commit()
        return jsonify({'error': 'validation', 'message': str(exc)}), 400

    return jsonify({'id': item.id, 'title': item.title, 'price': float(item.price), 'images': saved}), 201


@items_bp.route('/<int:item_id>', methods=['GET'])
def get_item(item_id):
    it = Item.query.get_or_404(item_id)
    if it.status in ('deleted', 'blocked'):
        if not current_user.is_authenticated or (current_user.id != it.owner_id and current_user.role != 'admin'):
            abort(404)
    images = ItemImage.query.filter_by(item_id=it.id).all()
    imgs = [f"/api/media/{os.path.basename(img.file_path)}" for img in images]
    owner = User.query.get(it.owner_id)
    payload = _serialize_item(it)
    payload.update({'images': imgs, 'owner': {'id': owner.id, 'username': owner.username}})
    return jsonify(payload)


@items_bp.route('/mine', methods=['GET'])
@login_required
def my_items():
    items = Item.query.filter_by(owner_id=current_user.id).order_by(Item.created_at.desc()).all()
    out = []
    for it in items:
        out.append({'id': it.id, 'title': it.title, 'price': float(it.price), 'status': it.status})
    return jsonify({'items': out})


@items_bp.route('/<int:item_id>/request', methods=['POST'])
@login_required
def request_purchase(item_id):
    it = Item.query.get_or_404(item_id)
    if it.owner_id == current_user.id:
        return jsonify({'error': 'validation', 'message': 'cannot request own item'}), 400
    if not current_user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'inactive users cannot request purchases'}), 403
    if it.status != 'available':
        return jsonify({'error': 'validation', 'message': 'item is not available for purchase'}), 400

    existing = Transaction.query.filter(
        Transaction.item_id == it.id,
        Transaction.buyer_id == current_user.id,
        Transaction.seller_id == it.owner_id,
        Transaction.status.in_(['requested', 'accepted']),
    ).order_by(Transaction.created_at.desc()).first()
    if existing:
        return jsonify({'transaction_id': existing.id, 'status': existing.status, 'message': 'existing request'}), 200

    tx = Transaction(item_id=it.id, buyer_id=current_user.id, seller_id=it.owner_id)
    db.session.add(tx)
    db.session.commit()
    return jsonify({'transaction_id': tx.id, 'status': tx.status}), 201


@items_bp.route('/<int:item_id>', methods=['PATCH'])
@login_required
def update_item(item_id):
    it = Item.query.get_or_404(item_id)
    if it.owner_id != current_user.id:
        return jsonify({'error': 'forbidden', 'message': 'You do not own this item'}), 403
    
    if it.status in ('deleted', 'blocked'):
        return jsonify({'error': 'validation', 'message': f'Cannot update item in status {it.status}'}), 400

    data = request.get_json() if request.is_json else request.form.to_dict()

    title = data.get('title')
    description = data.get('description')
    price = data.get('price')
    status = data.get('status')

    if title is not None:
        title_ok, title = validate_item_title(title)
        if not title_ok:
            return jsonify({'error': 'validation', 'message': title}), 400
        it.title = title

    if description is not None:
        description_ok, description = validate_item_description(description)
        if not description_ok:
            return jsonify({'error': 'validation', 'message': description}), 400
        it.description = description

    if price is not None:
        price_ok, price_val, price_message = validate_item_price(price)
        if not price_ok:
            return jsonify({'error': 'validation', 'message': price_message}), 400
        it.price = price_val

    if status is not None:
        status = status.strip().lower()
        if status != 'available':
            return jsonify({'error': 'validation', 'message': 'item status transitions must go through transaction flow'}), 400
        active_transactions = Transaction.query.filter(
            Transaction.item_id == it.id,
            Transaction.status.in_(['requested', 'accepted']),
        ).count()
        if active_transactions:
            return jsonify({'error': 'validation', 'message': 'cannot mark item available while active transactions exist'}), 400
        it.status = status

    db.session.commit()
    return jsonify(_serialize_item(it)), 200


@items_bp.route('/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    it = Item.query.get_or_404(item_id)
    if it.owner_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'forbidden', 'message': 'Permission denied'}), 403
        
    it.status = 'deleted'
    
    from app.models import AuditLog
    details = f"item {it.id} deleted by user {current_user.id}"
    log = AuditLog(actor_id=current_user.id, action='delete_item', target_type='item', target_id=it.id, details=details)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Item soft deleted successfully'}), 200
