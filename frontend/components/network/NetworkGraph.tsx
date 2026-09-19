"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import type { GraphResponse, GraphNode as GNode } from "@/lib/api";

type Props = {
  graph: GraphResponse;
};

const typeStyles: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  STUDENT: { bg: "bg-blue-50", border: "border-blue-400", text: "text-blue-900", icon: "👤" },
  UNIVERSITY: { bg: "bg-amber-50", border: "border-amber-600", text: "text-amber-900", icon: "🏛" },
  DEPARTMENT: { bg: "bg-orange-50", border: "border-orange-400", text: "text-orange-900", icon: "🏢" },
  PROGRAM: { bg: "bg-purple-50", border: "border-purple-400", text: "text-purple-900", icon: "🎓" },
  BATCH: { bg: "bg-teal-50", border: "border-teal-400", text: "text-teal-900", icon: "📅" },
  CLASS: { bg: "bg-emerald-50", border: "border-emerald-500", text: "text-emerald-900", icon: "👥" },
  FORUM: { bg: "bg-pink-50", border: "border-pink-400", text: "text-pink-900", icon: "💬" },
  SKILL: { bg: "bg-zinc-900", border: "border-zinc-900", text: "text-white", icon: "⚡" },
  INTEREST: { bg: "bg-sky-50", border: "border-sky-400", text: "text-sky-900", icon: "⭐" },
};

function layoutNodes(graph: GraphResponse): Map<string, { x: number; y: number }> {
  const pos = new Map<string, { x: number; y: number }>();
  const byType = new Map<string, GNode[]>();
  for (const n of graph.nodes) {
    const arr = byType.get(n.type) ?? [];
    arr.push(n);
    byType.set(n.type, arr);
  }
  const rootId = graph.root_id;
  // Academic spine centered
  const chainOrder: Array<[string, number, number]> = [
    ["UNIVERSITY", 0, -400],
    ["DEPARTMENT", 0, -300],
    ["PROGRAM", 0, -200],
    ["BATCH", 0, -100],
    ["CLASS", 0, 50],
  ];
  for (const [type, x, y] of chainOrder) {
    const nodes = byType.get(type) ?? [];
    nodes.forEach((n, i) => {
      // if multiple of same type, spread slightly
      const offset = nodes.length > 1 ? (i - (nodes.length - 1) / 2) * 80 : 0;
      pos.set(n.id, { x: x + offset, y: y + (nodes.length > 1 ? i * 10 : 0) });
    });
  }
  // Root
  pos.set(rootId, { x: 0, y: 170 });

  // Forums left
  const forums = byType.get("FORUM") ?? [];
  forums.forEach((n, i) => {
    const y = -120 + i * 75 - ((forums.length - 1) * 75) / 2 + 60;
    pos.set(n.id, { x: -320, y });
  });
  // Skills right upper
  const skills = byType.get("SKILL") ?? [];
  skills.forEach((n, i) => {
    const y = -140 + i * 62 - ((skills.length - 1) * 62) / 2 + 20;
    pos.set(n.id, { x: 320, y });
  });
  // Interests right lower
  const interests = byType.get("INTEREST") ?? [];
  interests.forEach((n, i) => {
    const y = 80 + i * 62;
    pos.set(n.id, { x: 320, y });
  });
  // Connected students south
  const connected = (byType.get("STUDENT") ?? []).filter((n) => n.id !== rootId);
  connected.forEach((n, i) => {
    const nCount = connected.length;
    const spread = 180;
    const x = nCount === 1 ? 0 : -((nCount - 1) * spread) / 2 + i * spread;
    // clamp
    const finalX = Math.max(-400, Math.min(400, x));
    // stagger y slightly for readability when many
    const y = 360 + (i % 2) * 30;
    pos.set(n.id, { x: finalX, y });
  });
  // Any other nodes not yet placed (fallback radial)
  for (const n of graph.nodes) {
    if (!pos.has(n.id)) {
      pos.set(n.id, { x: Math.random() * 200 - 100, y: Math.random() * 200 - 100 });
    }
  }
  return pos;
}

function edgeLabel(type: string): string | undefined {
  const map: Record<string, string | undefined> = {
    CONNECTED_TO: "connected",
    HAS_SKILL: "skill",
    HAS_INTEREST: "interest",
    PARTICIPATES_IN: "forum",
    IN_CLASS: "class",
    ENROLLED_IN: "university",
    BELONGS_TO: undefined,
    IN_PROGRAM: undefined,
    IN_BATCH: undefined,
  };
  return map[type];
}

