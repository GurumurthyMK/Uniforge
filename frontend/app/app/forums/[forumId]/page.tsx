"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  createComment,
  createPost,
  deleteComment,
  deletePost,
  fetchForum,
  likePost,
  unlikePost,
  listComments,
  listPosts,
  type Comment,
  type Forum,
  type Post,
} from "@/lib/api";
import { EmptyState, Loading, inputClass, buttonPrimaryClass, buttonSecondaryClass } from "@/components/ui";

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function LikeButton({ post, forumId, token, onUpdate }: { post: Post; forumId: string; token: string; onUpdate: (liked: boolean, count: number) => void }) {
  const [busy, setBusy] = useState(false);
  const handle = async () => {
    setBusy(true);
    try {
      if (post.liked_by_me) {
        const res = await unlikePost(token, forumId, post.id);
        onUpdate(false, res.like_count);
      } else {
        const res = await likePost(token, forumId, post.id);
        onUpdate(true, res.like_count);
      }
    } catch {
      // noop
    } finally {
      setBusy(false);
    }
  };
  return (
    <button disabled={busy} onClick={handle} className={`text-xs ${post.liked_by_me ? "text-rose-600 font-medium" : "text-zinc-500"} hover:underline disabled:opacity-40`}>
      {post.liked_by_me ? "♥" : "♡"} {post.like_count} {post.like_count === 1 ? "like" : "likes"}
    </button>
  );
}

