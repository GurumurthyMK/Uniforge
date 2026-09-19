"""SQLAlchemy declarative base. Domain models will import Base from here."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
