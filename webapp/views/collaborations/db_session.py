from contextlib import contextmanager
from webapp import db


@contextmanager
def db_session(session=None, autocommit=True):
    if session is None:
        outer_session_active = False
        session = db.session
    else:
        outer_session_active = True
    try:
        yield session
        if autocommit and not outer_session_active:
            session.commit()
    except:
        if not outer_session_active:
            session.rollback()
        raise
