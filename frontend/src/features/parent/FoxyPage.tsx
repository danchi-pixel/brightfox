/**
 * Foxy and AI (parents): which model does each job and what it costs, a monthly budget, each learner's
 * Foxy settings (grade, daily limit, interests, private notes), and every chat (read, delete, or try Foxy
 * yourself: test chats are hidden from the kid).
 */
import { useQueryClient } from "@tanstack/react-query";
import { Bot, MessageCircle, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Field, Input, NumberInput, Select, Textarea } from "@/components/ui/input";
import { Card, CardHeader, EmptyState, ErrorState, PageLoader, Switch } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { qk, ucApi, useAiSettings, useChats, useFamily, type AiSettings, type Learner } from "../learning/api";
import { LearnerAvatar, SubjectBubble } from "../learning/ui";
import { gradeName, PageTitle, plural, subjectName, usd } from "./common";

export default function FoxyPage() {
  const family = useFamily();
  const ai = useAiSettings();
  if (family.isError) return <ErrorState error={family.error} onRetry={() => void family.refetch()} />;
  if (!family.data || !ai.data) return <PageLoader />;
  const learners = family.data.learners.filter((l) => !l.archived);
  return (
    <div className="space-y-5">
      <PageTitle title="Foxy and AI" sub="Foxy is the homework tutor: hints before answers, in the school's own words. Every answer goes to the AI provider and is paid from your API credit." />
      <AiCard ai={ai.data} />
      {!learners.length ? (
        <EmptyState icon={<Bot />} title="No learners yet" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {learners.map((lr) => (
              <LearnerTutorCard key={lr.id} learner={lr} />
            ))}
          </div>
          <Chats learners={learners} />
        </>
      )}
    </div>
  );
}

const TIER_TEXT: Record<string, string> = { best: "best", balanced: "balanced", cheapest: "cheapest" };

