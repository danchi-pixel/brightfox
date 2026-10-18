import { Lock } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import type { Me } from "@/lib/auth";
import { APP_NAME } from "@/lib/brand";

/** One sign-in for parents and kids (each kid has their own username). Bilingual: it's the first screen. */
export function LoginPage({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await api.post<Me>("/api/auth/login", { username: username.trim(), password });
      setPassword("");
      onSignedIn(me);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="soft-gradient flex min-h-dvh items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-3xl border border-border bg-card p-6 shadow-card sm:p-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <img src="/favicon.svg" alt="" className="size-16" />
          <h1 className="font-display text-4xl text-primary">{APP_NAME}</h1>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Lock className="size-4" /> Prijava · Sign in
          </p>
        </div>
        <Field label="Uporabniško ime · Username">
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
            className="h-12 text-base"
          />
        </Field>
        <Field label="Geslo · Password">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required className="h-12 text-base" />
        </Field>
        {error && (
          <p className="rounded-xl bg-danger/10 p-3 text-sm text-danger" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy} disabled={!username.trim() || !password}>
          Prijava · Sign in
        </Button>
      </form>
    </div>
  );
}
