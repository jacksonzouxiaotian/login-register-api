# -*- coding: utf-8 -*-
"""Application configuration.

Most configuration is set via environment variables.

For local development, use a .env file to set
environment variables.
"""
from environs import Env

env = Env()
env.read_env()

ENV = env.str("FLASK_ENV", default="production")
DEBUG = ENV == "development"
SQLALCHEMY_DATABASE_URI = env.str("DATABASE_URL")
SECRET_KEY = env.str("SECRET_KEY")
SEND_FILE_MAX_AGE_DEFAULT = env.int("SEND_FILE_MAX_AGE_DEFAULT")
BCRYPT_LOG_ROUNDS = env.int("BCRYPT_LOG_ROUNDS", default=13)
DEBUG_TB_ENABLED = DEBUG
DEBUG_TB_INTERCEPT_REDIRECTS = False
CACHE_TYPE = (
    "flask_caching.backends.SimpleCache"  # Can be "MemcachedCache", "RedisCache", etc.
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
FLASK_ENV  = env.str("FLASK_ENV", "production")
DATABASE_URL = env.str("DATABASE_URL")

MAIL_SERVER   = env.str("MAIL_SERVER")
MAIL_PORT     = env.int("MAIL_PORT")
MAIL_USE_TLS  = env.bool("MAIL_USE_TLS", False)
MAIL_USERNAME = env.str("MAIL_USERNAME")
MAIL_PASSWORD = env.str("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = env.str("MAIL_USERNAME")
WTF_CSRF_ENABLED = False
SEND_FILE_MAX_AGE_DEFAULT = env.int("SEND_FILE_MAX_AGE_DEFAULT", 0)

