from pathlib import Path

from app import db
from app.models import AuditLog, Item, ItemImage, Message, Report, Transaction, User


TEST_EMAIL_SUFFIX = '@example.com'


def cleanup_test_data(upload_folder: str | None = None) -> dict[str, int]:
    test_users = User.query.filter(User.email.like(f'%{TEST_EMAIL_SUFFIX}')).all()
    if not test_users:
        return {
            'users': 0,
            'items': 0,
            'transactions': 0,
            'messages': 0,
            'reports': 0,
            'audit_logs': 0,
            'item_images': 0,
        }

    user_ids = {user.id for user in test_users}
    item_ids = {item.id for item in Item.query.filter(Item.owner_id.in_(user_ids)).all()}
    transaction_ids = {
        tx.id
        for tx in Transaction.query.filter(
            (Transaction.buyer_id.in_(user_ids)) |
            (Transaction.seller_id.in_(user_ids)) |
            (Transaction.item_id.in_(item_ids))
        ).all()
    }

    reports = Report.query.filter(
        (Report.reporter_id.in_(user_ids)) |
        ((Report.target_type == 'user') & (Report.target_id.in_(user_ids))) |
        ((Report.target_type == 'item') & (Report.target_id.in_(item_ids)))
    ).all()
    report_ids = {report.id for report in reports}

    item_images = ItemImage.query.filter(ItemImage.item_id.in_(item_ids)).all()
    image_paths = [image.file_path for image in item_images if image.file_path]

    deleted_counts = {
        'users': len(test_users),
        'items': len(item_ids),
        'transactions': len(transaction_ids),
        'messages': Message.query.filter(Message.transaction_id.in_(transaction_ids)).delete(synchronize_session=False) if transaction_ids else 0,
        'reports': len(report_ids),
        'audit_logs': AuditLog.query.filter(
            (AuditLog.actor_id.in_(user_ids)) |
            ((AuditLog.target_type == 'user') & (AuditLog.target_id.in_(user_ids))) |
            ((AuditLog.target_type == 'item') & (AuditLog.target_id.in_(item_ids))) |
            ((AuditLog.target_type == 'transaction') & (AuditLog.target_id.in_(transaction_ids)))
        ).delete(synchronize_session=False),
        'item_images': len(item_images),
    }

    if report_ids:
        Report.query.filter(Report.id.in_(report_ids)).delete(synchronize_session=False)
    if transaction_ids:
        Transaction.query.filter(Transaction.id.in_(transaction_ids)).delete(synchronize_session=False)
    if item_ids:
        ItemImage.query.filter(ItemImage.item_id.in_(item_ids)).delete(synchronize_session=False)
        Item.query.filter(Item.id.in_(item_ids)).delete(synchronize_session=False)
    User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.session.commit()

    if upload_folder:
        upload_root = Path(upload_folder)
        for raw_path in image_paths:
            try:
                image_path = Path(raw_path)
                if image_path.exists() and upload_root in image_path.parents:
                    image_path.unlink(missing_ok=True)
            except OSError:
                continue

    return deleted_counts
