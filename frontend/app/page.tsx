import { ApiStatus } from "@/components/ApiStatus";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">UniForge foundation shell</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Verified university ecosystem. MVP Phase 1A: frontend + API + Postgres wiring only —
          no business features yet.
        </p>
      </div>
      <ApiStatus />
      <div className="rounded-lg border bg-white p-4 text-sm">
        <p className="font-medium">Core product loop (upcoming phases)</p>
        <p className="mt-1 text-zinc-600">
          verification → profile → spaces → participation → relationships → network graph →
          skills/interests → talent graph → discovery → collaboration
        </p>
      </div>
    </div>
  );
}
