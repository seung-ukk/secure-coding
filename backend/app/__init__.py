import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_object: str = 'app.config.Config'):
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_object(config_object)

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
        user_area = '아직 로그인하지 않았습니다.'
        if current_user.is_authenticated:
            user_area = f'로그인됨: <strong>{current_user.username}</strong>'
        return html.replace('{{user_area}}', user_area)

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

    return app
