"""Discussion tests: posts, comments, reactions, notifications, access control."""

import uuid
from sqlalchemy import select

from app.modules.forum import models as fm
from app.modules.identity import models as m
from app.modules.identity import security as sec
from tests.conftest import auth_headers, register_payload


def _register(client, university, class_id, **overrides):
    resp = client.post("/api/v1/auth/register", json=register_payload(university.id, class_id, **overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()["token"], resp.json()["user"]["id"]


def _make_class_rep(db_session, university, cls, email):
    u = m.User(email=email, password_hash=sec.hash_password("Rep1234!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(m.Profile(user_id=u.id, display_name="Rep"))
    db_session.add(
        m.UniversityIdentity(
            user_id=u.id, university_id=university.id, role=m.Role.CLASS_REP, status=m.IdentityStatus.VERIFIED, student_no=f"REP-{uuid.uuid4().hex[:6]}", class_id=cls.id
        )
    )
    db_session.commit()
    return u


def _approved_forum(client, db_session, university, cls, creator_token, name="Test Forum"):
    # propose
    resp = client.post(f"/api/v1/classes/{cls.id}/forums", json={"name": name, "description": "desc"}, headers=auth_headers(creator_token))
    assert resp.status_code == 201, resp.text
    fid = resp.json()["id"]
    # rep approves
    rep = _make_class_rep(db_session, university, cls, f"rep-{uuid.uuid4().hex[:4]}@test.edu")
    tok_rep = client.post("/api/v1/auth/login", json={"email": rep.email, "password": "Rep1234!"}).json()["token"]
    rev = client.patch(f"/api/v1/forums/{fid}/review", json={"status": "APPROVED"}, headers=auth_headers(tok_rep))
    assert rev.status_code == 200, rev.text
    # ensure creator is member (join if not already)
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(creator_token), json={})
    return fid, tok_rep


def _get_class(db_session, university, name="CS-2024-A"):
    return db_session.scalar(select(m.Class).where(m.Class.name == name))


def test_member_can_create_post(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="poster@test.edu", student_no="POST1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="Poster Forum")
    resp = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "Hello world"}, headers=auth_headers(tok))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["content"] == "Hello world"
    assert body["like_count"] == 0
    assert body["comment_count"] == 0
    assert body["is_own"] is True


def test_non_member_cannot_create_post(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_creator, _ = _register(client, university, str(cls.id), email="creator@test.edu", student_no="NM1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_creator, name="NM Forum")
    # another student same class but not joined
    tok_other, _ = _register(client, university, str(cls.id), email="nonmember@test.edu", student_no="NM2")
    resp = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "hijack"}, headers=auth_headers(tok_other))
    assert resp.status_code == 403


def test_cross_class_cannot_create_post(client, university, db_session):
    cls_a = _get_class(db_session, university)
    # create second class
    prog = db_session.scalar(select(m.Program).where(m.Program.code == "CS-BSC"))
    batch = db_session.scalar(select(m.Batch).where(m.Batch.program_id == prog.id))
    cls_b = db_session.scalar(select(m.Class).where(m.Class.name == "CS-2024-B"))
    if cls_b is None:
        cls_b = m.Class(batch_id=batch.id, name="CS-2024-B", code="B")
        db_session.add(cls_b); db_session.commit(); db_session.refresh(cls_b)
    tok_a, _ = _register(client, university, str(cls_a.id), email="cross-a-post@test.edu", student_no="CROSSPOSTA1")
    fid, _ = _approved_forum(client, db_session, university, cls_a, tok_a, name="CrossPost Forum")
    tok_b, _ = _register(client, university, str(cls_b.id), email="cross-b-post@test.edu", student_no="CROSSPOSTB1")
    resp = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "cross"}, headers=auth_headers(tok_b))
    assert resp.status_code == 403


def test_pending_forum_cannot_receive_posts(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="pendposter@test.edu", student_no="PENDPOST1")
    resp = client.post(f"/api/v1/classes/{cls.id}/forums", json={"name": "Pend Forum", "description": "x"}, headers=auth_headers(tok))
    fid = resp.json()["id"]
    # try post without approval
    r2 = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "should fail"}, headers=auth_headers(tok))
    assert r2.status_code == 404


def test_rejected_forum_cannot_receive_posts(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="rejposter@test.edu", student_no="REJPOST1")
    resp = client.post(f"/api/v1/classes/{cls.id}/forums", json={"name": "Rej Forum", "description": "x"}, headers=auth_headers(tok))
    fid = resp.json()["id"]
    rep = _make_class_rep(db_session, university, cls, "rep-rej@test.edu")
    tok_rep = client.post("/api/v1/auth/login", json={"email": "rep-rej@test.edu", "password": "Rep1234!"}).json()["token"]
    client.patch(f"/api/v1/forums/{fid}/review", json={"status": "REJECTED"}, headers=auth_headers(tok_rep))
    r2 = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "no"}, headers=auth_headers(tok))
    assert r2.status_code == 404


