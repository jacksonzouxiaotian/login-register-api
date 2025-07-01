# tests/test_reset_password.py

import json
import pytest

from research_assistant.user.models import User, EmailCaptcha
from research_assistant.extensions import db, bcrypt


@pytest.fixture
def client(app):
    with app.app_context():
        db.create_all()
        client = app.test_client()
        yield client
        db.session.remove()
        db.drop_all()


def test_reset_password_success(client):
    User.create(
        username="alice",
        email="alice@example.com",
        password="oldpassword",
        active=True
    )
    db.session.commit()

    cap = EmailCaptcha(email="alice@example.com", captcha="654321")
    db.session.add(cap)
    db.session.commit()

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
    assert "message" in body
    assert substr.lower() in body["message"].lower()


def test_reset_password_invalid_captcha(client):
    User.create(
        username="bob",
        email="bob@example.com",
        password="oldpass",
        active=True
    )
    db.session.commit()

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
    assert "invalid" in body["message"].lower() or "Verification code error" in body["message"]


def test_reset_password_email_not_registered(client):
    cap = EmailCaptcha(email="nobody@example.com", captcha="123123")
    db.session.add(cap)
    db.session.commit()

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
    assert "not registered" in body["message"].lower() or "Not registered" in body["message"]
