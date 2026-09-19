"use client";

import { useEffect, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { ApiError, fetchGraph, type GraphResponse } from "@/lib/api";
import { EmptyState, Loading } from "@/components/ui";
import { NetworkGraph } from "@/components/network/NetworkGraph";

function NetworkPageInner() {
  const auth = useAuth();
  const token = auth.status === "authenticated" ? auth.token : null;
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    fetchGraph(token)
      .then((g) => {
        setGraph(g);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : "Unable to load your network.");
        setLoading(false);
      });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading) return <Loading label="Loading your university network…" />;
  if (error) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center">
        <p className="text-sm font-medium text-zinc-700">Unable to load your network.</p>
        <p className="mt-1 text-sm text-zinc-500">{error}</p>
        <button onClick={load} className="mt-4 rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700">
          Retry
        </button>
      </div>
    );
  }
  if (!graph) return <Loading label="Loading your university network…" />;

  // Empty state: only root + maybe university
  const hasContent = graph.nodes.length > 2 || graph.edges.length > 1;
  if (!hasContent) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Your University Network</h1>
          <p className="mt-1 text-sm text-zinc-600">Your academic context, communities, interests, skills, and connections in one network.</p>
        </div>
        <EmptyState
          title="Your network is still growing."
          hint="Complete your profile, add skills and interests, join forums, and connect with classmates to build your university network."
        />
        <div className="rounded-lg border bg-white p-4">
          <p className="text-sm text-zinc-600">Root: {graph.nodes.find((n) => n.id === graph.root_id)?.label ?? "You"}</p>
          <p className="mt-1 text-xs text-zinc-500">{graph.nodes.length} nodes · {graph.edges.length} edges</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Your University Network</h1>
        <p className="mt-1 text-sm text-zinc-600">Your academic context, communities, interests, skills, and connections in one network.</p>
        <p className="mt-1 text-xs text-zinc-500">Pan & zoom, click a node for details, use Fit to recenter. Student nodes link to profiles.</p>
      </div>
      <NetworkGraph graph={graph} />
    </div>
  );
}

export default function NetworkRoute() {
  return (
    <RequireAuth>
      <NetworkPageInner />
    </RequireAuth>
  );
}