function CommentSection({ forumId, post, token }: { forumId: string; post: Post; token: string }) {
  const [open, setOpen] = useState(false);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await listComments(token, forumId, post.id, 50, 0);
      setComments(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load comments.");
    }
  }, [token, forumId, post.id]);

  useEffect(() => {
    if (open && comments === null) void load();
  }, [open, comments, load]);

  const handleCreate = async () => {
    if (!content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const c = await createComment(token, forumId, post.id, content.trim());
      setComments((prev) => (prev ? [...prev, c] : [c]));
      setContent("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add comment.");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (cid: string) => {
    try {
      await deleteComment(token, forumId, post.id, cid);
      setComments((prev) => (prev ? prev.filter((c) => c.id !== cid) : prev));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete.");
    }
  };

  return (
    <div className="mt-3">
      <button onClick={() => setOpen((o) => !o)} className="text-xs text-zinc-600 hover:underline">
        {open ? "Hide" : "View"} comments {post.comment_count > 0 ? `(${post.comment_count})` : ""}
      </button>
      {open && (
        <div className="mt-3 rounded border bg-zinc-50 p-3 space-y-3">
          {error && <p className="text-xs text-red-700">{error}</p>}
          {comments === null ? (
            <p className="text-xs text-zinc-500">Loading…</p>
          ) : comments.length === 0 ? (
            <p className="text-xs text-zinc-500">No comments yet.</p>
          ) : (
            <ul className="space-y-2">
              {comments.map((c) => (
                <li key={c.id} className="flex justify-between gap-2 text-sm bg-white rounded border p-2">
                  <div>
                    <p className="text-xs text-zinc-500">{c.author_display_name ?? "Unknown"} · {timeAgo(c.created_at)}</p>
                    <p className="mt-1 whitespace-pre-wrap">{c.content}</p>
                  </div>
                  {c.is_own && (
                    <button onClick={() => handleDelete(c.id)} className="text-xs text-red-600 hover:underline shrink-0">Delete</button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <input className={inputClass} placeholder="Write a comment…" value={content} onChange={(e) => setContent(e.target.value)} maxLength={2000} />
            <button disabled={busy || !content.trim()} onClick={handleCreate} className={buttonPrimaryClass}>Post</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ForumPageInner({ forumId }: { forumId: string }) {
  const auth = useAuth();
  const token = auth.status === "authenticated" ? auth.token : null;
  const [forum, setForum] = useState<Forum | null>(null);
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [composer, setComposer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const loadForum = useCallback(async () => {
    if (!token) return;
    try {
      const f = await fetchForum(token, forumId);
      setForum(f);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 403 || e.status === 404)) setForbidden(true);
      setError(e instanceof ApiError ? e.message : "Failed to load forum.");
    }
  }, [token, forumId]);

  const loadPosts = useCallback(async () => {
    if (!token) return;
    try {
      const res = await listPosts(token, forumId, limit, offset);
      setPosts(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 403 || e.status === 404)) setForbidden(true);
      setError(e instanceof ApiError ? e.message : "Failed to load posts.");
    }
  }, [token, forumId, offset]);

  useEffect(() => { void loadForum(); }, [loadForum]);
  useEffect(() => { void loadPosts(); }, [loadPosts]);

  const handleCreate = async () => {
    if (!token || !composer.trim()) return;
    setBusy(true);
    setPostError(null);
    try {
      const p = await createPost(token, forumId, composer.trim());
      setPosts((prev) => (prev ? [p, ...prev] : [p]));
      setTotal((t) => t + 1);
      setComposer("");
    } catch (e) {
      setPostError(e instanceof ApiError ? e.message : "Failed to post.");
    } finally {
      setBusy(false);
    }
  };

  const handleDeletePost = async (pid: string) => {
    if (!token) return;
    try {
      await deletePost(token, forumId, pid);
      setPosts((prev) => (prev ? prev.filter((p) => p.id !== pid) : prev));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) {
      setPostError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  };

  const handleLikeUpdate = (pid: string, liked: boolean, count: number) => {
    setPosts((prev) => prev ? prev.map((p) => p.id === pid ? { ...p, liked_by_me: liked, like_count: count } : p) : prev);
  };

  if (auth.status !== "authenticated") return null;
  if (forbidden) return <EmptyState title="Access denied" hint="You must be a member of this forum's class and have joined the forum to view discussion." />;
  if (error && !forum) return <p className="text-sm text-red-700">{error}</p>;
  if (!forum || posts === null) return <Loading label="Loading forum…" />;

  const pageCount = Math.max(1, Math.ceil(total / limit));
  const curPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/app/class" className="text-xs text-zinc-500 hover:underline">← Back to class</Link>
        <p className="text-xs uppercase tracking-wide text-zinc-500 mt-2">{forum.class_id.slice(0, 8)}</p>
        <h1 className="text-2xl font-bold">{forum.name}</h1>
        {forum.description && <p className="text-sm text-zinc-600 mt-1">{forum.description}</p>}
        <p className="text-xs text-zinc-500 mt-2">{forum.member_count} members · {forum.status}</p>
      </div>

      {!forum.is_member && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          You are viewing this forum but you haven&apos;t joined it. Join from the class page to post.
        </div>
      )}

      <section className="rounded border bg-white p-4">
        <h2 className="text-sm font-medium">Write something…</h2>
        <textarea className={inputClass + " mt-2"} rows={3} placeholder="Share an update, ask a question…" value={composer} onChange={(e) => setComposer(e.target.value)} maxLength={5000} />
        {postError && <p className="mt-2 text-xs text-red-700">{postError}</p>}
        <button disabled={busy || !composer.trim()} onClick={handleCreate} className={buttonPrimaryClass + " mt-2"}>{busy ? "Posting…" : "Post"}</button>
      </section>

      <section className="space-y-4">
        <h2 className="font-medium">Posts {total > 0 && <span className="text-xs text-zinc-500">({total})</span>}</h2>
        {posts.length === 0 ? (
          <EmptyState title="No posts yet" hint="Be the first to start the discussion." />
        ) : (
          posts.map((p) => (
            <article key={p.id} className="rounded border bg-white p-4">
              <div className="flex justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{p.author_display_name ?? "Unknown"}</p>
                  <p className="text-xs text-zinc-500">{timeAgo(p.created_at)}</p>
                </div>
                {p.is_own && (
                  <button onClick={() => handleDeletePost(p.id)} className="text-xs text-red-600 hover:underline">Delete</button>
                )}
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm">{p.content}</p>
              <div className="mt-3 flex items-center gap-4 text-xs">
                <LikeButton post={p} forumId={forumId} token={token!} onUpdate={(liked, cnt) => handleLikeUpdate(p.id, liked, cnt)} />
                <span className="text-zinc-500">💬 {p.comment_count} {p.comment_count === 1 ? "comment" : "comments"}</span>
              </div>
              <CommentSection forumId={forumId} post={p} token={token!} />
            </article>
          ))
        )}
        {pageCount > 1 && (
          <div className="flex gap-2 items-center text-sm">
            <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - limit))} className="rounded border px-3 py-1 disabled:opacity-40">Previous</button>
            <span className="text-zinc-500">Page {curPage} of {pageCount}</span>
            <button disabled={offset + limit >= total} onClick={() => setOffset((o) => o + limit)} className="rounded border px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </section>
    </div>
  );
}

export default function ForumRoute({ params }: { params: { forumId: string } }) {
  return (
    <RequireAuth>
      <ForumPageInner forumId={params.forumId} />
    </RequireAuth>
  );
}
