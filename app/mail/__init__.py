from flask import Blueprint


bp = Blueprint('mail',
               __name__,
               template_folder="templates",
               static_folder="static",
               )

from app.mail.routes import *
