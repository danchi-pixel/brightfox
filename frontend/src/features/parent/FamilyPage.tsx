/** Family (parents): the family's name and language, the learners (kids), sign-in accounts, and your own settings. */
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Trash2, UserRound, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Field, Input, Select } from "@/components/ui/input";
import { Card, CardHeader, ErrorState, PageLoader, Segmented } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { qk, ucApi, useAccounts, useFamily, type FamilyView, type Learner } from "../learning/api";
import { LearnerAvatar } from "../learning/ui";
import { gradeName, PageTitle } from "./common";

const AVATARS = ["🦊", "⚽", "🏀", "🎨", "🚀", "🐱", "🐶", "🦉", "🐼", "🎸", "🌟", "📚"];
const COLORS = ["#e8590c", "#6a4bd6", "#0ea5e9", "#16a34a", "#f59e0b", "#ec4899", "#ef4444", "#14b8a6", "#64748b"];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function FamilyPage() {
  const family = useFamily();
  if (family.isError) return <ErrorState error={family.error} onRetry={() => void family.refetch()} />;
  if (!family.data) return <PageLoader />;
  return (
    <div className="space-y-5">
      <PageTitle title="Family" sub="Your kids, their sign-ins and your own settings." />
      <FamilyCard family={family.data} />
      <LearnersCard learners={family.data.learners} />
      <AccountsCard learners={family.data.learners} />
      <MeCard />
    </div>
  );
}

