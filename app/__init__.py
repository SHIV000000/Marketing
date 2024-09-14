# Marketing\app\__init__.py

from flask import Flask, render_template, url_for, request
from dotenv import load_dotenv
from app.database import db
from app.routes import bp
from app.admin import bp as admin_bp
from app.deutsche import bp as deut_bp
from app.finapi import bp as fin_bp
from app.mail import bp as mail_bp
from app.google_ads import bp as google_ads_bp
from app.bank_transactions import bp as bank_bp
from app.data_analysis import bp as analysis_bp
import os

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config.from_prefixed_env()
    
    app.secret_key = os.getenv('FLASK_SECRET_KEY')
    
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('FLASK_SQLALCHEMY_DATABASE_URI')

    app.config['ADMIN_LIST'] = os.getenv('FLASK_ADMIN_LIST', '').split(',')

    db.init_app(app)
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
