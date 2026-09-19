"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  fetchClassDetail,
  fetchClassMembers,
  type ClassDetail,
  type ClassMembersPage,
} from "@/lib/api";
import { EmptyState, Loading, StatusBadge } from "@/components/ui";

const PAGE_SIZE = 30;

function ClassPage() {
  const auth = useAuth();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [page, setPage] = useState<ClassMembersPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const classId =
    auth.status === "authenticated"
      ? auth.me.identities.find((i) => i.status === "VERIFIED" && i.class_id)?.class_id ?? null
      : null;

  useEffect(() => {
    if (!token || !classId) return;
    fetchClassDetail(token, classId).then(setDetail).catch((e) => {
      setError(e instanceof ApiError ? e.message : "Could not load class.");
    });
  }, [token, classId]);

  useEffect(() => {
    if (!token || !classId) return;
    fetchClassMembers(token, classId, PAGE_SIZE, offset)
      .then(setPage)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load members."));
  }, [token, classId, offset]);

  if (auth.status !== "authenticated") return null;
  if (error) return <p className="text-sm text-red-700" role="alert">{error}</p>;
  if (!classId) {
    return <EmptyState title="No class assigned" hint="Your verified identity is not linked to a class yet." />;
  }
  if (!detail || !page) return <Loading label="Loading your class…" />;

  const totalPages = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-zinc-500">My class</p>
        <h1 className="text-2xl font-bold">{detail.class.name}</h1>
        <p className="mt-1 text-sm text-zinc-600">
          {detail.program.name} · Batch {detail.batch.name} · {detail.department.name} · {detail.university.name}
        </p>
      </div>

      {detail.class_rep && (
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="font-medium">Class representative</h2>
          <Link
            href={`/app/people/${detail.class_rep.user_id}`}
            className="mt-1 inline-block font-medium text-zinc-900 underline"
          >
            {detail.class_rep.display_name ?? "Class rep"}
          </Link>
        </section>
      )}

      <section className="rounded-lg border bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Classmates ({page.total})</h2>
        </div>
        {page.items.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No verified members yet.</p>
        ) : (
          <ul className="mt-3 divide-y text-sm">
            {page.items.map((m) => (
              <li key={m.user_id} className="flex items-center justify-between gap-3 py-2">
                <Link href={`/app/people/${m.user_id}`} className="font-medium underline">
                  {m.display_name ?? "Unnamed student"}
                </Link>
                <span className="flex items-center gap-2 text-xs text-zinc-500">
                  {m.role !== "STUDENT" && <span>{m.role}</span>}
                  <StatusBadge status={m.verification_status} />
                </span>
              </li>
            ))}
          </ul>
        )}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center gap-3 text-sm">
            <button
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              className="rounded border px-3 py-1 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-zinc-500">
              Page {currentPage} of {totalPages}
            </span>
            <button
              disabled={offset + PAGE_SIZE >= page.total}
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
              className="rounded border px-3 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export default function ClassRoutePage() {
  return (
    <RequireAuth>
      <ClassPage />
    </RequireAuth>
  );
}
