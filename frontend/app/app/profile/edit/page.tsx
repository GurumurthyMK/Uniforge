"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth, useAuth } from "@/lib/auth";
import { ApiError, fetchMyProfile, saveMyProfile } from "@/lib/api";
import { Field, Loading, buttonPrimaryClass, buttonSecondaryClass, inputClass } from "@/components/ui";

function splitTags(raw: string): string[] {
  return raw.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
}

function EditForm() {
  const auth = useAuth();
  const router = useRouter();
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    display_name: "",
    headline: "",
    bio: "",
    avatar_url: "",
    github_url: "",
    linkedin_url: "",
    portfolio_url: "",
    website_url: "",
    career_interests: "",
    research_interests: "",
    skills: "",
    interests: "",
    hobbies: "",
  });

  const token = auth.status === "authenticated" ? auth.token : null;

  useEffect(() => {
    if (!token) return;
    fetchMyProfile(token)
      .then((p) => {
        setForm({
          display_name: p.display_name ?? "",
          headline: p.headline ?? "",
          bio: p.bio ?? "",
          avatar_url: p.avatar_url ?? "",
          github_url: p.github_url ?? "",
          linkedin_url: p.linkedin_url ?? "",
          portfolio_url: p.portfolio_url ?? "",
          website_url: p.website_url ?? "",
          career_interests: p.career_interests ?? "",
          research_interests: p.research_interests ?? "",
          skills: p.skills.join(", "),
          interests: p.interests.filter((t) => t.kind === "INTEREST").map((t) => t.name).join(", "),
          hobbies: p.interests.filter((t) => t.kind === "HOBBY").map((t) => t.name).join(", "),
        });
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load profile."));
  }, [token]);

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSaving(true);
    const opt = (v: string) => (v.trim() ? v.trim() : undefined);
    try {
      await saveMyProfile(token, {
        display_name: opt(form.display_name),
        headline: opt(form.headline),
        bio: opt(form.bio),
        avatar_url: opt(form.avatar_url),
        github_url: opt(form.github_url),
        linkedin_url: opt(form.linkedin_url),
        portfolio_url: opt(form.portfolio_url),
        website_url: opt(form.website_url),
        career_interests: opt(form.career_interests),
        research_interests: opt(form.research_interests),
        skills: splitTags(form.skills),
        interests: splitTags(form.interests),
        hobbies: splitTags(form.hobbies),
      });
      await auth.refresh();
      router.push("/app/profile");
    } catch (err) {
      setError(err instanceof ApiError ? `${err.message} (${err.code})` : "Could not save profile.");
      setSaving(false);
    }
  }

  if (auth.status !== "authenticated") return null;
  if (error && !loaded) return <p className="text-sm text-red-700" role="alert">{error}</p>;
  if (!loaded) return <Loading label="Loading editor…" />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Edit profile</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Student-controlled only. Your verified university identity cannot be changed here.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4 rounded-lg border bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Display name">
            <input value={form.display_name} onChange={set("display_name")} maxLength={100} className={inputClass} />
          </Field>
          <Field label="Headline" hint="One line under your name, e.g. “CS undergrad into robotics”">
            <input value={form.headline} onChange={set("headline")} maxLength={150} className={inputClass} />
          </Field>
        </div>
        <Field label="Bio">
          <textarea value={form.bio} onChange={set("bio")} rows={4} maxLength={2000} className={inputClass} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Avatar image URL" hint="Link an externally hosted image">
            <input value={form.avatar_url} onChange={set("avatar_url")} inputMode="url" className={inputClass} />
          </Field>
          <Field label="GitHub URL">
            <input value={form.github_url} onChange={set("github_url")} inputMode="url" className={inputClass} />
          </Field>
          <Field label="LinkedIn URL">
            <input value={form.linkedin_url} onChange={set("linkedin_url")} inputMode="url" className={inputClass} />
          </Field>
          <Field label="Portfolio URL">
            <input value={form.portfolio_url} onChange={set("portfolio_url")} inputMode="url" className={inputClass} />
          </Field>
        </div>
        <Field label="Website URL">
          <input value={form.website_url} onChange={set("website_url")} inputMode="url" className={inputClass} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Skills" hint="Comma-separated, max 20">
            <input value={form.skills} onChange={set("skills")} placeholder="python, sql" className={inputClass} />
          </Field>
          <Field label="Interests" hint="Comma-separated, max 20">
            <input value={form.interests} onChange={set("interests")} placeholder="robotics" className={inputClass} />
          </Field>
          <Field label="Hobbies" hint="Comma-separated, max 20">
            <input value={form.hobbies} onChange={set("hobbies")} placeholder="chess" className={inputClass} />
          </Field>
        </div>
        <Field label="Career interests">
          <textarea value={form.career_interests} onChange={set("career_interests")} rows={2} maxLength={2000} className={inputClass} />
        </Field>
        <Field label="Research interests">
          <textarea value={form.research_interests} onChange={set("research_interests")} rows={2} maxLength={2000} className={inputClass} />
        </Field>
        {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
        <div className="flex gap-3">
          <button type="submit" disabled={saving} className={buttonPrimaryClass}>
            {saving ? "Saving…" : "Save profile"}
          </button>
          <button type="button" onClick={() => router.push("/app/profile")} className={buttonSecondaryClass}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

export default function ProfileEditPage() {
  return (
    <RequireAuth>
      <EditForm />
    </RequireAuth>
  );
}
