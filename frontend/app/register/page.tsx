"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ApiError, listClasses, listUniversities, type ClassInfo, type University } from "@/lib/api";

export default function RegisterPage() {
  const { signUp } = useAuth();
  const [universities, setUniversities] = useState<University[]>([]);
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    university_id: "",
    class_id: "",
    student_no: "",
    enrollment_code: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listUniversities().then(setUniversities).catch(() => setError("Could not reach the API. Is the backend running?"));
  }, []);

  useEffect(() => {
    if (!form.university_id) {
      setClasses([]);
      return;
    }
    listClasses(form.university_id).then(setClasses).catch(() => setClasses([]));
  }, [form.university_id]);

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signUp({ ...form, email: form.email.trim() });
    } catch (err) {
      setError(err instanceof ApiError ? `${err.message} (${err.code})` : "Registration failed.");
      setBusy(false);
    }
  }

  const selectedUni = universities.find((u) => u.id === form.university_id);

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create your account</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Registration anchors you in the university structure. With a matching university email domain
          and the demo enrollment code, your identity is verified instantly — otherwise it goes to
          admin review.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4 rounded-lg border bg-white p-5">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">University</span>
          <select required value={form.university_id} onChange={set("university_id")} className="w-full rounded border px-3 py-2">
            <option value="">Select…</option>
            {universities.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </label>
        {selectedUni && (
          <p className="text-xs text-zinc-500">
            Use your <code>@{selectedUni.email_domain}</code> email. Demo enrollment code:{" "}
            <code>UNIFORGE-DEMO-2026</code>
          </p>
        )}
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Class</span>
          <select required value={form.class_id} onChange={set("class_id")} className="w-full rounded border px-3 py-2">
            <option value="">Select…</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.program_name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Student number</span>
          <input required value={form.student_no} onChange={set("student_no")} placeholder="DEMO-2024-010" className="w-full rounded border px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Enrollment code</span>
          <input required value={form.enrollment_code} onChange={set("enrollment_code")} placeholder="From your university" className="w-full rounded border px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Display name</span>
          <input required value={form.display_name} onChange={set("display_name")} className="w-full rounded border px-3 py-2" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">University email</span>
          <input required type="email" value={form.email} onChange={set("email")} className="w-full rounded border px-3 py-2" autoComplete="email" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Password (min 8 characters)</span>
          <input required type="password" minLength={8} value={form.password} onChange={set("password")} className="w-full rounded border px-3 py-2" autoComplete="new-password" />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy} className="w-full rounded bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="text-sm text-zinc-600">
        Already have an account? <Link className="underline" href="/login">Log in</Link>
      </p>
    </div>
  );
}
