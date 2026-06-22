"""
ASGI config for Smart Edu CRM project.
Uvicorn bilan asinxron ishlash uchun sozlangan.

Ishga tushirish:
    uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

# Django ASGI application
application = get_asgi_application()