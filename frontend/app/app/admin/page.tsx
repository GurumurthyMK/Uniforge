"use client";

import { useEffect, useMemo, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  adminCreateBatch,
  adminCreateClass,
  adminCreateDepartment,
  adminCreateProgram,
  adminRename,
  fetchStructure,
  type Structure,
} from "@/lib/api";
import { EmptyState, Field, Loading, buttonPrimaryClass, inputClass } from "@/components/ui";

const ADMIN_ROLES = ["UNIVERSITY_ADMIN", "DEPARTMENT_ADMIN"];

function AdminPanel() {
  const auth = useAuth();
  const [structure, setStructure] = useState<Structure | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const adminIdentities =
    auth.status === "authenticated"
      ? auth.me.identities.filter((i) => i.status === "VERIFIED" && ADMIN_ROLES.includes(i.role))
      : [];
  const [universityId, setUniversityId] = useState<string>("");
  const token = auth.status === "authenticated" ? auth.token : null;

  useEffect(() => {
    if (adminIdentities.length > 0 && !universityId) {
      setUniversityId(adminIdentities[0].university_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  const reload = useMemo(
    () => async () => {
      if (!token || !universityId) return;
      try {
        setStructure(await fetchStructure(token, universityId));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not load structure.");
      }
    },
    [token, universityId]
  );

  useEffect(() => {
    setStructure(null);
    void reload();
  }, [reload]);

  async function run(action: () => Promise<unknown>, label: string) {
    if (!token) return;
    setError(null);
    setNotice(null);
    try {
      await action();
      await reload();
      setNotice(`${label} saved.`);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (${e.code})` : `${label} failed.`);
    }
  }

  if (auth.status !== "authenticated") return null;
  if (adminIdentities.length === 0) {
    return <EmptyState title="No admin access" hint="This area is for university and department admins." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Structure admin</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Inspect and manage the academic hierarchy. Small by design — create and rename only
          (no deletes in the MVP).
        </p>
      </div>

      {adminIdentities.length > 1 && (
        <Field label="University">
          <select value={universityId} onChange={(e) => setUniversityId(e.target.value)} className={inputClass}>
            {adminIdentities.map((i) => (
              <option key={i.university_id} value={i.university_id}>{i.university_name}</option>
            ))}
          </select>
        </Field>
      )}

      {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
      {notice && <p className="text-sm text-green-700">{notice}</p>}
      {!structure ? (
        <Loading label="Loading hierarchy…" />
      ) : (
        <StructureTree
          structure={structure}
          onRename={(kind, id, name) =>
            run(() => adminRename(token!, kind, id, { name }), "Rename")
          }
        />
      )}
      {structure && (
        <CreateForms
          structure={structure}
          onCreate={(fn, label) => run(fn, label)}
          token={token!}
        />
      )}
    </div>
  );
}

function StructureTree({
  structure,
  onRename,
}: {
  structure: Structure;
  onRename: (kind: "department" | "program" | "batch" | "class", id: string, name: string) => void;
}) {
  const [editing, setEditing] = useState<{ kind: "department" | "program" | "batch" | "class"; id: string; name: string } | null>(null);
  return (
    <section className="rounded-lg border bg-white p-4 text-sm">
      <h2 className="font-medium">{structure.university_name}</h2>
      <ul className="mt-2 space-y-3">
        {structure.departments.map((dept) => (
          <li key={dept.id}>
            <RowLabel
              text={`${dept.name} (${dept.code})`}
              onEdit={() => setEditing({ kind: "department", id: dept.id, name: dept.name })}
            />
            <ul className="ml-4 mt-1 space-y-2 border-l pl-3">
              {dept.programs.map((prog) => (
                <li key={prog.id}>
                  <RowLabel
                    text={`${prog.name} (${prog.code})`}
                    onEdit={() => setEditing({ kind: "program", id: prog.id, name: prog.name })}
                  />
                  <ul className="ml-4 mt-1 space-y-1 border-l pl-3">
                    {prog.batches.map((batch) => (
                      <li key={batch.id}>
                        <RowLabel
                          text={`Batch ${batch.name}`}
                          onEdit={() => setEditing({ kind: "batch", id: batch.id, name: batch.name })}
                        />
                        <ul className="ml-4 mt-1 space-y-1 border-l pl-3 text-zinc-600">
                          {batch.classes.map((cls) => (
                            <li key={cls.id} className="flex items-center justify-between gap-2">
                              <span>{cls.name} · {cls.member_count} members</span>
                              <button
                                onClick={() => setEditing({ kind: "class", id: cls.id, name: cls.name })}
                                className="text-xs underline"
                              >
                                Rename
                              </button>
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      {editing && (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onRename(editing.kind, editing.id, editing.name);
            setEditing(null);
          }}
        >
          <input
            value={editing.name}
            onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            className={inputClass}
            aria-label="New name"
          />
          <button type="submit" className={buttonPrimaryClass}>Save</button>
          <button type="button" onClick={() => setEditing(null)} className="text-sm underline">Cancel</button>
        </form>
      )}
    </section>
  );
}

function RowLabel({ text, onEdit }: { text: string; onEdit: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 font-medium">
      <span>{text}</span>
      <button onClick={onEdit} className="text-xs font-normal underline">Rename</button>
    </div>
  );
}

function CreateForms({
  structure,
  onCreate,
  token,
}: {
  structure: Structure;
  onCreate: (fn: () => Promise<unknown>, label: string) => void;
  token: string;
}) {
  const [dept, setDept] = useState({ name: "", code: "" });
  const [prog, setProg] = useState({ department_id: "", name: "", code: "" });
  const [batch, setBatch] = useState({ program_id: "", name: "", start_year: "" });
  const [cls, setCls] = useState({ batch_id: "", name: "", code: "" });

  const programs = structure.departments.flatMap((d) => d.programs.map((p) => ({ ...p, deptName: d.name })));
  const batches = structure.departments.flatMap((d) =>
    d.programs.flatMap((p) => p.batches.map((b) => ({ ...b, progName: p.name })))
  );

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <form
        className="space-y-2 rounded-lg border bg-white p-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(() => adminCreateDepartment(token, structure.university_id, dept), "Department");
          setDept({ name: "", code: "" });
        }}
      >
        <h3 className="font-medium">New department</h3>
        <input placeholder="Name" value={dept.name} onChange={(e) => setDept({ ...dept, name: e.target.value })} required className={inputClass} />
        <input placeholder="Code" value={dept.code} onChange={(e) => setDept({ ...dept, code: e.target.value })} required className={inputClass} />
        <button className={buttonPrimaryClass}>Create</button>
      </form>

      <form
        className="space-y-2 rounded-lg border bg-white p-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (!prog.department_id) return;
          onCreate(() => adminCreateProgram(token, prog.department_id, { name: prog.name, code: prog.code }), "Program");
          setProg({ department_id: "", name: "", code: "" });
        }}
      >
        <h3 className="font-medium">New program</h3>
        <select value={prog.department_id} onChange={(e) => setProg({ ...prog, department_id: e.target.value })} required className={inputClass}>
          <option value="">Department…</option>
          {structure.departments.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <input placeholder="Name" value={prog.name} onChange={(e) => setProg({ ...prog, name: e.target.value })} required className={inputClass} />
        <input placeholder="Code" value={prog.code} onChange={(e) => setProg({ ...prog, code: e.target.value })} required className={inputClass} />
        <button className={buttonPrimaryClass}>Create</button>
      </form>

      <form
        className="space-y-2 rounded-lg border bg-white p-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (!batch.program_id) return;
          onCreate(
            () =>
              adminCreateBatch(token, batch.program_id, {
                name: batch.name,
                ...(batch.start_year ? { start_year: Number(batch.start_year) } : {}),
              }),
            "Batch"
          );
          setBatch({ program_id: "", name: "", start_year: "" });
        }}
      >
        <h3 className="font-medium">New batch</h3>
        <select value={batch.program_id} onChange={(e) => setBatch({ ...batch, program_id: e.target.value })} required className={inputClass}>
          <option value="">Program…</option>
          {programs.map((p) => (
            <option key={p.id} value={p.id}>{p.deptName} · {p.name}</option>
          ))}
        </select>
        <input placeholder="Name, e.g. 2026" value={batch.name} onChange={(e) => setBatch({ ...batch, name: e.target.value })} required className={inputClass} />
        <input placeholder="Start year (optional)" value={batch.start_year} onChange={(e) => setBatch({ ...batch, start_year: e.target.value })} inputMode="numeric" className={inputClass} />
        <button className={buttonPrimaryClass}>Create</button>
      </form>

      <form
        className="space-y-2 rounded-lg border bg-white p-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (!cls.batch_id) return;
          onCreate(() => adminCreateClass(token, cls.batch_id, { name: cls.name, code: cls.code }), "Class");
          setCls({ batch_id: "", name: "", code: "" });
        }}
      >
        <h3 className="font-medium">New class</h3>
        <select value={cls.batch_id} onChange={(e) => setCls({ ...cls, batch_id: e.target.value })} required className={inputClass}>
          <option value="">Batch…</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>{b.progName} · {b.name}</option>
          ))}
        </select>
        <input placeholder="Name, e.g. CS-2026-A" value={cls.name} onChange={(e) => setCls({ ...cls, name: e.target.value })} required className={inputClass} />
        <input placeholder="Code, e.g. A" value={cls.code} onChange={(e) => setCls({ ...cls, code: e.target.value })} required className={inputClass} />
        <button className={buttonPrimaryClass}>Create</button>
      </form>
    </section>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth>
      <AdminPanel />
    </RequireAuth>
  );
}