def test_user_can_delete_own_post(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="delown@test.edu", student_no="DELOWN1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="DelOwn Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "to delete"}, headers=auth_headers(tok)).json()["id"]
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}", headers=auth_headers(tok))
    assert del_resp.status_code == 204
    get = client.get(f"/api/v1/forums/{fid}/posts/{pid}", headers=auth_headers(tok))
    assert get.status_code == 404


def test_user_cannot_delete_another_post(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_a, _ = _register(client, university, str(cls.id), email="owner@test.edu", student_no="OWNER1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_a, name="DelOther Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "owned"}, headers=auth_headers(tok_a)).json()["id"]
    tok_b, _ = _register(client, university, str(cls.id), email="otherdel@test.edu", student_no="OTHERDEL1")
    # join other
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_b), json={})
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}", headers=auth_headers(tok_b))
    assert del_resp.status_code == 403


def test_rep_can_moderate_own_class(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_student, _ = _register(client, university, str(cls.id), email="studmod@test.edu", student_no="STUDMOD1")
    fid, tok_rep = _approved_forum(client, db_session, university, cls, tok_student, name="Mod Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "moderatable"}, headers=auth_headers(tok_student)).json()["id"]
    # rep deletes
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}", headers=auth_headers(tok_rep))
    assert del_resp.status_code == 204


def test_rep_cannot_moderate_another_class(client, university, db_session):
    cls_a = _get_class(db_session, university)
    prog = db_session.scalar(select(m.Program).where(m.Program.code == "CS-BSC"))
    batch = db_session.scalar(select(m.Batch).where(m.Batch.program_id == prog.id))
    cls_b = db_session.scalar(select(m.Class).where(m.Class.name == "CS-2024-B"))
    if cls_b is None:
        cls_b = m.Class(batch_id=batch.id, name="CS-2024-B", code="B"); db_session.add(cls_b); db_session.commit(); db_session.refresh(cls_b)
    tok_a, _ = _register(client, university, str(cls_a.id), email="mod-a@test.edu", student_no="MODA1")
    fid, _ = _approved_forum(client, db_session, university, cls_a, tok_a, name="ModOther Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "hello"}, headers=auth_headers(tok_a)).json()["id"]
    rep_b = _make_class_rep(db_session, university, cls_b, "rep-mod-other@test.edu")
    tok_rep_b = client.post("/api/v1/auth/login", json={"email": "rep-mod-other@test.edu", "password": "Rep1234!"}).json()["token"]
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}", headers=auth_headers(tok_rep_b))
    assert del_resp.status_code == 403


def test_member_can_comment(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="commenter@test.edu", student_no="COMM1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="Comment Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "post for comment"}, headers=auth_headers(tok)).json()["id"]
    resp = client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "nice!"}, headers=auth_headers(tok))
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"] == "nice!"
    # list
    lst = client.get(f"/api/v1/forums/{fid}/posts/{pid}/comments", headers=auth_headers(tok))
    assert lst.status_code == 200
    assert lst.json()["total"] == 1


def test_non_member_cannot_comment(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_creator, _ = _register(client, university, str(cls.id), email="creator-comm@test.edu", student_no="CCRE1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_creator, name="CommNM Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "p"}, headers=auth_headers(tok_creator)).json()["id"]
    tok_other, _ = _register(client, university, str(cls.id), email="nonmemcomm@test.edu", student_no="NMC2")
    resp = client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "hack"}, headers=auth_headers(tok_other))
    assert resp.status_code == 403


def test_user_can_delete_own_comment(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="delcomm@test.edu", student_no="DELCOMM1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="DelComm Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "p"}, headers=auth_headers(tok)).json()["id"]
    cid = client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "c"}, headers=auth_headers(tok)).json()["id"]
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}/comments/{cid}", headers=auth_headers(tok))
    assert del_resp.status_code == 204


def test_user_cannot_delete_other_comment(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_a, _ = _register(client, university, str(cls.id), email="comm-owner@test.edu", student_no="COMMOWN1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_a, name="CommOther Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "p"}, headers=auth_headers(tok_a)).json()["id"]
    cid = client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "c"}, headers=auth_headers(tok_a)).json()["id"]
    tok_b, _ = _register(client, university, str(cls.id), email="comm-other@test.edu", student_no="COMMOTH2")
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_b), json={})
    del_resp = client.delete(f"/api/v1/forums/{fid}/posts/{pid}/comments/{cid}", headers=auth_headers(tok_b))
    assert del_resp.status_code == 403


