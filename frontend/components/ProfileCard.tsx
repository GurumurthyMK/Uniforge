import Link from "next/link";
import type { FullProfile, PublicProfile } from "@/lib/api";

type ProfileLike = Pick<
  FullProfile,
  | "display_name"
  | "headline"
  | "bio"
  | "avatar_url"
  | "github_url"
  | "linkedin_url"
  | "portfolio_url"
  | "website_url"
  | "career_interests"
  | "research_interests"
  | "skills"
  | "interests"
>;

/** STUDENT-CONTROLLED profile card — editable expression, never verified. */
export function ProfileCard({ profile, editable = false }: { profile: ProfileLike; editable?: boolean }) {
  const links = [
    ["GitHub", profile.github_url],
    ["LinkedIn", profile.linkedin_url],
    ["Portfolio", profile.portfolio_url],
    ["Website", profile.website_url],
  ].filter(([, url]) => url) as [string, string][];

  const interestTags = profile.interests.filter((t) => t.kind === "INTEREST");
  const hobbyTags = profile.interests.filter((t) => t.kind === "HOBBY");

  return (
    <section aria-label="Student profile" className="rounded-lg border bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {profile.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={profile.avatar_url} alt="" className="h-14 w-14 rounded-full object-cover" />
          ) : (
            <div
              aria-hidden
              className="flex h-14 w-14 items-center justify-center rounded-full bg-zinc-200 text-lg font-semibold text-zinc-600"
            >
              {(profile.display_name ?? "?").slice(0, 1).toUpperCase()}
            </div>
          )}
          <div>
            <h2 className="text-lg font-semibold">{profile.display_name ?? "Unnamed student"}</h2>
            {profile.headline && <p className="text-sm text-zinc-600">{profile.headline}</p>}
          </div>
        </div>
        {editable && (
          <Link href="/app/profile/edit" className="shrink-0 rounded border px-3 py-1.5 text-sm hover:bg-zinc-100">
            Edit profile
          </Link>
        )}
      </div>

      {profile.bio ? (
        <p className="mt-3 text-sm text-zinc-700">{profile.bio}</p>
      ) : (
        <p className="mt-3 text-sm text-zinc-400">No bio yet.</p>
      )}

      {profile.skills.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Skills</h3>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {profile.skills.map((s) => (
              <li key={s} className="rounded-full bg-zinc-900 px-2.5 py-0.5 text-xs text-white">
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(interestTags.length > 0 || hobbyTags.length > 0) && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {interestTags.length > 0 && (
            <TagGroup title="Interests" tags={interestTags.map((t) => t.name)} style="bg-blue-100 text-blue-900" />
          )}
          {hobbyTags.length > 0 && (
            <TagGroup title="Hobbies" tags={hobbyTags.map((t) => t.name)} style="bg-emerald-100 text-emerald-900" />
          )}
        </div>
      )}

      {(profile.career_interests || profile.research_interests) && (
        <dl className="mt-4 space-y-2 text-sm">
          {profile.career_interests && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Career interests</dt>
              <dd className="mt-0.5 text-zinc-700">{profile.career_interests}</dd>
            </div>
          )}
          {profile.research_interests && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Research interests</dt>
              <dd className="mt-0.5 text-zinc-700">{profile.research_interests}</dd>
            </div>
          )}
        </dl>
      )}

      {links.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          {links.map(([label, url]) => (
            <a
              key={label}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="rounded border px-2.5 py-1 text-zinc-700 hover:bg-zinc-100"
            >
              {label} ↗
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function TagGroup({ title, tags, style }: { title: string; tags: string[]; style: string }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <li key={t} className={`rounded-full px-2.5 py-0.5 text-xs ${style}`}>
            {t}
          </li>
        ))}
      </ul>
    </div>
  );
}

export type { PublicProfile };
