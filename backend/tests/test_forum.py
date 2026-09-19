"""Phase 2B-A forum foundation tests."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.forum import models as fm
from app.modules.identity import models as m
from app.modules.identity import security as sec
from tests.conftest import auth_headers, register_payload


def _register(client, university, class_id, **overrides):
    resp = client.post("/api/v1/auth/register", json=register_payload(university.id, class_id, **overrides))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["token"], body["user"]["id"]


@pytest.fixture()
def class_a(db_session, university):
    cls = db_session.scalar(select(m.Class).where(m.Class.name == "CS-2024-A"))
    assert cls is not None
    return cls


@pytest.fixture()
def class_b(db_session, university):
    # Create second class for cross-class checks
    prog = db_session.scalar(select(m.Program).where(m.Program.code == "CS-BSC"))
    assert prog is not None
    batch = db_session.scalar(select(m.Batch).where(m.Batch.program_id == prog.id))
    # Reuse or create B
    existing = db_session.scalar(select(m.Class).where(m.Class.name == "CS-2024-B"))
    if existing:
        return existing
    cls = m.Class(batch_id=batch.id, name="CS-2024-B", code="B")
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(cls)
    return cls


def _make_class_rep(db_session, university, cls, email="rep2@test.edu"):
    user = m.User(email=email, password_hash=sec.hash_password("Rep1234!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(m.Profile(user_id=user.id, display_name="Rep2"))
    db_session.add(
        m.UniversityIdentity(
            user_id=user.id,
            university_id=university.id,
            role=m.Role.CLASS_REP,
            status=m.IdentityStatus.VERIFIED,
            student_no=f"REP-{uuid.uuid4().hex[:6]}",
            class_id=cls.id,
        )
    )
    db_session.commit()
    return user


def test_forum_proposal_and_approval(client, university, class_a):
    # Student in class A proposes forum
    token, _ = _register(client, university, str(class_a.id), email="stud1@test.edu", student_no="S-001")
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Exam Prep", "description": "Prep group"}, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    forum = resp.json()
    assert forum["status"] == "PENDING"
    forum_id = forum["id"]

    # Student can view own pending forum via direct fetch
    got = client.get(f"/api/v1/forums/{forum_id}", headers=auth_headers(token))
    assert got.status_code == 200
    assert got.json()["name"] == "Exam Prep"

    # Listing approved forums should be empty (pending not shown)
    lst = client.get(f"/api/v1/classes/{class_a.id}/forums", headers=auth_headers(token))
    assert lst.status_code == 200
    assert len(lst.json()) == 0

def test_approval_flow_with_rep(client, university, class_a, db_session):
    tok_student, _ = _register(client, university, str(class_a.id), email="stud_approve@test.edu", student_no="S-APR1")
    # propose
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Study Group", "description": "let study"}, headers=auth_headers(tok_student))
    assert resp.status_code == 201
    fid = resp.json()["id"]

    # create class rep
    rep_user = _make_class_rep(db_session, university, class_a, email="rep_approve@test.edu")
    # login rep
    login = client.post("/api/v1/auth/login", json={"email": "rep_approve@test.edu", "password": "Rep1234!"})
    assert login.status_code == 200, login.text
    tok_rep = login.json()["token"]

    # rep sees pending proposal
    pending = client.get(f"/api/v1/classes/{class_a.id}/forums/proposals", headers=auth_headers(tok_rep))
    assert pending.status_code == 200
    assert any(p["id"] == fid for p in pending.json())

    # approve
    rev = client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep))
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "APPROVED"

    # now listed as approved for student
    lst = client.get(f"/api/v1/classes/{class_a.id}/forums", headers=auth_headers(tok_student))
    assert lst.status_code == 200
    assert any(f["id"] == fid for f in lst.json())


def test_rejection(client, university, class_a, db_session):
    tok_student, _ = _register(client, university, str(class_a.id), email="stud_reject@test.edu", student_no="S-REJ1")
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Rejected Forum", "description": "x"}, headers=auth_headers(tok_student))
    fid = resp.json()["id"]

    rep_user = _make_class_rep(db_session, university, class_a, email="rep_reject@test.edu")
    tok_rep = client.post("/api/v1/auth/login", json={"email": "rep_reject@test.edu", "password": "Rep1234!"}).json()["token"]

    rev = client.patch(f"/api/v1/forums/{fid}/review", json={"status": "REJECTED"}, headers=auth_headers(tok_rep))
    assert rev.status_code == 200
    assert rev.json()["status"] == "REJECTED"

    # rejected not visible via class forums list
    lst = client.get(f"/api/v1/classes/{class_a.id}/forums", headers=auth_headers(tok_student))
    assert all(f["id"] != fid for f in lst.json())
    # creator can still fetch detail but sees rejected
    got = client.get(f"/api/v1/forums/{fid}", headers=auth_headers(tok_student))
    assert got.status_code == 200
    assert got.json()["status"] == "REJECTED"
    # cannot join rejected
    join = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_student), json={})
    assert join.status_code == 404


def test_class_rep_authorization(client, university, class_a, class_b, db_session):
    tok_student, _ = _register(client, university, str(class_a.id), email="stud_auth@test.edu", student_no="S-AUTH1")
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Auth Forum", "description": "x"}, headers=auth_headers(tok_student))
    fid = resp.json()["id"]

    # Another student in same class (not rep) cannot approve
    tok_other, _ = _register(client, university, str(class_a.id), email="other_auth@test.edu", student_no="S-AUTH2")
    rev = client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_other))
    assert rev.status_code == 403

    # Rep of other class cannot approve
    rep_b = _make_class_rep(db_session, university, class_b, email="rep_otherclass@test.edu")
    tok_rep_b = client.post("/api/v1/auth/login", json={"email": "rep_otherclass@test.edu", "password": "Rep1234!"}).json()["token"]
    rev2 = client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep_b))
    assert rev2.status_code == 403

    # Student cannot view proposals list
    lst = client.get(f"/api/v1/classes/{class_a.id}/forums/proposals", headers=auth_headers(tok_student))
    assert lst.status_code == 403


def test_cross_class_access_denial(client, university, class_a, class_b, db_session):
    tok_a, _ = _register(client, university, str(class_a.id), email="cross_a@test.edu", student_no="CROSS-A1")
    # create approved forum in class A via rep
    rep_a = _make_class_rep(db_session, university, class_a, email="rep_cross_a@test.edu")
    tok_rep_a = client.post("/api/v1/auth/login", json={"email": "rep_cross_a@test.edu", "password": "Rep1234!"}).json()["token"]
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Cross Forum", "description": "x"}, headers=auth_headers(tok_a))
    fid = resp.json()["id"]
    client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep_a))

    # Student in class B cannot list class A forums
    tok_b, _ = _register(client, university, str(class_b.id), email="cross_b@test.edu", student_no="CROSS-B1")
    lst = client.get(f"/api/v1/classes/{class_a.id}/forums", headers=auth_headers(tok_b))
    assert lst.status_code == 403
    # Cannot fetch forum by guessing ID
    got = client.get(f"/api/v1/forums/{fid}", headers=auth_headers(tok_b))
    assert got.status_code == 403
    # Cannot propose for another class
    prop = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Hack", "description": "y"}, headers=auth_headers(tok_b))
    assert prop.status_code == 403
    # Cannot join another class's forum
    join = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_b), json={})
    assert join.status_code == 403


def test_faculty_cannot_access_forums(client, university, class_a, db_session):
    # Faculty with no class
    fac = m.User(email="fac@test.edu", password_hash=sec.hash_password("Fac1234!"))
    db_session.add(fac)
    db_session.flush()
    db_session.add(m.Profile(user_id=fac.id, display_name="Fac"))
    db_session.add(m.UniversityIdentity(user_id=fac.id, university_id=university.id, role=m.Role.FACULTY, status=m.IdentityStatus.VERIFIED))
    db_session.commit()
    tok_fac = client.post("/api/v1/auth/login", json={"email": "fac@test.edu", "password": "Fac1234!"}).json()["token"]

    # Cannot list forums
    resp = client.get(f"/api/v1/classes/{class_a.id}/forums", headers=auth_headers(tok_fac))
    assert resp.status_code == 403
    # Cannot propose
    resp2 = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Fac Forum", "description": "x"}, headers=auth_headers(tok_fac))
    assert resp2.status_code == 403


def test_forum_membership_join_leave(client, university, class_a, db_session):
    tok, _ = _register(client, university, str(class_a.id), email="member@test.edu", student_no="MEM-1")
    rep = _make_class_rep(db_session, university, class_a, email="rep_member@test.edu")
    tok_rep = client.post("/api/v1/auth/login", json={"email": "rep_member@test.edu", "password": "Rep1234!"}).json()["token"]
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Member Forum", "description": "x"}, headers=auth_headers(tok))
    fid = resp.json()["id"]
    client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep))

    # Join
    join = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok), json={})
    assert join.status_code == 200, join.text
    assert join.json()["is_member"] is True
    assert join.json()["member_count"] == 1

    # Duplicate membership
    dup = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok), json={})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CONFLICT"

    # List joined
    joined = client.get("/api/v1/forums/joined", headers=auth_headers(tok))
    assert joined.status_code == 200
    assert any(f["id"] == fid for f in joined.json())

    # Fetch forum shows is_member
    got = client.get(f"/api/v1/forums/{fid}", headers=auth_headers(tok))
    assert got.json()["is_member"] is True

    # Leave via DELETE
    leave = client.delete(f"/api/v1/forums/{fid}/members/me", headers=auth_headers(tok))
    assert leave.status_code == 204

    # After leave, not member
    got2 = client.get(f"/api/v1/forums/{fid}", headers=auth_headers(tok))
    assert got2.json()["is_member"] is False
    assert got2.json()["member_count"] == 0

    # Leave again -> 404
    leave2 = client.delete(f"/api/v1/forums/{fid}/members/me", headers=auth_headers(tok))
    assert leave2.status_code == 404

    # Can re-join after leaving
    join2 = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok), json={})
    assert join2.status_code == 200


def test_cannot_join_pending_forum(client, university, class_a):
    tok, _ = _register(client, university, str(class_a.id), email="pendjoin@test.edu", student_no="PENDJOIN1")
    resp = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "Pending Join", "description": "x"}, headers=auth_headers(tok))
    fid = resp.json()["id"]
    join = client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok), json={})
    assert join.status_code == 404


def test_leave_via_post_alias(client, university, class_a, db_session):
    tok, _ = _register(client, university, str(class_a.id), email="leavepost@test.edu", student_no="LEAVEPOST1")
    rep = _make_class_rep(db_session, university, class_a, email="rep_leavepost@test.edu")
    tok_rep = client.post("/api/v1/auth/login", json={"email": "rep_leavepost@test.edu", "password": "Rep1234!"}).json()["token"]
    fid = client.post(f"/api/v1/classes/{class_a.id}/forums", json={"name": "LeavePost Forum", "description": "x"}, headers=auth_headers(tok)).json()["id"]
    client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep))
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok), json={})
    resp = client.post(f"/api/v1/forums/{fid}/leave", headers=auth_headers(tok))
    assert resp.status_code == 204
