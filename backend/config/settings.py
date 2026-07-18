import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "archive",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": dj_database_url.config(
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
)}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = PROJECT_ROOT / "media"

LINODE_S3_BUCKET = os.getenv("LINODE_S3_BUCKET", "").strip()
if LINODE_S3_BUCKET:
    INSTALLED_APPS.append("storages")
    LINODE_S3_ENDPOINT = os.getenv(
        "LINODE_S3_ENDPOINT",
        "https://us-ord-10.linodeobjects.com",
    ).rstrip("/")
    LINODE_S3_CUSTOM_DOMAIN = os.getenv(
        "LINODE_S3_CUSTOM_DOMAIN",
        f"{LINODE_S3_BUCKET}.{LINODE_S3_ENDPOINT.removeprefix('https://').removeprefix('http://')}",
    )
    STORAGES["default"] = {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": os.environ["LINODE_S3_ACCESS_KEY_ID"],
                "secret_key": os.environ["LINODE_S3_SECRET_ACCESS_KEY"],
                "bucket_name": LINODE_S3_BUCKET,
                "endpoint_url": LINODE_S3_ENDPOINT,
                "custom_domain": LINODE_S3_CUSTOM_DOMAIN,
                "location": "media",
                "default_acl": None,
                "querystring_auth": False,
                "file_overwrite": False,
            },
    }
    MEDIA_URL = f"https://{LINODE_S3_CUSTOM_DOMAIN}/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "archive.pagination.ArchivePagination",
    "PAGE_SIZE": 20,
}
MAX_IMPORT_FILE_SIZE = int(os.getenv("MAX_IMPORT_FILE_SIZE", str(500 * 1024 * 1024)))
MAX_ARCHIVE_EXPANDED_SIZE = int(os.getenv("MAX_ARCHIVE_EXPANDED_SIZE", str(2 * 1024 * 1024 * 1024)))
MAX_ARCHIVE_FILES = int(os.getenv("MAX_ARCHIVE_FILES", "5000"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"
