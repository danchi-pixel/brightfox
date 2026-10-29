/**
 * Full-screen chat with Foxy. ``/l/:lid/chat/new?subject=math`` (or ``?topic=<id>&task=<id>`` from a topic)
 * starts a chat with its first message; after that the chat has its own address. Photos (up to 4 per
 * message) are shrunk to JPEGs in the browser before they are sent. Parents read a learner's chats here
 * (read-only) and try Foxy in their own test chats.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUp, ImagePlus, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Feedback } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { qk, SUBJECTS, ucApi, useChat, useLearnerHome, type ChatMessage, type ChatView, type Subject } from "../learning/api";
import { photoToJpeg } from "../learning/image";
import { LangContext, useT } from "../learning/i18n";
import { FoxAvatar, RichText, SUBJECT_META } from "../learning/ui";

const MAX_PHOTOS = 4;

export default function ChatPage() {
  const { lid: lidParam = "", cid: cidParam = "new" } = useParams();
  const [params] = useSearchParams();
  const lid = Number(lidParam) || 0;
  const cid = cidParam === "new" ? null : Number(cidParam) || null;
  const wanted = params.get("subject") as Subject | null;
  const subject: Subject = wanted && SUBJECTS.includes(wanted) ? wanted : "other";
  const navigate = useNavigate();
  const home = useLearnerHome(lid);
  return (
    <LangContext.Provider value={home.data && !home.data.owner ? home.data.lang : null}>
      <Chat
        lid={lid}
        cid={cid}
        subject={subject}
        topicId={params.get("topic")}
        taskId={params.get("task")}
        onClose={() => navigate(`/l/${lid}`)}
        onChatCreated={(id) => navigate(`/l/${lid}/chat/${id}`, { replace: true })}
      />
    </LangContext.Provider>
  );
}

/** The same chat can live in its own route or in help over an exercise; only the caller navigates. */
export function Chat({ lid, cid, subject = "other", topicId, taskId, onClose, onChatCreated }: {
  lid: number;
  cid: number | null;
  subject?: Subject;
  topicId?: string | null;
  taskId?: string | null;
  onClose: () => void;
  onChatCreated: (id: number) => void;
}) {
  const { t } = useT();
  const qc = useQueryClient();
  const chat = useChat(lid, cid);
  const home = useLearnerHome(lid);

  const [text, setText] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [sending, setSending] = useState<{ text: string; photos: string[] } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const view = chat.data;
  const messages = view?.messages ?? [];
  const topicCard = home.data?.topics.find((x) => x.id === (view?.chat.topic_id ?? topicId));
  const chatSubject = view?.chat.subject ?? topicCard?.subject ?? subject;
  const canSend = cid ? !!view?.can_send : true;
  const left = home.data?.tutor.left_today;
  const owner = home.data?.owner ?? false;
  const tutorOff = home.data && (!home.data.tutor.configured || (owner && !home.data.tutor.enabled));

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, sending]);

  const pick = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files).slice(0, MAX_PHOTOS - photos.length)) {
      try {
        const jpeg = await photoToJpeg(file);
        setPhotos((p) => (p.length < MAX_PHOTOS ? [...p, jpeg] : p));
      } catch {
        toast.error(t("photoTooBig"));
      }
    }
  };

  const send = async () => {
    const body = { text: text.trim(), images: photos };
    if ((!body.text && !body.images.length) || sending) return;
    setSending({ text: body.text, photos: body.images });
    setText("");
    setPhotos([]);
    try {
      const res: ChatView = cid
        ? await ucApi.send(lid, cid, body)
        : await ucApi.newChat(lid, topicId ? { ...body, topic_id: topicId, task_id: taskId ?? undefined } : { ...body, subject });
      qc.setQueryData(qk.chat(lid, res.chat.id), res);
      void qc.invalidateQueries({ queryKey: qk.home(lid) });
      void qc.invalidateQueries({ queryKey: qk.chats(lid) });
      if (!cid) onChatCreated(res.chat.id);
    } catch (e) {
      // Nothing was saved: give the message back so it can be sent again.
      setText(body.text);
      setPhotos(body.images);
      toast.error(errorMessage(e));
    } finally {
      setSending(null);
    }
  };

  const Icon = SUBJECT_META[chatSubject].icon;
  return (
    <div className="flex h-dvh flex-col bg-background">
      <header className="shrink-0 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-3 px-4">
          <button onClick={onClose} className="-ml-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={t("back")}>
            <X className="size-6" />
          </button>
          <FoxAvatar size="sm" />
          <div className="min-w-0 flex-1">
            <div className="truncate font-semibold leading-tight">{t("foxy")}</div>
            <div className="flex items-center gap-1 truncate text-xs text-muted-foreground">
              <Icon className="size-3.5" style={{ color: SUBJECT_META[chatSubject].color }} /> {topicCard?.title ?? t(SUBJECT_META[chatSubject].key)}
              {view?.chat.parent_test && <span className="ml-1 rounded-full bg-warning/15 px-1.5 text-warning">{t("parentTest")}</span>}
            </div>
          </div>
          {owner && left !== undefined && <span className="shrink-0 text-xs text-muted-foreground">{t("leftToday", { n: left })}</span>}
        </div>
      </header>

      <main className="scrollbar-thin flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-3 px-4 py-4">
          {chat.isError ? (
            <ErrorState error={chat.error} onRetry={() => void chat.refetch()} />
          ) : cid && !view ? (
            <PageLoader />
          ) : (
            <>
              <Bubble role="assistant">
                <RichText text={topicCard ? t("chatHelloTopic", { title: topicCard.title }) : t("chatHello")} />
              </Bubble>
              {messages.map((m) => (
                <MessageBubble key={m.id} m={m} />
              ))}
              {sending && (
                <>
                  <Bubble role="user">
                    <Photos srcs={sending.photos} />
                    {sending.text && <RichText text={sending.text} />}
                  </Bubble>
                  <div className="flex items-center gap-2 pl-1 text-sm text-muted-foreground">
                    <FoxAvatar size="sm" />
                    <Loader2 className="size-4 animate-spin" /> {t("thinking")}
                  </div>
                </>
              )}
            </>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="pb-safe shrink-0 border-t border-border bg-card/95 backdrop-blur">
        <div className="mx-auto max-w-2xl space-y-2 px-4 py-3">
          {!canSend ? (
            <p className="text-center text-sm text-muted-foreground">{t("readOnly")}</p>
          ) : tutorOff ? (
            <Feedback tone="soft">{home.data!.tutor.configured ? t("switchedOff") : t("notReady")}</Feedback>
          ) : owner && left === 0 ? (
            <Feedback tone="soft">{t("noneLeft")}</Feedback>
          ) : (
            <>
              {photos.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {photos.map((p, i) => (
                    <div key={i} className="relative">
                      <img src={p} alt="" className="h-20 rounded-xl border border-border" />
                      <button
                        onClick={() => setPhotos((ps) => ps.filter((_, j) => j !== i))}
                        className="absolute -right-2 -top-2 rounded-full bg-card p-1 text-muted-foreground shadow ring-1 ring-border hover:text-foreground"
                        aria-label={t("removePhoto")}
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-end gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => void pick(e.target.files).finally(() => (e.target.value = ""))}
                />
                <Button
                  variant="secondary"
                  size="icon-lg"
                  onClick={() => fileRef.current?.click()}
                  aria-label={t("addPhoto")}
                  title={t("addPhoto")}
                  disabled={!!sending || photos.length >= MAX_PHOTOS}
                >
                  <ImagePlus />
                </Button>
                <Textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !("ontouchstart" in window)) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                  placeholder={t("typeHere")}
                  maxLength={2000}
                  rows={1}
                  className="max-h-40 min-h-14 flex-1 resize-none py-3.5 text-base"
                  disabled={!!sending}
                />
                <Button variant="primary" size="icon-lg" onClick={() => void send()} disabled={!!sending || (!text.trim() && !photos.length)} aria-label={t("send")}>
                  <ArrowUp />
                </Button>
              </div>
              {owner && <p className="text-center text-[11px] text-muted-foreground">{t("parentsCanRead")}</p>}
            </>
          )}
        </div>
      </footer>
    </div>
  );
}

function Bubble({ role, children }: { role: ChatMessage["role"]; children: React.ReactNode }) {
  const mine = role === "user";
  return (
    <div className={cn("flex items-end gap-2", mine && "justify-end")}>
      {!mine && <FoxAvatar size="sm" />}
      <div
        className={cn(
          "max-w-[85%] rounded-3xl px-4 py-2.5 text-[15px] leading-relaxed",
          mine ? "rounded-br-lg bg-primary text-primary-foreground" : "rounded-bl-lg border border-border bg-card",
        )}
      >
        {children}
      </div>
    </div>
  );
}

function Photos({ srcs }: { srcs: string[] }) {
  if (!srcs.length) return null;
  return (
    <div className={cn("mb-1.5 grid gap-1.5", srcs.length > 1 && "grid-cols-2")}>
      {srcs.map((src, i) => (
        <a key={i} href={src} target="_blank" rel="noreferrer">
          <img src={src} alt="" className="max-h-60 rounded-xl" loading="lazy" />
        </a>
      ))}
    </div>
  );
}

function MessageBubble({ m }: { m: ChatMessage }) {
  return (
    <Bubble role={m.role}>
      <Photos srcs={m.images} />
      {m.text && <RichText text={m.text} />}
    </Bubble>
  );
}
