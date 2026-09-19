"""Profile/directory tests: retrieval, updates, identity protection, visibility."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.identity import models as m
from app.modules.identity import security as sec
from tests.conftest import auth_headers, register_payload


def _register(client, university_id, class_id, **overrides):
    resp = client.post("/api/v1/auth/register", json=register_payload(university_id, class_id, **overrides))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["token"], body["user"]["id"]


@pytest.fixture()
def student(client, university, class_id):
    token, user_id = _register(client, university.id, class_id)
    return token, user_id


@pytest.fixture()
def other_university(db_session):
    """A second university so cross-university visibility can be tested."""
    uni = m.University(
        name="Other University",
        code="OTHER-U",
        email_domain="other.edu",
        enrollment_code_hash=sec.hash_password("OTHER123"),
    )
    db_session.add(uni)
    db_session.flush()
    dept = m.Department(university_id=uni.id, name="Math", code="MATH")
    db_session.add(dept)
    db_session.flush()
    prog = m.Program(department_id=dept.id, name="BSc Math", code="MATH-BSC", degree_level="BSc")
    db_session.add(prog)
    db_session.flush()
    batch = m.Batch(program_id=prog.id, name="2024", start_year=2024)
    db_session.add(batch)
    db_session.flush()
    cls = m.Class(batch_id=batch.id, name="MATH-2024-A", code="A")
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(uni)
    return uni


def test_get_my_profile_with_academic_context(client, student):
    token, _ = student
    resp = client.get("/api/v1/profile/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["skills"] == []
    assert body["role"] == "STUDENT"
    assert body["verification_status"] == "VERIFIED"
    ctx = body["academic_context"]
    assert ctx["university"]["name"] == "Test University"
    assert ctx["department"]["name"] == "CS"
    assert ctx["program"]["name"] == "BSc CS"
    assert ctx["batch"]["name"] == "2024"
    assert ctx["class"]["name"] == "CS-2024-A"


def test_update_my_profile_skills_interests_links(client, student):
    token, _ = student
    resp = client.patch(
        "/api/v1/profile/me",
        json={
            "headline": "  CS undergrad  ",
            "bio": "Hello world",
            "github_url": "https://github.com/student",
            "career_interests": "Backend engineering",
            "skills": ["Python", " python ", "SQL"],
            "interests": ["Robotics"],
            "hobbies": ["Chess", "robotics"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["headline"] == "CS undergrad"
    assert body["github_url"] == "https://github.com/student"
    assert body["skills"] == ["python", "sql"]  # normalized, deduped, sorted
    kinds = {i["name"]: i["kind"] for i in body["interests"]}
    assert kinds == {"robotics": "INTEREST", "chess": "HOBBY"}

    # Replacement semantics: second write replaces the skill set.
    resp2 = client.patch("/api/v1/profile/me", json={"skills": ["go"]}, headers=auth_headers(token))
    assert resp2.json()["skills"] == ["go"]


def test_update_profile_requires_auth(client):
    assert client.patch("/api/v1/profile/me", json={"bio": "x"}).status_code == 401
    assert client.get("/api/v1/profile/me").status_code == 401


def test_verified_identity_fields_rejected_and_untouched(client, student):
    token, user_id = student
    resp = client.patch(
        "/api/v1/profile/me",
        json={"student_no": "HACK-1", "role": "UNIVERSITY_ADMIN", "status": "VERIFIED"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    ident = me["identities"][0]
    assert ident["student_no"] == "TEST-001"
    assert ident["role"] == "STUDENT"


def test_invalid_url_and_limits_rejected(client, student):
    token, _ = student
    bad_url = client.patch(
        "/api/v1/profile/me", json={"github_url": "not-a-url"}, headers=auth_headers(token)
    )
    assert bad_url.status_code == 422

    too_many = client.patch(
        "/api/v1/profile/me", json={"skills": [f"s{i}" for i in range(25)]}, headers=auth_headers(token)
    )
    assert too_many.status_code == 422


def test_public_profile_same_university(client, student):
    token, user_id = student
    resp = client.get(f"/api/v1/profile/users/{user_id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["role"] == "STUDENT"
    assert "email" not in body
    assert "student_no" not in body


def test_public_profile_hidden_across_universities(client, student, other_university, db_session):
    token, user_id = student
    other_cls = db_session.scalar(select(m.Class).where(m.Class.name == "MATH-2024-A"))
    outsider_token, outsider_id = _register(
        client,
        other_university.id,
        str(other_cls.id),
        email="outsider@other.edu",
        student_no="OUT-001",
        enrollment_code="OTHER123",
    )
    # Our student cannot see the outsider's profile...
    resp = client.get(f"/api/v1/profile/users/{outsider_id}", headers=auth_headers(token))
    assert resp.status_code == 403
    # ...and the outsider cannot see ours.
    resp2 = client.get(f"/api/v1/profile/users/{user_id}", headers=auth_headers(outsider_token))
    assert resp2.status_code == 403


def test_public_profile_unknown_user_404(client, student):
    token, _ = student
    resp = client.get(f"/api/v1/profile/users/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


def test_structure_and_class_pages(client, student, university, class_id):
    token, _ = student
    struct = client.get(
        f"/api/v1/directory/universities/{university.id}/structure", headers=auth_headers(token)
    )
    assert struct.status_code == 200, struct.text
    depts = struct.json()["departments"]
    assert depts[0]["programs"][0]["batches"][0]["classes"][0]["member_count"] >= 1

    detail = client.get(f"/api/v1/directory/classes/{class_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["program"]["name"] == "BSc CS"
    assert detail.json()["member_count"] >= 1

    members = client.get(
        f"/api/v1/directory/classes/{class_id}/members?limit=10&offset=0", headers=auth_headers(token)
    )
    assert members.status_code == 200
    assert members.json()["total"] >= 1
    assert members.json()["limit"] == 10

    over_limit = client.get(
        f"/api/v1/directory/classes/{class_id}/members?limit=101", headers=auth_headers(token)
    )
    assert over_limit.status_code == 422


def test_structure_requires_same_university(client, other_university, university, student):
    token, _ = student
    resp = client.get(
        f"/api/v1/directory/universities/{other_university.id}/structure", headers=auth_headers(token)
    )
    assert resp.status_code == 403


def test_admin_structure_crud_and_authorization(client, university, admin_user, student, db_session):
    admin_token = client.post(
        "/api/v1/auth/login", json={"email": "admin@test.edu", "password": "Admin1234!"}
    ).json()["token"]
    student_token, _ = student

    # Student is forbidden from managing structure.
    forbidden = client.post(
        f"/api/v1/admin/structure/universities/{university.id}/departments",
        json={"name": "Physics", "code": "PHYS"},
        headers=auth_headers(student_token),
    )
    assert forbidden.status_code == 403

    # Admin creates department → program → batch → class.
    dept = client.post(
        f"/api/v1/admin/structure/universities/{university.id}/departments",
        json={"name": "Physics", "code": "PHYS"},
        headers=auth_headers(admin_token),
    )
    assert dept.status_code == 201, dept.text
    dept_id = dept.json()["id"]

    dup = client.post(
        f"/api/v1/admin/structure/universities/{university.id}/departments",
        json={"name": "Physics again", "code": "PHYS"},
        headers=auth_headers(admin_token),
    )
    assert dup.status_code == 409

    prog = client.post(
        f"/api/v1/admin/structure/departments/{dept_id}/programs",
        json={"name": "BSc Physics", "code": "PHYS-BSC", "degree_level": "BSc"},
        headers=auth_headers(admin_token),
    )
    assert prog.status_code == 201, prog.text

    batch = client.post(
        f"/api/v1/admin/structure/programs/{prog.json()['id']}/batches",
        json={"name": "2025", "start_year": 2025},
        headers=auth_headers(admin_token),
    )
    assert batch.status_code == 201, batch.text

    cls = client.post(
        f"/api/v1/admin/structure/batches/{batch.json()['id']}/classes",
        json={"name": "PHYS-2025-A", "code": "A"},
        headers=auth_headers(admin_token),
    )
    assert cls.status_code == 201, cls.text

    renamed = client.patch(
        f"/api/v1/admin/structure/department/{dept_id}",
        json={"name": "Department of Physics"},
        headers=auth_headers(admin_token),
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Department of Physics"

    # New structure is visible in the hierarchy.
    struct = client.get(
        f"/api/v1/directory/universities/{university.id}/structure", headers=auth_headers(admin_token)
    )
    assert any(d["name"] == "Department of Physics" for d in struct.json()["departments"])
