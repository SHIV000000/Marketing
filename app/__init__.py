# Marketing/app/__init__.py

import os
from flask import Flask, render_template, url_for, request
from flask_mail import Mail
from dotenv import load_dotenv
from app.database import db
from app.routes import bp
from app.admin import bp as admin_bp
from app.deutsche import bp as deut_bp
from app.finapi import bp as fin_bp
from app.mail import bp as mail_bp
from app.google_ads.google_ads_routes import bp as google_ads_bp
from app.bank_transactions import bp as bank_bp
from app.data_analysis import bp as analysis_bp

load_dotenv()

mail = Mail()

def create_app():
    app = Flask(__name__)

    app.config.from_prefixed_env()
    
    app.secret_key = os.getenv('FLASK_SECRET_KEY')
    
    # Set the SQLALCHEMY_DATABASE_URI
    database_uri = os.getenv('FLASK_SQLALCHEMY_DATABASE_URI')
    if not database_uri:
        # If the environment variable is not set, use a default SQLite database
        base_dir = os.path.abspath(os.path.dirname(__file__))
        database_uri = f"sqlite:///{os.path.join(base_dir, 'app.db')}"
        print(f"Using default SQLite database: {database_uri}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['ADMIN_LIST'] = os.getenv('FLASK_ADMIN_LIST', '').split(',')

    # Email configuration
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.googlemail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)

    # Register blueprints
    app.register_blueprint(bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(deut_bp, url_prefix="/deutsche")
    app.register_blueprint(fin_bp, url_prefix="/finapi")
    app.register_blueprint(mail_bp, url_prefix="/mail")
    app.register_blueprint(google_ads_bp, url_prefix="/google-ads")
    app.register_blueprint(bank_bp, url_prefix="/bank")
    app.register_blueprint(analysis_bp, url_prefix="/analysis")
    
    with app.app_context():
        db.create_all()

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('page_not_found.html'), 404

    return app
