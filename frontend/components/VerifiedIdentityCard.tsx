import type { AcademicContext, Identity } from "@/lib/api";
import { StatusBadge } from "@/components/ui";

/** Breadcrumb of verified academic placement: University → Dept → Program → Batch → Class. */
export function AcademicBreadcrumb({ ctx }: { ctx: AcademicContext }) {
  const parts = [ctx.university.name, ctx.department?.name, ctx.program?.name, ctx.batch?.name, ctx.class?.name].filter(
    Boolean
  ) as string[];
  return (
    <nav aria-label="Academic placement" className="text-sm text-zinc-600">
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span className="mx-1 text-zinc-400">→</span>}
          <span className={i === parts.length - 1 ? "font-medium text-zinc-900" : undefined}>{part}</span>
        </span>
      ))}
    </nav>
  );
}

/** VERIFIED university identity card — read-only, university-controlled data. */
export function VerifiedIdentityCard({ identity }: { identity: Identity }) {
  return (
    <section aria-label="Verified university identity" className="rounded-lg border bg-white p-4">
      <div className="flex items-center gap-2">
        <h2 className="font-medium">Verified university identity</h2>
        <span title="University-controlled — you cannot edit this">🔒</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        Issued and controlled by your university. Contact your department office to correct it.
      </p>
      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <dt className="text-zinc-500">Status</dt>
          <dd>
            <StatusBadge status={identity.status} />
          </dd>
        </div>
        <Info label="University" value={identity.university_name} />
        <Info label="Student number" value={identity.student_no} />
        <Info label="Class" value={identity.class_name} />
        <Info label="Role" value={identity.role} />
        {identity.photo_url && (
          <div>
            <dt className="text-zinc-500">University photo</dt>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={identity.photo_url} alt="University-issued photo" className="mt-1 h-20 w-20 rounded object-cover" />
          </div>
        )}
      </dl>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-medium">{value ?? "—"}</dd>
    </div>
  );
}
