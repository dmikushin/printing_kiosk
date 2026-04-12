import os

# DEBUG = True

DATABASE_PATH = os.path.join(os.getcwd(), './data/sqlite.db')
DATABASE_URL = 'sqlite:///{}'.format(DATABASE_PATH)

PRINT_COMMAND = 'lp-brother-dcp1510'

MAX_CONTENT_LENGTH = 128 * 1024 * 1024 # 128 MB
BASE_UPLOAD_FOLDER = './data/uploads'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg'])

SECRET_KEY = "3d2a29a5641fcfc4d5ed2be69af8391c"

