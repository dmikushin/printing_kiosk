#!/usr/bin/env python
import os
import sys

from config import DATABASE_PATH, BASE_UPLOAD_FOLDER
from simple_print_server import app
from simple_print_server.database import init_db


def ensure_db_and_dirs():
    if not os.path.exists(DATABASE_PATH):
        print("Creating database")
    else:
        print("Running idempotent schema migrations")
    init_db()  # idempotent: create_all + ALTER TABLE for new columns
    if not os.path.exists(BASE_UPLOAD_FOLDER):
        print("Creating upload folder")
        os.makedirs(BASE_UPLOAD_FOLDER)


if __name__ == "__main__":
    ensure_db_and_dirs()
    host = '0.0.0.0'
    if len(sys.argv) > 1:
        host = sys.argv[1]
    app.run(host=host)
