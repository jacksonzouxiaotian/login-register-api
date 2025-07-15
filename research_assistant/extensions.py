# -*- coding: utf-8 -*-
"""Extensions module. Each extension is initialized in the app factory located in app.py."""
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_static_digest import FlaskStaticDigest
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask import current_app
import boto3
bcrypt = Bcrypt()
csrf_protect = CSRFProtect()
login_manager = LoginManager()
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
debug_toolbar = DebugToolbarExtension()
flask_static_digest = FlaskStaticDigest()

from research_assistant.user.models import User

@login_manager.user_loader
def load_user(user_id):
    """根据用户 ID 加载用户，用于 Flask-Login 管理会话。"""
    return User.query.get(int(user_id))

# 设置未登录时访问受限资源的返回行为（API 项目推荐返回 JSON 而非重定向）
login_manager.unauthorized_handler(lambda: ("Unauthorized", 401))
mail = Mail()
jwt = JWTManager()

def init_s3_client(app):
    app.s3_client = boto3.client(
        "s3",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=app.config.get("AWS_S3_REGION"),
    )

def get_s3_client():
    return current_app.s3_client
