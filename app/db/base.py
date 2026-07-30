from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base.

    NOTE: app.main never calls Base.metadata.create_all()/drop_all()
    against the database. Every table here already exists in NRDB
    (Django-owned tables like auth_user, program, ...) or is created
    manually by running the scripts under sql/ (payment_order,
    refresh_token, ...). This keeps schema changes explicit and
    reviewable instead of happening implicitly at app startup.
    """
