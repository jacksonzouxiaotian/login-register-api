# tests/test_reset_password.py

import json
import pytest

from research_assistant.user.models import User, EmailCaptcha
from research_assistant.extensions import db, bcrypt


@pytest.fixture
def client(app):
    """
    创建一个带测试数据库的 test_client：
      - 在 app_context 里创建所有表
      - 测试结束后清空 session 并 drop_all
    """
    with app.app_context():
        db.create_all()
        client = app.test_client()
        yield client
        db.session.remove()
        db.drop_all()


def test_reset_password_success(client):
    """密码重置成功的场景"""
    # 1) 先在测试库中创建一个用户
    User.create(
        username="alice",
        email="alice@example.com",
        password="oldpassword",
        active=True
    )
    db.session.commit()

    # 2) 再插入一条对应的验证码
    cap = EmailCaptcha(email="alice@example.com", captcha="654321")
    db.session.add(cap)
    db.session.commit()

    # 3) 调用重置密码接口
    resp = client.post(
        "/password/reset/",
        data=json.dumps({
            "email": "alice@example.com",
            "captcha": "654321",
            "new_password": "newsecret"
        }),
        content_type="application/json"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["code"] == 200
    assert "reset" in data["message"] or "reset" in data["message"].lower()

    updated = User.query.filter_by(email="alice@example.com").first()
    assert bcrypt.check_password_hash(updated.password, "newsecret")


@pytest.mark.parametrize("payload, status, substr", [
    ({},                    400, "required"),
    ({"email": "x"},        400, "required"),
    ({"email": "x", "captcha": "1"},    400, "required"),
    ({"email": "x", "new_password": "p"}, 400, "required"),
    ({"captcha": "1", "new_password": "p"}, 400, "required"),
])
def test_reset_password_missing_params(client, payload, status, substr):
    resp = client.post(
        "/password/reset/",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert resp.status_code == status
    body = resp.get_json()
    # 接口返回字段是 "message"
    assert "message" in body
    assert substr.lower() in body["message"].lower()


def test_reset_password_invalid_captcha(client):
    """验证码不匹配（或过期）时返回 400 + 错误提示。"""
    # 1) 仅创建用户，不插入对应 captcha
    User.create(
        username="bob",
        email="bob@example.com",
        password="oldpass",
        active=True
    )
    db.session.commit()

    # 2) 用不存在的验证码调用
    resp = client.post(
        "/password/reset/",
        json={
            "email": "bob@example.com",
            "captcha": "000000",
            "new_password": "whatever"
        }
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "invalid" in body["message"].lower() or "验证码错误" in body["message"]


def test_reset_password_email_not_registered(client):
    """验证码正确，但邮箱未注册时返回 404 + 未注册提示。"""
    # 1) 插入一条验证码到数据库（邮箱不在 users 表中）
    cap = EmailCaptcha(email="nobody@example.com", captcha="123123")
    db.session.add(cap)
    db.session.commit()

    # 2) 调用接口
    resp = client.post(
        "/password/reset/",
        json={
            "email": "nobody@example.com",
            "captcha": "123123",
            "new_password": "anything"
        }
    )
    assert resp.status_code == 404
    body = resp.get_json()
    assert "not registered" in body["message"].lower() or "未注册" in body["message"]