def test_like_and_unlike(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="liker@test.edu", student_no="LIKER1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="Like Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "like me"}, headers=auth_headers(tok)).json()["id"]
    # need another user to like
    tok_other, _ = _register(client, university, str(cls.id), email="liker2@test.edu", student_no="LIKER2")
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_other), json={})
    like = client.post(f"/api/v1/forums/{fid}/posts/{pid}/like", headers=auth_headers(tok_other), json={})
    assert like.status_code == 200
    assert like.json()["like_count"] == 1
    # duplicate like should 409
    dup = client.post(f"/api/v1/forums/{fid}/posts/{pid}/like", headers=auth_headers(tok_other), json={})
    assert dup.status_code == 409
    # like count in post list
    lst = client.get(f"/api/v1/forums/{fid}/posts", headers=auth_headers(tok_other))
    assert lst.json()["items"][0]["like_count"] == 1
    assert lst.json()["items"][0]["liked_by_me"] is True
    # unlike
    unlike = client.delete(f"/api/v1/forums/{fid}/posts/{pid}/like", headers=auth_headers(tok_other))
    assert unlike.status_code == 200
    assert unlike.json()["like_count"] == 0
    lst2 = client.get(f"/api/v1/forums/{fid}/posts", headers=auth_headers(tok_other))
    assert lst2.json()["items"][0]["like_count"] == 0
    assert lst2.json()["items"][0]["liked_by_me"] is False


def test_faculty_blocked_from_discussion(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_student, _ = _register(client, university, str(cls.id), email="facblock-stud@test.edu", student_no="FACB1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_student, name="FacBlock Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "student post"}, headers=auth_headers(tok_student)).json()["id"]
    fac = m.User(email="fac-disc@test.edu", password_hash=sec.hash_password("Fac1234!"))
    db_session.add(fac); db_session.flush()
    db_session.add(m.Profile(user_id=fac.id, display_name="Fac"))
    db_session.add(m.UniversityIdentity(user_id=fac.id, university_id=university.id, role=m.Role.FACULTY, status=m.IdentityStatus.VERIFIED))
    db_session.commit()
    tok_fac = client.post("/api/v1/auth/login", json={"email": "fac-disc@test.edu", "password": "Fac1234!"}).json()["token"]
    r1 = client.get(f"/api/v1/forums/{fid}/posts", headers=auth_headers(tok_fac))
    assert r1.status_code == 403
    r2 = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "fac post"}, headers=auth_headers(tok_fac))
    assert r2.status_code == 403
    r3 = client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "fac comment"}, headers=auth_headers(tok_fac))
    assert r3.status_code == 403


def test_notification_on_comment(client, university, db_session):
    cls = _get_class(db_session, university)
    tok_author, _ = _register(client, university, str(cls.id), email="notif-author@test.edu", student_no="NOTIFA1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok_author, name="Notif Forum")
    pid = client.post(f"/api/v1/forums/{fid}/posts", json={"content": "notify me"}, headers=auth_headers(tok_author)).json()["id"]
    tok_commenter, _ = _register(client, university, str(cls.id), email="notif-commenter@test.edu", student_no="NOTIFC1")
    client.post(f"/api/v1/forums/{fid}/join", headers=auth_headers(tok_commenter), json={})
    client.post(f"/api/v1/forums/{fid}/posts/{pid}/comments", json={"content": "hello"}, headers=auth_headers(tok_commenter))
    notifs = client.get("/api/v1/notifications", headers=auth_headers(tok_author))
    assert notifs.status_code == 200
    assert any(n["type"] == "COMMENT_ON_POST" for n in notifs.json())
    # mark read
    nid = [n for n in notifs.json() if n["type"] == "COMMENT_ON_POST"][0]["id"]
    read = client.patch(f"/api/v1/notifications/{nid}/read", headers=auth_headers(tok_author))
    assert read.status_code == 200
    assert read.json()["is_read"] is True


def test_post_listing_pagination_and_counts(client, university, db_session):
    cls = _get_class(db_session, university)
    tok, _ = _register(client, university, str(cls.id), email="pag@test.edu", student_no="PAG1")
    fid, _ = _approved_forum(client, db_session, university, cls, tok, name="Pag Forum")
    for i in range(5):
        client.post(f"/api/v1/forums/{fid}/posts", json={"content": f"post {i}"}, headers=auth_headers(tok))
    lst = client.get(f"/api/v1/forums/{fid}/posts?limit=2&offset=0", headers=auth_headers(tok))
    assert lst.status_code == 200
    assert lst.json()["total"] == 5
    assert len(lst.json()["items"]) == 2
    # pagination second page also returns 2 items, distinct from first
    lst2 = client.get(f"/api/v1/forums/{fid}/posts?limit=2&offset=2", headers=auth_headers(tok))
    assert len(lst2.json()["items"]) == 2
    # ensure all contents appear across pages
    all_contents = {c["content"] for c in lst.json()["items"]} | {c["content"] for c in lst2.json()["items"]}
    assert len(all_contents) == 4
    # check newest first by comparing total ordering: fetch all at once and verify count
    full = client.get(f"/api/v1/forums/{fid}/posts?limit=5&offset=0", headers=auth_headers(tok))
    assert len(full.json()["items"]) == 5
