from flask import request, jsonify, current_app
from app.items import items_bp
from app import db
from app.models import Item, ItemImage, User
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os, uuid
from app.utils.security import verify_file_type


@items_bp.route('', methods=['GET'])
def list_items():
    q = request.args.get('q')
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 50)
    query = Item.query.order_by(Item.created_at.desc())
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
    title = request.form.get('title')
    description = request.form.get('description')
    price = request.form.get('price')
    category_id = request.form.get('category_id')
    if not title or not price:
        return jsonify({'error': 'validation', 'message': 'title and price required'}), 400
    try:
        price_val = float(price)
    except Exception:
        return jsonify({'error': 'validation', 'message': 'invalid price'}), 400
    item = Item(owner_id=current_user.id, title=title, description=description, price=price_val)
    db.session.add(item)
    db.session.commit()

    files = request.files.getlist('images[]')
    saved = []
    upload_folder = current_app.config.get('UPLOAD_FOLDER') or '/tmp'
    for f in files:
        if not f:
            continue
        filename = secure_filename(f.filename)
        ext = os.path.splitext(filename)[1].lower()
        uid = str(uuid.uuid4())
        dest_name = uid + ext
        dest_path = os.path.join(upload_folder, dest_name)
        # verify image
        if not verify_file_type(f.stream):
            continue
        f.save(dest_path)
        img = ItemImage(item_id=item.id, file_path=dest_path)
        db.session.add(img)
        saved.append(dest_name)
    db.session.commit()
    return jsonify({'id': item.id, 'title': item.title, 'price': float(item.price), 'images': saved}), 201


@items_bp.route('/<int:item_id>', methods=['GET'])
def get_item(item_id):
    it = Item.query.get_or_404(item_id)
    images = ItemImage.query.filter_by(item_id=it.id).all()
    imgs = [img.file_path for img in images]
    owner = User.query.get(it.owner_id)
    return jsonify({'id': it.id, 'title': it.title, 'description': it.description, 'price': float(it.price), 'images': imgs, 'owner': {'id': owner.id, 'username': owner.username}, 'status': it.status})


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

    from app.models import Transaction
    existing = Transaction.query.filter_by(item_id=it.id, buyer_id=current_user.id, seller_id=it.owner_id).order_by(Transaction.created_at.desc()).first()
    if existing:
        return jsonify({'transaction_id': existing.id, 'status': existing.status, 'message': 'existing request'}), 200

    tx = Transaction(item_id=it.id, buyer_id=current_user.id, seller_id=it.owner_id)
    db.session.add(tx)
    db.session.commit()
    return jsonify({'transaction_id': tx.id, 'status': tx.status}), 201
