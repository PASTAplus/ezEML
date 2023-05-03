from contextlib import contextmanager
from webapp import db

from webapp.config import Config
import webapp.home.exceptions as exceptions


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
    except Exception:
        if not outer_session_active:
            session.rollback()
        # The point of the following is that in the event the collaborations database gets corrupted and
        # accesses to it are causing exceptions, we want to be able to disable the collaborations feature and
        # suppress the resulting exceptions so the rest of the site can continue to function. This would be a
        # temporary measure until we can figure out what's going on with the collaborations database.
        if Config.ENABLE_COLLABORATION_FEATURES:
            raise
