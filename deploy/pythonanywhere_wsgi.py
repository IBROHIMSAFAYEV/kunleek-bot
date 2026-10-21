# PythonAnywhere: Web -> WSGI configuration file ichidagi hamma narsani o'chirib, shuni qo'ying.
# USERNAME ni o'z login'ingizga almashtiring.
import os
import sys

path = "/home/USERNAME/kunleek_bot"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
