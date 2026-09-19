"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl, getApiHealth, type HealthResponse } from "@/lib/api";

export function ApiStatus() {
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "ok"; data: HealthResponse } | { kind: "error"; message: string }
  >({ kind: "loading" });

  useEffect(() => {
    getApiHealth()
      .then((data) => setState({ kind: "ok", data }))
      .catch((e: unknown) => setState({ kind: "error", message: e instanceof Error ? e.message : String(e) }));
  }, []);

  return (
    <div className="rounded-lg border bg-white p-4 text-sm">
      <p className="font-medium">API status</p>
      <p className="mt-1 text-zinc-500">Backend: {apiBaseUrl()}</p>
      {state.kind === "loading" && <p className="mt-2">Checking backend…</p>}
      {state.kind === "ok" && (
        <p className="mt-2 text-green-700">
          Connected — {state.data.service} ({state.data.status}, v{state.data.version})
        </p>
      )}
      {state.kind === "error" && (
        <p className="mt-2 text-red-700">
          Backend unreachable: {state.message}. Start the API on port 8000.
        </p>
      )}
    </div>
  );
}