function NodeDetails({ node, rootId, onClose }: { node: GNode; rootId: string; onClose: () => void }) {
  const isRoot = node.id === rootId;
  const meta = node.metadata as Record<string, unknown>;
  return (
    <div className="rounded-lg border bg-white p-4 shadow-lg">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">{node.type}{isRoot ? " · You" : ""}</p>
          <h3 className="font-semibold">{node.label}</h3>
        </div>
        <button onClick={onClose} className="rounded border px-2 py-1 text-xs hover:bg-zinc-100">Close</button>
      </div>
      <div className="mt-3 space-y-2 text-sm text-zinc-700">
        {node.type === "STUDENT" && (
          <>
            {meta.headline ? <p className="text-zinc-600">{String(meta.headline)}</p> : null}
            {meta.role ? <p className="text-xs text-zinc-500">Role: {String(meta.role)}</p> : null}
            {!isRoot && (
              <Link href={`/app/people/${node.id}`} className="inline-block rounded bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700">
                View profile →
              </Link>
            )}
            {isRoot && <p className="text-xs text-zinc-500">This is you — the center of your network.</p>}
          </>
        )}
        {node.type === "CLASS" && (
          <>
            {meta.code ? <p className="text-xs">Code: {String(meta.code)}</p> : null}
            <p className="text-xs text-zinc-500">Class community for your cohort.</p>
          </>
        )}
        {node.type === "FORUM" && (
          <>
            {meta.description ? <p className="text-sm text-zinc-600">{String(meta.description)}</p> : <p className="text-xs text-zinc-500">Approved forum you are a member of.</p>}
            {meta.class_id ? <p className="text-xs text-zinc-500">Class: {String(meta.class_id).slice(0, 8)}…</p> : null}
          </>
        )}
        {node.type === "SKILL" && <p className="text-xs text-zinc-500">Skill you have declared.</p>}
        {node.type === "INTEREST" && (
          <p className="text-xs text-zinc-500">Interest: {meta.kind ? String(meta.kind) : "INTEREST"}</p>
        )}
        {["UNIVERSITY", "DEPARTMENT", "PROGRAM", "BATCH"].includes(node.type) && (
          <>
            {meta.code ? <p className="text-xs">Code: {String(meta.code)}</p> : null}
            {meta.degree_level ? <p className="text-xs">Degree: {String(meta.degree_level)}</p> : null}
            {meta.start_year ? <p className="text-xs">Year: {String(meta.start_year)}</p> : null}
          </>
        )}
      </div>
    </div>
  );
}

function InnerGraph({ graph }: Props) {
  const [selected, setSelected] = useState<GNode | null>(null);
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  const positions = useMemo(() => layoutNodes(graph), [graph]);

  const rfNodes: Node[] = useMemo(() => {
    return graph.nodes.map((n) => {
      const isRoot = n.id === graph.root_id;
      const styleCfg = typeStyles[n.type] ?? typeStyles["STUDENT"];
      const pos = positions.get(n.id) ?? { x: 0, y: 0 };
      const isSkill = n.type === "SKILL";
      return {
        id: n.id,
        position: pos,
        data: { label: `${styleCfg.icon}  ${n.label}` },
        style: {
          background: isSkill ? "#18181b" : undefined,
          color: isSkill ? "#ffffff" : undefined,
          borderWidth: isRoot ? 2.5 : 1.2,
          borderColor: isRoot ? "#18181b" : undefined,
          borderRadius: 10,
          padding: "8px 12px",
          fontSize: isRoot ? 13 : 12,
          fontWeight: isRoot ? 600 : 500,
          width: isRoot ? 180 : 150,
          textAlign: "center" as const,
          boxShadow: isRoot ? "0 4px 12px rgba(0,0,0,0.12)" : "0 2px 6px rgba(0,0,0,0.08)",
        },
        className: `${styleCfg.bg} ${styleCfg.border} ${styleCfg.text}`,
        selected: selected?.id === n.id,
      };
    });
  }, [graph, positions, selected]);

  const rfEdges: Edge[] = useMemo(() => {
    return graph.edges.map((e) => {
      const lbl = edgeLabel(e.type);
      const isConnected = e.type === "CONNECTED_TO";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: lbl,
        animated: isConnected,
        style: { stroke: isConnected ? "#3b82f6" : "#a1a1aa", strokeWidth: isConnected ? 2 : 1.4 },
        labelStyle: { fontSize: 10, fill: "#52525b" },
        labelBgStyle: { fill: "#ffffff", fillOpacity: 0.85 },
      };
    });
  }, [graph]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const gNode = graph.nodes.find((n) => n.id === node.id) ?? null;
      setSelected(gNode);
    },
    [graph.nodes]
  );

  const onPaneClick = useCallback(() => setSelected(null), []);

  return (
    <div className="flex h-[620px] flex-col overflow-hidden rounded-lg border bg-white lg:h-[700px]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-zinc-50 px-3 py-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium">Network</span>
          <span className="text-zinc-500">· {graph.nodes.length} nodes · {graph.edges.length} edges</span>
        </div>
        <div className="flex gap-1">
          <button onClick={() => zoomIn()} className="rounded border bg-white px-2 py-1 hover:bg-zinc-100">Zoom +</button>
          <button onClick={() => zoomOut()} className="rounded border bg-white px-2 py-1 hover:bg-zinc-100">Zoom −</button>
          <button onClick={() => fitView({ padding: 0.2, duration: 300 })} className="rounded border bg-white px-2 py-1 hover:bg-zinc-100">Fit</button>
          <button onClick={() => fitView({ padding: 0.2, duration: 300 })} className="rounded bg-zinc-900 px-2 py-1 text-white hover:bg-zinc-700">Recenter</button>
        </div>
      </div>
      <div className="relative flex-1">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} color="#e4e4e7" />
          <Controls showInteractive={false} />
          <MiniMap style={{ height: 90, width: 130 }} maskColor="rgba(0,0,0,0.08)" />
        </ReactFlow>
        {selected && (
          <div className="absolute bottom-3 right-3 w-[300px] max-w-[90%]">
            <NodeDetails node={selected} rootId={graph.root_id} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
      <div className="border-t bg-white px-3 py-2 text-xs text-zinc-500">
        <span className="inline-flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-400" /> Student</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-600" /> University</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Class</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-pink-400" /> Forum</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-zinc-900" /> Skill</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-sky-400" /> Interest</span>
        </span>
        <span className="ml-3">Root is larger with dark border. Click a node for details.</span>
      </div>
    </div>
  );
}

export function NetworkGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <InnerGraph {...props} />
    </ReactFlowProvider>
  );
}
