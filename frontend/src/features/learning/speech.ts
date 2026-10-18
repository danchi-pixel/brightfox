/** Reading text aloud with the browser's own voice (nothing is recorded or sent anywhere). */

export const CAN_SPEAK = typeof window !== "undefined" && "speechSynthesis" in window;

/** BCP-47 tags for the languages we read aloud. */
const LANG_TAG = { en: "en-GB", sl: "sl-SI" } as const;

export function hasVoice(lang: keyof typeof LANG_TAG): boolean {
  if (!CAN_SPEAK) return false;
  const prefix = lang;
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(prefix));
}

export function speak(text: string, rate = 0.85, lang: keyof typeof LANG_TAG = "en") {
  if (!CAN_SPEAK) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG_TAG[lang];
  u.rate = rate;
  const voices = synth.getVoices();
  const voice = voices.find((v) => v.lang === LANG_TAG[lang]) ?? voices.find((v) => v.lang.toLowerCase().startsWith(lang));
  if (voice) u.voice = voice;
  synth.speak(u);
}
