"""
WSGI config for weats_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import base64

from django.core.wsgi import get_wsgi_application

credential = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if credential:
    with open("choosee.json", "wb") as f:
        f.write(base64.b64decode(credential))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weats_backend.settings')

application = get_wsgi_application()
