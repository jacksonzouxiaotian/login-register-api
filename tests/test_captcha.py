# tests/test_captcha.py

import json
import re
import pytest
from flask import Flask

from research_assistant.extensions import db, mail
from research_assistant.public.views import blueprint as public_bp
from research_assistant.user.models import EmailCaptcha


@pytest.fixture
def app():
    """Create a minimal Flask app for testing just the captcha endpoints."""
    app = Flask(__name__)
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "MAIL_SUPPRESS_SEND": True,           # 抑制真实 SMTP
        "MAIL_DEFAULT_SENDER": "noreply@example.com",  # ← 必填：默认发件人
    })

    # 初始化我们需要的扩展
    db.init_app(app)
    mail.init_app(app)

    # 只注册 public blueprint（包含 /captcha/email/）
    app.register_blueprint(public_bp)

    # 创建表
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_send_email_captcha_success(client):
    with mail.record_messages() as outbox:
        resp = client.post(
            "/captcha/email/",
            data=json.dumps({"email": "test@example.com"}),
            content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 200

        # 验证数据库保存
        cap = EmailCaptcha.query.filter_by(email="test@example.com").first()
        assert cap is not None
        assert re.fullmatch(r"\d{6}", cap.captcha)

        # 验证邮件已“发送”并包含验证码
        assert len(outbox) == 1
        sent = outbox[0]
        assert "Your verification code is:" in sent.body
        assert cap.captcha in sent.body


def test_send_email_captcha_missing_email(client):
    resp = client.post(
        "/captcha/email/",
        json={}  # 没有提供 email
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["message"] == "Email is required"
