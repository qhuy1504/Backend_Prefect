# middlewares/upload.py
from flask import request
from werkzeug.datastructures import FileStorage
from functools import wraps

def upload_file(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        file = request.files.get('file') or request.files.get('avatar')
        request.uploaded_file = file if file and file.filename != '' else None
        
        if file and file.filename != '':
            kwargs['file'] = file
        else:
            kwargs['file'] = None  # Gắn None nếu không có file được gửi lên

        return func(*args, **kwargs)

    return wrapper
