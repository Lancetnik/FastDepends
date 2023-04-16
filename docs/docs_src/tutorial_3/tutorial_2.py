def dependency():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()
