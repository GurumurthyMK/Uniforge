"""Test setup: SQLite in-memory DB with get_db overridden.

SQLite keeps unit tests independent of Postgres. Production parity for
Postgres-specific behavior is covered by running migrations + seed against
the real database in the verification step.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.identity import models as m
from app.modules.identity import security as sec


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def university(db_session):
    """Minimal verified structure: university + dept + program + batch + class."""
    uni = m.University(
        name="Test University",
        code="TEST-U",
        email_domain="test.edu",
        enrollment_code_hash=sec.hash_password("CODE123"),
    )
    db_session.add(uni)
    db_session.flush()
    dept = m.Department(university_id=uni.id, name="CS", code="CS")
    db_session.add(dept)
    db_session.flush()
    prog = m.Program(department_id=dept.id, name="BSc CS", code="CS-BSC", degree_level="BSc")
    db_session.add(prog)
    db_session.flush()
    batch = m.Batch(program_id=prog.id, name="2024", start_year=2024)
    db_session.add(batch)
    db_session.flush()
    cls = m.Class(batch_id=batch.id, name="CS-2024-A", code="A")
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(uni)
    return uni


@pytest.fixture()
def class_id(db_session, university):
    cls = db_session.query(m.Class).first()
    assert cls is not None
    return str(cls.id)


@pytest.fixture()
def admin_user(db_session, university):
    """Verified university admin for authorization tests."""
    user = m.User(email="admin@test.edu", password_hash=sec.hash_password("Admin1234!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        m.UniversityIdentity(
            user_id=user.id,
            university_id=university.id,
            role=m.Role.UNIVERSITY_ADMIN,
            status=m.IdentityStatus.VERIFIED,
        )
    )
    db_session.add(m.Profile(user_id=user.id, display_name="Admin"))
    db_session.commit()
    return user


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_payload(university_id: uuid.UUID, class_id: str, **overrides):
    payload = {
        "email": "student@test.edu",
        "password": "Student123!",
        "display_name": "Student",
        "university_id": str(university_id),
        "class_id": class_id,
        "student_no": "TEST-001",
        "enrollment_code": "CODE123",
    }
    payload.update(overrides)
    return payload
