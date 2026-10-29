/**
 * The parent's overview: each learner at a glance (their classroom, Foxy today), topics waiting for a check,
 * and what Foxy costs this month.
 */
import { ArrowRight, BookOpenCheck, CalendarDays, KeyRound, MessageCircle } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, ErrorState, PageLoader } from "@/components/ui/misc";
import { useOverview, useStudioTopics } from "../learning/api";
import { LearnerAvatar, SubjectBubble } from "../learning/ui";
import { ApprovalBadge, gradeName, PageTitle, plural, usd } from "./common";

export default function OverviewPage() {
  const overview = useOverview();
  const topics = useStudioTopics();
  const navigate = useNavigate();
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />;
  if (!overview.data) return <PageLoader />;
  const o = overview.data;
  const waiting = (topics.data?.topics ?? []).filter((t) => !t.approved && (t.scope === "family" || t.outdated_ids.length));

  return (
    <div className="space-y-6">
      <PageTitle title={o.family.name} sub="Your kids' classrooms at a glance: what to check, how they're doing, and Foxy." />
      {o.local_auto_assignment && (
        <p className="rounded-2xl bg-info/10 p-4 text-sm">
          Local classroom: new and updated topics and mock tests appear automatically for the child they are assigned to.
          Refresh to load the latest content. Approval controls below apply to the published site.
        </p>
      )}

      {!o.learners.length ? (
        <EmptyState icon={<BookOpenCheck />} title="No learners yet" action={<Button variant="primary" onClick={() => navigate("/family")}>Add a learner</Button>}>
          Add your kids on the Family page.
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {o.learners.map((lr) => (
            <Card key={lr.id} className="space-y-3 p-4">
              <div className="flex items-center gap-3">
                <LearnerAvatar learner={lr} size="lg" />
                <div className="min-w-0 flex-1">
                  <div className="font-display text-2xl leading-tight">{lr.name}</div>
                  <div className="text-sm text-muted-foreground">{gradeName(lr.grade, true)}</div>
                </div>
              </div>
              <div className="text-sm text-muted-foreground">
                Foxy today {lr.today_messages} of {lr.tutor_daily_limit}
                {!lr.tutor_enabled && " (switched off)"} · this month {plural(lr.month_calls, "answer")}, about {usd(lr.month_cost_usd)}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="primary" size="sm" onClick={() => navigate(`/l/${lr.id}`)}>
                  Open {lr.name}'s classroom <ArrowRight />
                </Button>
                <Button variant="secondary" size="sm" onClick={() => navigate(`/tests?learner=${lr.id}`)}>
                  <CalendarDays /> Tests and gaps
                </Button>
                <Button variant="secondary" size="sm" onClick={() => navigate(`/foxy?learner=${lr.id}`)}>
                  <MessageCircle /> Chats
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-display text-xl">{o.local_auto_assignment ? "Review before publishing" : "Waiting for your check"}</h2>
          <Link to="/topics" className="text-sm font-medium text-primary underline">
            All topics
          </Link>
        </div>
        {!waiting.length ? (
          <p className="text-sm text-muted-foreground">Nothing to check. New topics appear here when Claude adds them.</p>
        ) : (
          <div className="space-y-1.5">
            {waiting.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => navigate(`/topics?id=${t.id}`)}
                className="flex w-full items-center gap-3 rounded-2xl border border-border bg-card-2 px-3 py-2 text-left hover:border-input"
              >
                <SubjectBubble subject={t.subject} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold leading-tight">{t.title}</span>
                  <span className="text-xs text-muted-foreground">
                    v{t.version}
                    {t.for.length ? ` · made for ${t.for.join(", ")}` : ""}
                  </span>
                </span>
                <ApprovalBadge card={t} />
              </button>
            ))}
          </div>
        )}
      </Card>

      <Card className="flex items-start gap-3 p-4">
        <span className={o.tutor.configured ? "rounded-2xl bg-success/10 p-2.5 text-success" : "rounded-2xl bg-warning/15 p-2.5 text-warning"}>
          <KeyRound className="size-5" />
        </span>
        <div className="min-w-0 flex-1 space-y-1 text-sm">
          <div className="font-semibold">{o.tutor.configured ? `Foxy is ready (${o.tutor.model}, ${o.tutor.effort} effort)` : "Foxy isn't set up yet"}</div>
          <p className="text-muted-foreground">
            This month: {plural(o.tutor.month_calls, "answer")}, about {usd(o.tutor.month_cost_usd)}
            {o.tutor.budget_usd !== null ? ` of your ${usd(o.tutor.budget_usd)} budget` : " (no monthly budget set)"}.{" "}
            <Link to="/foxy" className="font-medium text-primary underline">
              Foxy and AI settings
            </Link>
          </p>
        </div>
      </Card>

      <Card className="p-4 text-sm leading-relaxed text-muted-foreground">
        <b className="text-foreground">Adding topics:</b> ask Codex or Claude to make a topic for Alan or Erik from their school material. Each topic can include study pages, practice and a challenge.
        {o.local_auto_assignment ? " Assigned content appears in the local classroom after refresh; progress stays saved." : " Review and approve the topic before it appears in the child's classroom."}
      </Card>
    </div>
  );
}
