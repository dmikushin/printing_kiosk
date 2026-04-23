import os

# DEBUG = True

DATABASE_PATH = os.path.join(os.getcwd(), './data/sqlite.db')
DATABASE_URL = 'sqlite:///{}'.format(DATABASE_PATH)

PRINT_COMMAND = 'lp-brother-dcp1510'

MAX_CONTENT_LENGTH = 128 * 1024 * 1024 # 128 MB
BASE_UPLOAD_FOLDER = './data/uploads'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg'])

SECRET_KEY = "3d2a29a5641fcfc4d5ed2be69af8391c"

# URL of the printing-kiosk-api gateway on the kiosk machine. When Flask
# runs on the dev box, this should point at the SSH-forwarded local port
# (e.g. `ssh -L 8080:127.0.0.1:8080 printing_kiosk`). On the kiosk itself
# it's just the API's own bind address.
KIOSK_API_URL = os.environ.get('KIOSK_API_URL', 'http://127.0.0.1:8080')

