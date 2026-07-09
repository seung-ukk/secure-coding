import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
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

    # Register blueprints (minimal skeletons)
    from app.auth.routes import auth_bp
    from app.items.routes import items_bp
    from app.transactions.routes import transactions_bp
    from app.reports.routes import reports_bp
    from app.admin.routes import admin_bp
    from app.payments.routes import payments_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(items_bp, url_prefix='/api/items')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')

    # simple health route
    @app.route('/health')
    def health():
        return {'status': 'ok'}

    @app.route('/')
    def index():
        return app.send_static_file('index.html')

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

    return app
