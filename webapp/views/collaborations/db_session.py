"""
This module provides a context manager for database sessions. It makes it possible for a sequence of calls to the
database to be handled by a single session and thereby treated as a single transaction, which will properly be
committed or rolled back as a unit.

Various functions in collaborations.py use this context manager. The functions have a parameter named session, which
is a SQLAlchemy session object. If the caller passes in a session object, then the context manager will use that
session object. If the caller does not pass in a session object, then the context manager will create a session.

So a function that uses the context manager might look like this:

    def get_something_from_the_database(..., session=None):
        with db_session(session) as session:
            # Do something with the session

The "with db_session(session) as session:" statement is using this context manager.
"""

from contextlib import contextmanager
from webapp import db

from webapp.config import Config


@contextmanager
def db_session(session=None, autocommit=True):
    if session is None:
        # No session was provided, so create one
        outer_session_active = False
        session = db.session
    else:
        outer_session_active = True
    try:
        yield session
        if autocommit and not outer_session_active:
            # We created the session, so we commit it
            session.commit()
    except Exception:
        if not outer_session_active:
            # We created the session, so we roll it back
            session.rollback()
        # The point of the following is that we want the ability to suppress exceptions in emergency situations
        # where the collaborations database is corrupted and we want to disable the collaborations feature so it
        # doesn't cause exceptions in other parts of the site, so the rest of the site can continue to function.
        # This would be a temporary measure until we can figure out what's going on with the collaborations database.
        if Config.ENABLE_COLLABORATION_FEATURES:
            raise
