import hashlib

def sha256_file(fobj, chunk_size=8192):
    h = hashlib.sha256()
    for chunk in iter(lambda: fobj.read(chunk_size), b""):
        h.update(chunk)
    fobj.seek(0)
    return h.hexdigest()
