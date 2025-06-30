# -*- coding: utf-8 -*-
"""Public section, including homepage and signup (API version)."""
from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)
from flask_login import login_required, login_user, logout_user
import random
import string
from flask_mail import Message
from research_assistant.extensions import login_manager, mail, bcrypt, db, csrf_protect
from research_assistant.public.forms import LoginForm
from research_assistant.user.forms import RegisterForm
from research_assistant.user.models import User, EmailCaptcha

blueprint = Blueprint("public", __name__, static_folder="../static")

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.get_by_id(int(user_id))

@blueprint.route("/", methods=["GET"])
def home():
    """
    API endpoint for service health check or greeting.
    """
    current_app.logger.info("Hello from the home page (API)!")
    return jsonify({
        "code": 0,
        "msg": "API service is running",
        "data": {}
    })

@blueprint.route("/login/", methods=["POST"])
def login():
    """
    API endpoint for user login.
    Accepts JSON body: { "email": "", "password": "" }
    Returns authentication status.
    """
    json_data = request.get_json()
    if not json_data:
        return jsonify({"code": 400, "msg": "Missing JSON data"}), 400

    form = LoginForm(data=json_data)
    if form.validate():
        login_user(form.user)
        return jsonify({
            "code": 0,
            "msg": "Login successful",
            "data": {
                "user_id": form.user.id,
                "username": form.user.username
            }
        })
    else:
        # Collect error messages for frontend display
        errors = [f"{field}: {','.join(errs)}" for field, errs in form.errors.items()]
        return jsonify({
            "code": 401,
            "msg": "Login failed",
            "errors": errors
        }), 401

@blueprint.route("/logout/", methods=["POST"])
@login_required
def logout():
    """
    API endpoint for logging out the current user.
    """
    logout_user()
    return jsonify({
        "code": 0,
        "msg": "Logout successful"
    })
@blueprint.route("/register/", methods=["POST"])
def register():
    """
    API endpoint for new user registration.
    Accepts JSON body: { "username": "", "email": "", "password": "" }
    Returns registration result.
    """
    json_data = request.get_json()
    if not json_data:
        return jsonify({"code": 400, "msg": "Missing JSON data"}), 400

    form = RegisterForm(data=json_data)
    if form.validate():
        User.create(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            active=True,
        )
        return jsonify({
            "code": 0,
            "msg": "Registration successful, you can now log in."
        })
    else:
        errors = [f"{field}: {','.join(errs)}" for field, errs in form.errors.items()]
        return jsonify({
            "code": 400,
            "msg": "Registration failed",
            "errors": errors
        }), 400

@blueprint.route("/about/", methods=["GET"])
def about():
    """
    API endpoint for service/about information.
    """
    return jsonify({
        "code": 0,
        "msg": "About this API service",
        "data": {
            "version": "1.0.0",
            "description": "Research Assistant API"
        }
    })
@csrf_protect.exempt
@blueprint.route("/captcha/email/", methods=["GET", "POST"])
def send_email_captcha():
    """
    Request an email verification code.
    Expected JSON body: {"email": "user@example.com"}
    """
    if request.method == "GET":
        email = request.args.get("email")
    else:  # POST
        data = request.get_json() or {}
        email = data.get("email")
    if not email:
        return jsonify({"code": 400, "message": "Email is required"}), 400

    # Generate a 6-digit numeric code
    code = "".join(random.choices(string.digits, k=6))

    # Send the email
    try:
        msg = Message(
            subject="[Research Assistant] Registration / Password Reset Code",
            recipients=[email],
            body=f"Your verification code is: {code}. It is valid for 10 minutes."
        )
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return jsonify({"code": 500, "message": "Failed to send email"}), 500

    # Save the code to the database
    cap = EmailCaptcha(email=email, captcha=code)
    db.session.add(cap)
    db.session.commit()

    return jsonify({"code": 200, "message": "Verification code sent successfully"})


@csrf_protect.exempt
@blueprint.route("/password/reset/", methods=["POST"])
def reset_password():
    """
    Reset user password.
    Expected JSON body:
    {
      "email": "...",
      "captcha": "...",
      "new_password": "..."
    }
    """
    data = request.get_json() or {}
    email = data.get("email")
    captcha = data.get("captcha")
    new_password = data.get("new_password")

    if not all([email, captcha, new_password]):
        return jsonify({
            "code": 400,
            "message": "Email, captcha, and new_password are all required"
        }), 400

    # Validate the most recent captcha entry
    record = (
        EmailCaptcha.query
                    .filter_by(email=email, captcha=captcha)
                    .order_by(EmailCaptcha.created_at.desc())
                    .first()
    )
    if not record:
        return jsonify({"code": 400, "message": "Invalid or expired captcha"}), 400

    # Find the user and update their password
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"code": 404, "message": "Email not registered"}), 404

    # Hash the new password and save
    user.password = new_password#bcrypt.generate_password_hash(new_password).decode("utf-8")
    db.session.commit()

    return jsonify({"code": 200, "message": "Password reset successfully"})