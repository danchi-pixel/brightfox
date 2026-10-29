import { Dialog } from "radix-ui";
import { useRef, useState } from "react";
import { useT } from "../learning/i18n";
import { Chat } from "./ChatPage";

/** Help is a modal, not a route change: the exercise and all its local state stay mounted beneath it. */
export function FoxyHelp({ lid, topicId, taskId, onClose }: {
  lid: number;
  topicId: string;
  taskId?: string;
  onClose: () => void;
}) {
  const { t } = useT();
  const [cid, setCid] = useState<number | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--overlay)]" />
        <Dialog.Content
          className="fixed inset-0 z-50 bg-background"
          aria-describedby={undefined}
          onOpenAutoFocus={(event) => {
            opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
            // Keep the exercise's scroll position and avoid opening the keyboard on touch devices.
            if (window.matchMedia("(pointer: coarse)").matches) event.preventDefault();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            opener.current?.focus({ preventScroll: true });
          }}
        >
          <Dialog.Title className="sr-only">{t("foxy")}</Dialog.Title>
          <Chat lid={lid} cid={cid} topicId={topicId} taskId={taskId} onClose={onClose} onChatCreated={setCid} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
