"""Identity tests: verification, auth, sessions, server-side authorization."""

from tests.conftest import auth_headers, register_payload


def test_register_auto_verifies_with_university_controlled_data(client, university, class_id):
    resp = client.post(
        "/api/v1/auth/register", json=register_payload(university.id, class_id)
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token"]
    assert body["user"]["email"] == "student@test.edu"
    assert body["user"]["profile"]["display_name"] == "Student"
    ident = body["user"]["identities"][0]
    assert ident["status"] == "VERIFIED"
    assert ident["role"] == "STUDENT"
    assert ident["student_no"] == "TEST-001"
    assert ident["class_name"] == "CS-2024-A"


def test_register_pending_on_wrong_enrollment_code(client, university, class_id):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(university.id, class_id, email="pending@test.edu", enrollment_code="WRONG"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["identities"][0]["status"] == "PENDING"


def test_register_pending_on_non_university_email(client, university, class_id):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(university.id, class_id, email="someone@gmail.com", student_no="TEST-002"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["identities"][0]["status"] == "PENDING"


def test_register_duplicate_email_conflicts(client, university, class_id):
    assert client.post("/api/v1/auth/register", json=register_payload(university.id, class_id)).status_code == 201
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(university.id, class_id, student_no="TEST-999"),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_register_duplicate_student_no_conflicts(client, university, class_id):
    assert client.post("/api/v1/auth/register", json=register_payload(university.id, class_id)).status_code == 201
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(university.id, class_id, email="other@test.edu"),
    )
    assert resp.status_code == 409


def test_register_weak_password_rejected(client, university, class_id):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(university.id, class_id, password="short"),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_logout_session_lifecycle(client, university, class_id):
    reg = client.post("/api/v1/auth/register", json=register_payload(university.id, class_id))
    assert reg.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": "student@test.edu", "password": "Student123!"})
    assert login.status_code == 200, login.text
    token = login.json()["token"]

    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "student@test.edu"

    bad_login = client.post("/api/v1/auth/login", json={"email": "student@test.edu", "password": "nope"})
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "AUTH_FAILED"

    assert client.post("/api/v1/auth/logout", headers=auth_headers(token)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth_headers(token)).status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_profile_update_is_student_controlled(client, university, class_id):
    reg = client.post("/api/v1/auth/register", json=register_payload(university.id, class_id))
    token = reg.json()["token"]

    patched = client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "New Name", "bio": "Hello"},
        headers=auth_headers(token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["display_name"] == "New Name"

    # Identity (verified, university-controlled) is untouched by profile edits.
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["identities"][0]["status"] == "VERIFIED"
    assert me["identities"][0]["student_no"] == "TEST-001"


def test_admin_can_approve_pending_identity(client, university, class_id, admin_user, db_session):

    pending = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            university.id, class_id, email="pending@test.edu", student_no="TEST-010", enrollment_code="WRONG"
        ),
    )
    assert pending.json()["user"]["identities"][0]["status"] == "PENDING"
    identity_id = pending.json()["user"]["identities"][0]["id"]

    # Admin login (seeded directly).
    from sqlalchemy import select
    from app.modules.identity import models as m

    admin = db_session.scalar(select(m.User).where(m.User.email == "admin@test.edu"))
    assert admin is not None
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.edu", "password": "Admin1234!"})
    assert login.status_code == 200, login.text
    admin_token = login.json()["token"]

    approved = client.patch(
        f"/api/v1/admin/identities/{identity_id}",
        json={"status": "VERIFIED"},
        headers=auth_headers(admin_token),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "VERIFIED"


def test_student_cannot_use_admin_endpoints(client, university, class_id):
    reg = client.post("/api/v1/auth/register", json=register_payload(university.id, class_id))
    token = reg.json()["token"]
    identity_id = reg.json()["user"]["identities"][0]["id"]

    resp = client.patch(
        f"/api/v1/admin/identities/{identity_id}",
        json={"role": "UNIVERSITY_ADMIN"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    listing = client.get(
        f"/api/v1/admin/identities?university_id={university.id}",
        headers=auth_headers(token),
    )
    assert listing.status_code == 403


def test_directory_is_public(client, university, class_id):
    unis = client.get("/api/v1/universities")
    assert unis.status_code == 200
    assert any(u["code"] == "TEST-U" for u in unis.json())

    classes = client.get(f"/api/v1/universities/{university.id}/classes")
    assert classes.status_code == 200
    assert classes.json()[0]["program_name"] == "BSc CS"
