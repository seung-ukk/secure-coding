import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_object: str = 'app.config.Config'):
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_object(config_object)
    auth_paths = {'/api/auth/login', '/api/auth/register', '/api/auth/csrf-token'}

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Import models before creating tables so the metadata is registered.
    from app import models  # noqa: F401

    # Register blueprints (minimal skeletons)
    from app.auth.routes import auth_bp
    from app.items.routes import items_bp
    from app.transactions.routes import transactions_bp
    from app.reports.routes import reports_bp
    from app.admin.routes import admin_bp
    from app.payments.routes import payments_bp
    from app.users import users_bp
    from app.chat import chat_bp

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(items_bp, url_prefix='/api/items')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')

    login_manager.login_view = None

    @app.before_request
    def enforce_active_session():
        if not current_user.is_authenticated:
            return None
        try:
            from app.models import User

            result = db.session.execute(
                db.select(
                    User.id,
                    User.is_active,
                    User.session_version,
                    User.active_session_token,
                ).where(User.id == current_user.id)
            ).first()
        except Exception:
            db.session.rollback()
            session.clear()
            logout_user()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized', 'message': 'session expired'}), 401
            return None
        if not result:
            session.clear()
            logout_user()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized', 'message': 'session expired'}), 401
            return None
        user_id, is_active, session_version_db, active_session_token = result
        if not is_active:
            session.clear()
            logout_user()
            if request.path in auth_paths:
                return None
            if request.path.startswith('/api/'):
                return jsonify({'error': 'forbidden', 'message': 'account is inactive'}), 403
            return None
        session_version = session.get('session_version')
        if session_version is not None and session_version != session_version_db:
            session.clear()
            logout_user()
            if request.path in auth_paths:
                return None
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized', 'message': 'session expired'}), 401
            return None
        session_token = session.get('session_token')
        if session_token is not None and session_token != active_session_token:
            session.clear()
            logout_user()
            if request.path in auth_paths:
                return None
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized', 'message': 'session expired'}), 401
            return None
        return None

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'error': 'unauthorized', 'message': 'authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(_error):
        return jsonify({'error': 'forbidden', 'message': 'permission denied'}), 403

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({'error': 'not_found', 'message': 'resource not found'}), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return jsonify({'error': 'server_error', 'message': 'internal server error'}), 500

    # simple health route
    @app.route('/health')
    def health():
        return {'status': 'ok'}

    @app.route('/api/media/<filename>')
    def serve_media(filename):
        upload_folder = app.config.get('UPLOAD_FOLDER') or '/tmp/secure_media'
        os.makedirs(upload_folder, exist_ok=True)
        return send_from_directory(upload_folder, filename)

    @app.route('/')
    def index():
        html_path = Path(app.static_folder) / 'index.html'
        html = html_path.read_text(encoding='utf-8')
        legacy_catalog_label = '\ufffd\ufffd\u01f0 \ufffd\ufffd\u0238'
        user_area = '아직 로그인하지 않았습니다.'
        if current_user.is_authenticated:
            user_area = f'로그인됨: <strong>{current_user.username}</strong>'
        if '{{user_area}}' in html:
            return html.replace('{{user_area}}', user_area)
        user_panel = (
            '<section class="card" style="margin-bottom: 1.5rem;">'
            f'<p>{user_area}</p>'
            '<p>?곹뭹 議고쉶</p>'
            f'<p>{legacy_catalog_label}</p>'
            '<p>??? ???</p>'
            '</section>'
        )
        return html.replace('<section class="hero-section">', f'{user_panel}<section class="hero-section">', 1)

    @app.route('/login')
    def login_page():
        return app.send_static_file('login.html')

    @app.route('/register')
    def register_page():
        return app.send_static_file('register.html')

    @app.route('/items')
    def items_page():
        return app.send_static_file('items.html')

    @app.route('/items/<int:item_id>')
    def item_detail_page(item_id):
        return app.send_static_file('item_detail.html')

    @app.route('/dashboard')
    def dashboard_page():
        return app.send_static_file('dashboard.html')

    @app.route('/admin')
    def admin_page():
        return app.send_static_file('admin.html')

    return app
