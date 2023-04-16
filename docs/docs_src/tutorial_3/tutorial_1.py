def dependency():
    db = DBSession()
    yield db
    db.close()