function FamilyCard({ family }: { family: FamilyView }) {
  const qc = useQueryClient();
  const [name, setName] = useState(family.name);
  const save = async (body: Parameters<typeof ucApi.patchFamily>[0]) => {
    try {
      await ucApi.patchFamily(body);
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success("Saved.");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  return (
    <Card className="flex flex-wrap items-end gap-3 p-4">
      <Field label="Family name" className="min-w-56 flex-1">
        <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Button variant="secondary" disabled={!name.trim() || name === family.name} onClick={() => void save({ name: name.trim() })}>
        Save
      </Button>
      <Field label="Kids' screens">
        <Select value={family.language} onChange={(e) => void save({ language: e.target.value as "sl" | "en" })}>
          <option value="sl">Slovenščina</option>
          <option value="en">English</option>
        </Select>
      </Field>
    </Card>
  );
}

function LearnersCard({ learners }: { learners: Learner[] }) {
  const [adding, setAdding] = useState(false);
  return (
    <Card>
      <CardHeader
        title="Learners"
        icon={<Users />}
        action={
          <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
            <Plus /> Add
          </Button>
        }
      />
      <div className="space-y-3 px-5 pb-5">
        {adding && <LearnerForm onDone={() => setAdding(false)} />}
        {learners.map((lr) => (
          <LearnerForm key={lr.id} learner={lr} />
        ))}
        {!learners.length && !adding && <p className="text-sm text-muted-foreground">No learners yet.</p>}
      </div>
    </Card>
  );
}

function LearnerForm({ learner, onDone }: { learner?: Learner; onDone?: () => void }) {
  const qc = useQueryClient();
  const initial = {
    name: learner?.name ?? "",
    avatar: learner?.avatar ?? "🦊",
    color: learner?.color ?? COLORS[0],
    grade: learner?.grade ?? null,
    language: learner?.language ?? "sl",
    rhythm: learner?.rhythm ?? { days: [1, 2, 3, 4], minutes: 20 },
    archived: learner?.archived ?? false,
  };
  const [v, setV] = useState(initial);
  const [busy, setBusy] = useState(false);
  useEffect(() => setV(initial), [learner]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = !learner || JSON.stringify(v) !== JSON.stringify(initial);

  const save = async () => {
    setBusy(true);
    try {
      if (learner) await ucApi.patchLearner(learner.id, { ...v, name: v.name.trim() });
      else await ucApi.addLearner({ ...v, name: v.name.trim() });
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success(learner ? "Saved." : `${v.name.trim()} added.`);
      onDone?.();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("space-y-3 rounded-2xl border border-border p-3", v.archived && "opacity-60")}>
      <div className="flex flex-wrap items-end gap-3">
        <LearnerAvatar learner={{ ...v, name: v.name || "?" }} size="lg" />
        <Field label="Name" className="min-w-40 flex-1">
          <Input value={v.name} maxLength={40} onChange={(e) => setV({ ...v, name: e.target.value })} />
        </Field>
        <Field label="School">
          <Select value={v.grade ?? ""} onChange={(e) => setV({ ...v, grade: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Not set</option>
            {Array.from({ length: 13 }, (_, i) => i + 1).map((g) => (
              <option key={g} value={g}>
                {gradeName(g, true)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Language">
          <Select value={v.language} onChange={(e) => setV({ ...v, language: e.target.value as "sl" | "en" })}>
            <option value="sl">Slovenščina</option>
            <option value="en">English</option>
          </Select>
        </Field>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {AVATARS.map((a) => (
          <button
            key={a}
            type="button"
            aria-pressed={v.avatar === a}
            onClick={() => setV({ ...v, avatar: a })}
            className={cn("grid size-9 place-items-center rounded-xl border-2 text-lg", v.avatar === a ? "border-primary bg-primary-soft" : "border-transparent hover:bg-muted")}
          >
            {a}
          </button>
        ))}
        <span className="mx-1 w-px self-stretch bg-border" />
        {COLORS.map((c) => (
          <button
            key={c}
            type="button"
            aria-label={`Colour ${c}`}
            aria-pressed={v.color === c}
            onClick={() => setV({ ...v, color: c })}
            className={cn("size-9 rounded-xl border-2", v.color === c ? "border-foreground" : "border-transparent")}
            style={{ background: c }}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Usual study days:</span>
        {DAYS.map((d, i) => {
          const on = v.rhythm.days.includes(i + 1);
          return (
            <button
              key={d}
              type="button"
              aria-pressed={on}
              onClick={() =>
                setV({ ...v, rhythm: { ...v.rhythm, days: on ? v.rhythm.days.filter((x) => x !== i + 1) : [...v.rhythm.days, i + 1].sort() } })
              }
              className={cn("rounded-lg border px-2 py-1 text-xs font-medium", on ? "border-primary bg-primary-soft text-primary" : "border-border")}
            >
              {d}
            </button>
          );
        })}
        <Select value={v.rhythm.minutes} onChange={(e) => setV({ ...v, rhythm: { ...v.rhythm, minutes: Number(e.target.value) } })} className="w-28" aria-label="Minutes a day">
          {[10, 15, 20, 30, 45, 60].map((m) => (
            <option key={m} value={m}>
              {m} min
            </option>
          ))}
        </Select>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {learner && (
          <Button variant="ghost" size="sm" onClick={() => setV({ ...v, archived: !v.archived })}>
            {v.archived ? "Bring back" : "Archive"}
          </Button>
        )}
        {onDone && (
          <Button variant="ghost" size="sm" onClick={onDone}>
            Cancel
          </Button>
        )}
        <Button variant="primary" size="sm" disabled={!dirty || !v.name.trim()} loading={busy} onClick={() => void save()}>
          {learner ? "Save" : "Add learner"}
        </Button>
      </div>
    </div>
  );
}

function AccountsCard({ learners }: { learners: Learner[] }) {
  const accounts = useAccounts();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { me } = useAuth();
  const [form, setForm] = useState({ username: "", password: "", role: "learner" as "admin" | "learner", learner_id: "" });
  const [busy, setBusy] = useState(false);
  const free = learners.filter((l) => !l.username && !l.archived);

  const create = async () => {
    setBusy(true);
    try {
      await ucApi.addAccount({
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        learner_id: form.role === "learner" ? Number(form.learner_id) : null,
      });
      setForm({ username: "", password: "", role: "learner", learner_id: "" });
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success("Account created. Give the username and password to its owner.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const reset = async (uid: number, username: string) => {
    const pw = window.prompt(`New password for ${username} (at least 10 characters). They'll be signed out everywhere.`);
    if (!pw) return;
    try {
      await ucApi.setAccountPassword(uid, pw);
      toast.success("Password changed.");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const remove = async (uid: number, username: string) => {
    if (!(await confirm({ title: `Delete the account ${username}?`, description: "The sign-in is removed; the learner's work stays.", confirmLabel: "Delete", danger: true })))
      return;
    try {
      await ucApi.deleteAccount(uid);
      await qc.invalidateQueries({ queryKey: qk.all });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <Card>
      <CardHeader title="Sign-in accounts" icon={<KeyRound />} />
      <div className="space-y-4 px-5 pb-5">
        {accounts.isError ? (
          <ErrorState error={accounts.error} />
        ) : !accounts.data ? (
          <PageLoader />
        ) : (
          <div className="divide-y divide-border/60">
            {accounts.data.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <UserRound className="size-4 text-muted-foreground" />
                <span className="font-medium">{a.username}</span>
                <span className="text-muted-foreground">{a.role === "admin" ? "parent" : `${a.learner_name}'s account`}</span>
                <div className="flex-1" />
                <Button variant="ghost" size="sm" onClick={() => void reset(a.id, a.username)}>
                  New password
                </Button>
                {a.username !== me.username && (
                  <Button variant="danger-ghost" size="icon-sm" aria-label={`Delete ${a.username}`} onClick={() => void remove(a.id, a.username)}>
                    <Trash2 />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
        <div className="space-y-3 rounded-2xl bg-card-2 p-3">
          <div className="text-sm font-semibold">New account</div>
          <Segmented
            value={form.role}
            onChange={(role) => setForm({ ...form, role })}
            options={[
              { value: "learner", label: "For a kid" },
              { value: "admin", label: "Another parent" },
            ]}
            size="sm"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {form.role === "learner" && (
              <Field label="Learner">
                <Select value={form.learner_id} onChange={(e) => setForm({ ...form, learner_id: e.target.value })}>
                  <option value="">Choose…</option>
                  {free.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Username">
              <Input value={form.username} autoCapitalize="none" spellCheck={false} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </Field>
            <Field label="Password (10+ characters)">
              <Input type="text" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Field>
          </div>
          <Button
            variant="primary"
            size="sm"
            loading={busy}
            disabled={!form.username.trim() || form.password.length < 10 || (form.role === "learner" && !form.learner_id)}
            onClick={() => void create()}
          >
            Create account
          </Button>
        </div>
      </div>
    </Card>
  );
}

function MeCard() {
  const { me, signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const change = async () => {
    setBusy(true);
    try {
      await ucApi.changePassword(cur, next);
      setCur("");
      setNext("");
      toast.success("Password changed. Other devices are signed out.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader title={`You (${me.username})`} icon={<UserRound />} />
      <div className="space-y-4 px-5 pb-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-muted-foreground">Look</span>
          <Segmented
            value={theme}
            onChange={setTheme}
            options={[
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ]}
            size="sm"
          />
          <div className="flex-1" />
          <Button variant="secondary" size="sm" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Current password">
            <Input type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} />
          </Field>
          <Field label="New password (10+)">
            <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
          <Button variant="secondary" size="md" loading={busy} disabled={!cur || next.length < 10} onClick={() => void change()}>
            Change password
          </Button>
        </div>
      </div>
    </Card>
  );
}
