/** Reading text aloud with the browser's own voice (nothing is recorded or sent anywhere). */

export const CAN_SPEAK = typeof window !== "undefined" && "speechSynthesis" in window;

/** BCP-47 tags for the languages we read aloud. */
const LANG_TAG = { en: "en-GB", sl: "sl-SI" } as const;
export type SpeechLang = keyof typeof LANG_TAG;

export function hasVoice(lang: SpeechLang): boolean {
  if (!CAN_SPEAK) return false;
  const prefix = lang;
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(prefix));
}

function utterance(text: string, rate: number, lang: SpeechLang): SpeechSynthesisUtterance {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG_TAG[lang];
  u.rate = rate;
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find((v) => v.lang === LANG_TAG[lang]) ?? voices.find((v) => v.lang.toLowerCase().startsWith(lang));
  if (voice) u.voice = voice;
  return u;
}

export function speak(text: string, rate = 0.85, lang: SpeechLang = "en") {
  if (!CAN_SPEAK) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  synth.speak(utterance(text, rate, lang));
}

/** Read aloud and wait until it's said. Resolves anyway after a generous time limit, because some browsers
 * never fire "end" (and at once when there's no voice). */
export function speakAndWait(text: string, rate = 0.85, lang: SpeechLang = "en"): Promise<void> {
  if (!CAN_SPEAK) return Promise.resolve();
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    synth.cancel();
    const u = utterance(text, rate, lang);
    const limit = window.setTimeout(resolve, 2500 + text.length * 140);
    const done = () => {
      window.clearTimeout(limit);
      resolve();
    };
    u.onend = done;
    u.onerror = done;
    synth.speak(u);
  });
}

export function stopSpeaking() {
  if (CAN_SPEAK) window.speechSynthesis.cancel();
}
