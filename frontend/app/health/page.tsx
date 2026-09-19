import { getApiHealth, getApiReady } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HealthPage() {
  const [health, ready] = await Promise.all([
    getApiHealth().catch((e: unknown) => ({ error: String(e) })),
    getApiReady().catch((e: unknown) => ({ error: String(e) })),
  ]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Backend connectivity</h1>
      <pre className="overflow-auto rounded-lg border bg-white p-4 text-xs">
        {JSON.stringify({ health, ready }, null, 2)}
      </pre>
      <p className="text-xs text-zinc-500">
        API base: {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
      </p>
    </div>
  );
}
