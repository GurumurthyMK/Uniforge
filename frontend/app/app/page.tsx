"use client";

import { useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { updateProfile } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "VERIFIED" ? "bg-green-100 text-green-800" : status === "PENDING" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${color}`}>{status}</span>;
}

function Dashboard() {
  const auth = useAuth();
  if (auth.status !== "authenticated") return null;
  const { me, token, signOut, refresh } = auth;

  const [displayName, setDisplayName] = useState(me.profile.display_name ?? "");
  const [bio, setBio] = useState(me.profile.bio ?? "");
  const [saved, setSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(null);
    try {
      await updateProfile(token, { display_name: displayName || undefined, bio: bio || undefined });
      await refresh();
      setSaved("Profile saved.");
    } catch {
      setSaved("Could not save profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Welcome, {me.profile.display_name ?? me.email}</h1>
          <p className="text-sm text-zinc-600">{me.email}</p>
        </div>
        <button onClick={() => void signOut()} className="rounded border px-3 py-1.5 text-sm hover:bg-zinc-100">
          Log out
        </button>
      </div>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium">Verified university identity 🔒</h2>
        <p className="mt-1 text-xs text-zinc-500">
          University-controlled. You cannot edit this — it is verified against university records.
        </p>
        <div className="mt-3 space-y-2 text-sm">
          {me.identities.length === 0 && <p className="text-zinc-500">No university identity yet.</p>}
          {me.identities.map((ident) => (
            <div key={ident.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded border px-3 py-2">
              <StatusBadge status={ident.status} />
              <span className="font-medium">{ident.university_name}</span>
              <span className="text-zinc-600">{ident.role}</span>
              {ident.student_no && <span className="text-zinc-600">No. {ident.student_no}</span>}
              {ident.class_name && <span className="text-zinc-600">Class {ident.class_name}</span>}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium">Your profile ✏️</h2>
        <p className="mt-1 text-xs text-zinc-500">Student-controlled. Editable anytime, never treated as verified.</p>
        <form onSubmit={onSaveProfile} className="mt-3 space-y-3 text-sm">
          <label className="block">
            <span className="mb-1 block font-medium">Display name</span>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="w-full rounded border px-3 py-2" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Bio</span>
            <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3} className="w-full rounded border px-3 py-2" />
          </label>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={saving} className="rounded bg-zinc-900 px-3 py-1.5 text-white disabled:opacity-50">
              {saving ? "Saving…" : "Save profile"}
            </button>
            {saved && <span className="text-zinc-600">{saved}</span>}
          </div>
        </form>
      </section>
    </div>
  );
}

export default function AppPage() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