function AiCard({ ai }: { ai: AiSettings }) {
  const qc = useQueryClient();
  const [budget, setBudget] = useState<string>(ai.budget_usd === null ? "" : String(ai.budget_usd));
  const [busy, setBusy] = useState(false);
  useEffect(() => setBudget(ai.budget_usd === null ? "" : String(ai.budget_usd)), [ai.budget_usd]);

  const save = async (body: Parameters<typeof ucApi.setAi>[0]) => {
    setBusy(true);
    try {
      await ucApi.setAi(body);
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success("Saved.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Models and costs" icon={<Bot />} />
      <div className="space-y-4 px-5 pb-5">
        <div className="divide-y divide-border/60">
          {ai.jobs.map((j) => (
            <div key={j.job} className="flex flex-wrap items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{j.label}</div>
                <div className="text-xs text-muted-foreground">
                  This month {plural(j.month_calls, "answer")}, {usd(j.month_cost_usd)}
                  {j.per_100_usd !== null ? ` · about ${usd(j.per_100_usd)} per 100 answers` : ""}
                </div>
              </div>
              <Select
                value={j.model}
                disabled={busy || j.options.length < 2}
                onChange={(e) => void save({ routes: [{ job: j.job, model: e.target.value, effort: j.effort }] })}
                aria-label={`Model for ${j.label}`}
                className="w-56"
              >
                {j.options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label} ({TIER_TEXT[o.tier] ?? o.tier})
                  </option>
                ))}
              </Select>
              <Select
                value={j.effort}
                disabled={busy}
                onChange={(e) => void save({ routes: [{ job: j.job, model: j.model, effort: e.target.value }] })}
                aria-label={`Effort for ${j.label}`}
                className="w-32"
              >
                {["low", "medium", "high"].map((e) => (
                  <option key={e} value={e}>
                    {e} effort
                  </option>
                ))}
              </Select>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Cheaper models (Sonnet, Haiku) appear here once they've passed the maths and language checks for that job. Lower effort answers faster and costs less.
        </p>
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <Field label="Monthly AI budget (USD)" hint="When it's used up, Foxy rests until the 1st. Empty = no limit (set one in the Anthropic Console too).">
            <Input type="number" min={0} max={1000} step={1} value={budget} onChange={(e) => setBudget(e.target.value)} className="w-40" />
          </Field>
          <Button variant="primary" size="md" loading={busy} onClick={() => void save({ budget_usd: budget.trim() === "" ? null : Number(budget) })}>
            Save budget
          </Button>
        </div>
      </div>
    </Card>
  );
}

function LearnerTutorCard({ learner }: { learner: Learner }) {
  const qc = useQueryClient();
  const initial = {
    grade: learner.grade,
    tutor_enabled: learner.tutor_enabled,
    tutor_daily_limit: learner.tutor_daily_limit,
    interests: learner.interests,
    tutor_notes: learner.tutor_notes,
  };
  const [p, setP] = useState(initial);
  const [busy, setBusy] = useState(false);
  useEffect(() => setP(initial), [learner]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = JSON.stringify(p) !== JSON.stringify(initial);
  const save = async () => {
    setBusy(true);
    try {
      await ucApi.patchLearner(learner.id, p);
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success(`Saved for ${learner.name}.`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <LearnerAvatar learner={learner} size="sm" /> {learner.name}
          </span>
        }
      />
      <div className="space-y-3 px-5 pb-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="School">
            <Select value={p.grade ?? ""} onChange={(e) => setP({ ...p, grade: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Not set</option>
              {Array.from({ length: 13 }, (_, i) => i + 1).map((g) => (
                <option key={g} value={g}>
                  {gradeName(g)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Foxy questions a day">
            <NumberInput value={p.tutor_daily_limit} min={0} max={200} onChange={(v) => setP({ ...p, tutor_daily_limit: v ?? 0 })} aria-label="Foxy questions a day" />
          </Field>
        </div>
        <Switch checked={p.tutor_enabled} onCheckedChange={(v) => setP({ ...p, tutor_enabled: v })} label="Foxy on" description="Off: the kid sees that Foxy is switched off." />
        <Field label="Interests" hint="Foxy uses them for examples now and then.">
          <Input value={p.interests} maxLength={200} onChange={(e) => setP({ ...p, interests: e.target.value })} placeholder="e.g. football, Minecraft" />
        </Field>
        <Field label="Private notes for Foxy" hint="Helps Foxy (what's hard, how their teacher does things). Never shown to the kid.">
          <Textarea value={p.tutor_notes} maxLength={1000} onChange={(e) => setP({ ...p, tutor_notes: e.target.value })} placeholder="e.g. Fractions are new this month." />
        </Field>
        <div className="flex justify-end">
          <Button variant="primary" size="sm" disabled={!dirty} loading={busy} onClick={() => void save()}>
            Save
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Chats({ learners }: { learners: Learner[] }) {
  const [params, setParams] = useSearchParams();
  const lid = Number(params.get("learner")) || learners[0].id;
  const learner = learners.find((l) => l.id === lid) ?? learners[0];
  const chats = useChats(learner.id);
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();

  const remove = async (cid: number) => {
    if (!(await confirm({ title: "Delete this chat?", description: "The messages and photos are removed for good.", confirmLabel: "Delete", danger: true }))) return;
    try {
      await ucApi.deleteChat(learner.id, cid);
      await qc.invalidateQueries({ queryKey: qk.all });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <Card>
      <CardHeader title="Chats" icon={<MessageCircle />} />
      <div className="space-y-3 px-5 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          {learners.map((k) => (
            <button
              key={k.id}
              type="button"
              aria-pressed={k.id === learner.id}
              onClick={() => setParams({ learner: String(k.id) }, { replace: true })}
              className={cn("inline-flex items-center gap-2 rounded-full border-2 px-3 py-1.5 text-sm font-medium", k.id === learner.id ? "border-primary bg-primary-soft" : "border-border bg-card")}
            >
              <LearnerAvatar learner={k} size="xs" /> {k.name}
            </button>
          ))}
          <div className="flex-1" />
          <Button variant="secondary" size="sm" onClick={() => navigate(`/l/${learner.id}/chat/new?subject=math`)}>
            <MessageCircle /> Try Foxy as {learner.name}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Your own tries are marked "Parent test", use {learner.name}'s grade and language, and are hidden from {learner.name}.
        </p>
        {chats.isError ? (
          <ErrorState error={chats.error} onRetry={() => void chats.refetch()} />
        ) : !chats.data ? (
          <PageLoader />
        ) : !chats.data.length ? (
          <p className="text-sm text-muted-foreground">No chats from {learner.name} yet.</p>
        ) : (
          <div className="divide-y divide-border/60">
            {chats.data.map((c) => (
              <div key={c.id} className="flex items-center gap-3 py-2.5">
                <SubjectBubble subject={c.subject} size="sm" />
                <Link to={`/l/${learner.id}/chat/${c.id}`} className="min-w-0 flex-1 hover:opacity-80">
                  <div className="truncate font-medium">{c.title || subjectName(c.subject)}</div>
                  <div className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                    <span>{new Date(c.updated_at).toLocaleString()}</span>
                    <span>{subjectName(c.subject)}</span>
                    <span>{c.messages} messages</span>
                    {c.cost_usd !== undefined && <span>about {usd(c.cost_usd)}</span>}
                    {c.topic_id && <span>from a topic</span>}
                    {c.parent_test && <span className="text-warning">Parent test</span>}
                  </div>
                </Link>
                <Button variant="ghost" size="icon-sm" aria-label="Delete chat" onClick={() => void remove(c.id)}>
                  <Trash2 />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
