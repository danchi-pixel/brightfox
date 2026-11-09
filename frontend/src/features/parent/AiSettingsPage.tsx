/**
 * AI settings (parents): Foxy's Anthropic API key. A parent can enter or replace it, check it and remove it.
 * The server only ever says whether there is a key, where it's kept and its last 4 characters.
 */
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Field, Input } from "@/components/ui/input";
import { Card, CardHeader, ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { qk, ucApi, useAiKey, type AiKeyStatus } from "../learning/api";
import { PageTitle } from "./common";

const KEY_PATTERN = /^sk-ant-[A-Za-z0-9_-]+$/;

export function keyStatusLine(s: AiKeyStatus): string {
  if (!s.configured) return "No key yet: Foxy shows \"not ready\" to the kids.";
  const where = s.source === "app" ? "saved in the app" : "saved on the server";
  return s.hint ? `Key set (…${s.hint}), ${where}.` : `Key set, ${where}.`;
}

export default function AiSettingsPage() {
  const status = useAiKey();
  if (status.isError) return <ErrorState error={status.error} onRetry={() => void status.refetch()} />;
  if (!status.data) return <PageLoader />;
  return (
    <div className="space-y-5">
      <PageTitle title="AI settings" sub="Foxy runs on Anthropic's API and is paid from your API credit. Models, effort and the monthly budget are on the Foxy page.">
        <Link to="/foxy" className="text-sm font-medium text-primary underline">
          Models and costs
        </Link>
      </PageTitle>
      <KeyCard status={status.data} />
    </div>
  );
}

function KeyCard({ status }: { status: AiKeyStatus }) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);
  const trimmed = key.trim();
  const looksValid = KEY_PATTERN.test(trimmed);

  const run = async (what: "save" | "test" | "remove", fn: () => Promise<void>) => {
    setBusy(what);
    try {
      await fn();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  const refresh = (s: AiKeyStatus) => {
    qc.setQueryData(qk.aiKey, s);
    void qc.invalidateQueries({ queryKey: qk.all });
  };

  const save = () =>
    run("save", async () => {
      const s = await ucApi.setAiKey(trimmed);
      setKey("");
      refresh(s);
      toast.success("Key saved. Foxy uses it from now on.");
    });
  const test = () =>
    run("test", async () => {
      const r = await ucApi.testAiKey();
      if (r.ok) toast.success(r.message);
      else toast.error(r.message);
    });
  const remove = async () => {
    const fallback = "Foxy falls back to the server's key, if there is one; otherwise he isn't ready until a key is entered.";
    if (!(await confirm({ title: "Remove the key saved in the app?", description: fallback, confirmLabel: "Remove", danger: true }))) return;
    await run("remove", async () => {
      refresh(await ucApi.removeAiKey());
      toast.success("Removed.");
    });
  };

  return (
    <Card>
      <CardHeader title="Anthropic API key" icon={<KeyRound />} />
      <div className="space-y-4 px-5 pb-5">
        <p className="font-medium" data-testid="key-status">
          {keyStatusLine(status)}
          {status.updated_at && <span className="ml-1 text-sm font-normal text-muted-foreground">Changed {new Date(status.updated_at).toLocaleString()}.</span>}
        </p>
        {!status.can_manage ? (
          <p className="text-sm text-muted-foreground">The key for this installation is managed by its owner.</p>
        ) : (
          <>
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (looksValid) void save();
              }}
            >
              <Field
                label={status.configured ? "Replace the key" : "Enter the key"}
                hint="From console.anthropic.com → API keys. It starts with sk-ant-. Only the last 4 characters are ever shown again."
                className="min-w-0 flex-1"
              >
                <Input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="sk-ant-…"
                  aria-label="Anthropic API key"
                />
              </Field>
              <Button type="submit" variant="primary" size="md" disabled={!looksValid || busy !== null} loading={busy === "save"}>
                Save
              </Button>
            </form>
            {trimmed && !looksValid && <p className="text-sm text-danger">That doesn't look like an Anthropic key (sk-ant-…).</p>}
            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              <Button variant="secondary" size="sm" disabled={!status.configured || busy !== null} loading={busy === "test"} onClick={() => void test()}>
                Test key
              </Button>
              <Button variant="ghost" size="sm" disabled={status.source !== "app" || busy !== null} loading={busy === "remove"} onClick={() => void remove()}>
                Remove key saved in the app
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Test asks Anthropic for its model list, which costs nothing. A key saved here wins over the server's key and works at once, without a restart. It's kept in a private file on the server, not in the backups: after moving to a new server, enter it again.
            </p>
          </>
        )}
      </div>
    </Card>
  );
}
