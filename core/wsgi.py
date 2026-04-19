# wsgi.py
import os
import sys

# Ajouter le chemin du projet
path = '/home/luminaireads/Lumina'  # À adapter avec ton username
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()