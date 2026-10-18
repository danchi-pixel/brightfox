/** Product name shown in the UI (VITE_APP_NAME, so the name can change before launch without code edits). */
export const APP_NAME: string = (import.meta.env.VITE_APP_NAME as string | undefined)?.trim() || "BrightFox";
