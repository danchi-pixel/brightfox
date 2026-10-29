/**
 * The parents' guide: how BrightFox works, in Slovenian and English (parents only). Keep it in step with the
 * features (AGENTS.md section 7).
 */
import { useState } from "react";
import { Segmented } from "@/components/ui/misc";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type L = "sl" | "en";
type Section = { id: string; icon: string; title: Record<L, string>; body: Record<L, (string | string[])[]> };

/* A string is a paragraph; a string[] is a bullet list. **bold** works inside both. */
const SECTIONS: Section[] = [
  {
    id: "english-collection", icon: "💬",
    title: { sl: "Angleščina na enem mestu", en: "English in one place" },
    body: {
      sl: ["V učilnici odprite **Angleščina**. Tu so skupaj vse dostopne angleške teme, njihove razlage, kartice, vaje, Liga prvakov, ustno spraševanje in poskusni testi. Datumi šolskih testov in načrti so pod **Testi in priprava**; dosedanji napredek pod **Moj napredek**.", "Gre za ureditev obstoječih gradiv. Vprašanja, točkovanje, odobritve in napredek ostanejo isti. Nove teme in testi iz angleščine se vključijo samodejno, ko so otroku dostopni. Izhod iz angleške vaje ali testa se vrne v Angleščino."],
      en: ["Open **Angleščina** in the classroom for all accessible English lessons, notes, flashcards, practice, Champions League, oral practice and mocks. Scheduled school tests and plans appear under **Testi in priprava**, and existing progress under **Moj napredek**.", "This organizes existing materials without changing questions, scoring, approvals or progress. Newly accessible English topics and tests join automatically. Leaving an English lesson or test returns to the collection."],
    },
  },
  {
    id: "science-bank",
    icon: "🌿",
    title: { sl: "Erikovo naravoslovje", en: "Erik's science practice" },
    body: {
      sl: ["V Erikovi učilnici odprite **Erikovo naravoslovje**. Zbirka povezuje razlage po temah, kvize, izvorne slike, kartice in ustno vajo. **Poskusno ustno ocenjevanje** sestavi 5–10 vprašanj; ne daje uradne šolske ocene.", "Otrok naj najprej odgovori na glas ali zapiše misel, nato razkrije primer odgovora in pomembne točke. **Znam / Še vadim / Ne znam še** so samoocene. Ni snemanja, prepoznavanja govora ali klica AI. Besedilni osnutek se ne shranjuje; napredek in nadaljevanje vaje se shranita v račun. Kartice dajejo prednost šibkejšim odgovorom in uporabljajo razmake ponavljanja do 30 dni.", "**Viri in opombe** pokažejo pokritost snovi, fotografije in nejasnosti za pregled. Izvorne slike so zasebne datoteke, dostopne samo prek odobrene teme. Ob prenosu na drug računalnik ali strežnik je treba prenesti tudi te datoteke. Starševski predogled ne spreminja otrokovega napredka. Napredek zbirke je prikazan znotraj zbirke in se ne prišteva pripravljenosti drugih testov."],
      en: ["Open **Erikovo naravoslovje** in Erik's classroom for topic notes, quizzes, source pictures, flashcards and oral rehearsal. Mock oral sessions draw 5–10 questions and never assign an official school grade.", "The learner attempts an answer before revealing a model answer and key-point checklist. Recall ratings are self-assessments. There is no microphone recording, speech recognition or AI call. Typed drafts are not stored; progress and session continuation are saved to the account. Flashcards prioritize weaker recall and space reviews up to 30 days apart.", "**Viri in opombe** contains the coverage matrix and source ambiguities. Source pictures require authorized topic access and must also be transferred when moving the installation. Parent previews never save learner progress. Bank progress is separate from the readiness calculations for other tests."],
    },
  },
  {
    id: "localhost",
    icon: "💻",
    title: { sl: "Lokalna učilnica", en: "Local classroom" },
    body: {
      sl: ["Na tem računalniku **start.bat** odpre najnovejšo kodo na **http://localhost:7686**. Alan in Erik imata svoja profila. Nove veljavne teme in poskusni testi se ob osvežitvi samodejno prikažejo otroku, za katerega so napisani. Napredek ostane shranjen.", "Lokalno samodejno dodeljevanje velja samo za izrecno vključeni lokalni način. Na objavljeni strani brightfox.si še vedno veljajo odobritve vsake različice. Starševski ogled ostaja predogled; za shranjevanje vaj otrok uporablja svojo prijavo, geslo pa določi oseba sama."],
      en: ["On this computer, **start.bat** opens the current source at **http://localhost:7686**. Alan and Erik have separate profiles. Valid new topics and mock tests appear for their assigned child on refresh. Saved progress is preserved.", "Automatic assignment is limited to the explicitly enabled local mode. The published brightfox.si site still requires approval of each version. A parent's classroom view remains a preview; saving practice requires the child's own account, with a password set by a person."],
    },
  },
  {
    id: "what",
    icon: "🦊",
    title: { sl: "Kaj je BrightFox", en: "What BrightFox is" },
    body: {
      sl: [
        "BrightFox je družinska učilnica za snov, ki jo otroka jemljeta v šoli. Iz fotografij učbenika, delovnega zvezka ali zapiskov nastanejo **teme**, vsaka z enako potjo:",
        ["📖 **Uči se**: urejena snov (razlaga, tabele, »Pazi!« pasti), kartice in seznam »Kaj znam«.", "✏️ **Vaja**: naloge od lažjih k težjim, z namigi in rešitvami.", "🏆 **Liga prvakov**: težja raven, ki se odklene po vaji; zmaga prinese pokal.", "🎤 **Ustno spraševanje** in 📝 **poskusni test**, kjer sta pripravljena."],
        "Zraven je **Foxy**, lisička inštruktor za domače naloge: najprej pomaga z namigi, celotno rešitev pokaže šele, ko otrok res poskusi.",
        "Za teste vnesete datum in snov, otrok pa dobi odštevanje, približno pripravljenost in kratek načrt za vsak dan.",
      ],
      en: [
        "BrightFox is a family classroom for what the kids are learning at school. Photos of the textbook, workbook or notes become **topics**, each with the same path:",
        ["📖 **Learn**: the material in order (explanations, tables, \"Watch out!\" traps), flashcards and an \"I can\" list.", "✏️ **Practice**: tasks from easy to harder, with hints and solutions.", "🏆 **Champions League**: a harder level that opens after the practice; finishing it wins a trophy.", "🎤 **Oral exam** and 📝 **mock test**, where they exist."],
        "Next to that is **Foxy**, a fox homework tutor: hints first, the full solution only after the kid has really tried.",
        "For school tests you enter the date and what's on it; the kid gets a countdown, about how ready they are, and a short plan for every day.",
      ],
    },
  },
  {
    id: "who",
    icon: "👪",
    title: { sl: "Kdo vidi kaj", en: "Who sees what" },
    body: {
      sl: [
        ["**Starši** (danijel, daniela) vidita vse v družini: teme, rezultate, teste, vrzeli, pogovore s Foxyjem in stroške.", "**Otroka** (erik, alan) vidita samo svoj prostor. Drug drugega ne vidita.", "Druge družine (če bo aplikacija kdaj prodana) vaše družine nikoli ne vidijo, tudi ne vedo, da obstaja.", "Otroka sta obveščena, da starši lahko preberete njune pogovore s Foxyjem."],
        "Ko kot starš odprete otrokovo učilnico (»Open Erik's classroom«), vidite natanko to, kar vidi otrok, a nič od tega, kar poskusite, se ne shrani v njegov napredek.",
      ],
      en: [
        ["**Parents** (danijel, daniela) see everything in the family: topics, results, tests, gaps, Foxy chats and costs.", "**Kids** (erik, alan) see only their own space, not each other's.", "Other families (if the app is ever sold) never see yours, or even that it exists.", "The kids are told that parents can read their chats with Foxy."],
        "When you open a kid's classroom (\"Open Erik's classroom\") you see exactly what the kid sees, but nothing you try there is saved to their progress.",
      ],
    },
  },
  {
    id: "logins",
    icon: "🔑",
    title: { sl: "Prijave in gesla", en: "Logins and passwords" },
    body: {
      sl: [
        ["Vsak ima svojo prijavo. Geslo izbere vsak sam (vsaj 10 znakov).", "Svoje geslo spremenite na strani **Family → You**.", "Pozabljeno geslo otroka ali drugega starša: **Family → Sign-in accounts → New password**. Ta račun se odjavi z vseh naprav.", "Nov račun za otroka: **Family → Sign-in accounts → New account → For a kid**."],
      ],
      en: [
        ["Everyone has their own login and picks their own password (at least 10 characters).", "Change your own password on **Family → You**.", "A kid's (or the other parent's) forgotten password: **Family → Sign-in accounts → New password**. That account is signed out everywhere.", "A new login for a kid: **Family → Sign-in accounts → New account → For a kid**."],
      ],
    },
  },
  {
    id: "newtopic",
    icon: "📸",
    title: { sl: "Kako nastane nova tema", en: "How a new topic is made" },
    body: {
      sl: [
        ["Fotografirajte strani, ki se jih otrok uči (učbenik, delovni zvezek, zapiski, star test), in jih dajte v mapo na računalniku.", "Prosite AI pomočnika (Claude ali Codex), naj iz njih naredi temo za Erika ali Alana. Napiše **novo** snov in naloge (nikoli ne prepiše knjige), začne lažje od knjige in uporabi šolsko pisavo (decimalna vejica, · in :).", "Ko je tema objavljena, se pojavi na **Overview** pod »Waiting for your check«.", "Na strani **Topics** si oglejte naloge in odgovore, kliknite **Preview** ali **📖 Study pages**, nato **Approve for Erik**. Šele takrat jo otrok vidi."],
        "Vsaka sprememba teme dvigne njeno **verzijo**. Spremenjeno temo otrok spet vidi šele, ko jo znova odobrite (en klik). Tako nikoli ne dobi nečesa, česar niste preverili.",
      ],
      en: [
        ["Photograph the pages the kid is learning (textbook, workbook, notes, an old test) and put them in a folder on the computer.", "Ask the AI assistant (Claude or Codex) to make a topic for Erik or Alan. It writes **new** material and tasks (it never copies the book), starts easier than the book and uses the school's notation (decimal comma, · and :).", "Once it's published it appears on **Overview** under \"Waiting for your check\".", "On **Topics**, look through the tasks and answers, try **Preview** or **📖 Study pages**, then **Approve for Erik**. Only then does the kid see it."],
        "Every change to a topic raises its **version**. A changed topic comes back to the kid only after you approve it again (one click), so a kid never gets something you haven't checked.",
      ],
    },
  },
  {
    id: "results",
    icon: "📊",
    title: { sl: "Kako je šlo (rezultati)", en: "How the kids did" },
    body: {
      sl: [
        "Na strani **Topics** izberite temo. V polju **How the kids did** vidite za vsakega otroka:",
        ["koliko nalog je rešil prvič pravilno in katere so bile težke,", "**kaj je otrok dejansko vpisal** narobe (npr. »Spainish«), zato veste, kaj ga zmede,", "koliko kartic zna in katere točke »Kaj znam« še niso odkljukane,", "ali je osvojil pokal Lige prvakov."],
        "Naloge, ki so bile težke, se same vrnejo v **Moje napake**. Napake, ki jih vidite pri več temah, povejte AI pomočniku: v naslednjo temo bo vgradil »pasti« z razlago.",
      ],
      en: [
        "On **Topics**, pick a topic. **How the kids did** shows for each kid:",
        ["how many tasks were right on the first try and which were hard,", "**what the kid actually typed** wrong (e.g. \"Spainish\"), so you see what confuses them,", "how many flashcards they know and which \"I can\" points aren't ticked yet,", "whether they won the Champions League trophy."],
        "Hard tasks come back by themselves in **Moje napake**. Tell the AI assistant about mistakes you see: it builds them into the next topic as \"traps\" with an explanation.",
      ],
    },
  },
  {
    id: "tests",
    icon: "📅",
    title: { sl: "Testi, pripravljenost in načrt", en: "Tests, readiness and the plan" },
    body: {
      sl: [
        "Na **Overview** pri otroku kliknite **Tests and gaps**, nato **Add a test**: ime, datum, predmet, katere teme pridejo na test, ocena, ki jo ciljate, in opombe učitelja. Teme morajo biti otroku že odobrene.",
        "Otrok dobi na začetni strani **odštevanje**, **približno pripravljenost** (npr. 55 %) in **korake za danes**. Načrt se vsak dan sam preračuna: najprej najšibkejše veščine, zadnji dan pred testom je lahek (ponavljanje), poskusni test pride predzadnji dan.",
        "Pripravljenost je ocena iz: vaje (prvič pravilno), poskusnega testa, Lige prvakov, kartic in »Kaj znam«. Kar je starejše od 4 tednov, šteje pol. Samo kartice in kljukice brez nalog dajo največ 60 %. Nikoli ni ocena in nikoli se ne »pokvari«.",
        "Študijske dni in minute na dan (na strani **Family**) načrt upošteva.",
      ],
      en: [
        "On **Overview**, click **Tests and gaps** next to the kid, then **Add a test**: name, date, subject, which topics are on it, the grade you aim for, and the teacher's notes. The topics must already be approved for that kid.",
        "The kid's home then shows a **countdown**, **about how ready** they are (e.g. 55 %) and **today's steps**. The plan recalculates every day: weakest skills first, a light last day (review), the mock test on the second-to-last day.",
        "Readiness is an estimate from: practice (right first time), the mock test, the Champions League, flashcards and \"I can\". Results older than 4 weeks count half. Flashcards and ticks alone give at most 60 %. It's never a grade and never \"breaks\".",
        "The plan follows the kid's study days and minutes (set on **Family**).",
      ],
    },
  },
  {
    id: "gaps",
    icon: "🎯",
    title: { sl: "Vrzeli in Moje napake", en: "Gaps and Moje napake" },
    body: {
      sl: [
        "**Vrzeli** (stran Tests and gaps) pokažejo, kaj otrok še ne zna, najhujše najprej: 🚨 kritično (npr. snov na testu čez manj kot 10 dni pod 50 %, ali ista naloga narobe večkrat), ⚠️ pozornost, 💡 manjše. Pri vsaki je razlog in kaj je otrok vpisal.",
        "**Moje napake**: vsaka naloga, ki ni šla v prvo, se vrne po 1, 3, 7 in 14 dneh. Ko je štirikrat zapored pravilna, je »popravljena za vedno« (✅, ki ostane). 3 dni pred testom se vrnejo vse napake iz snovi testa.",
      ],
      en: [
        "**Gaps** (Tests and gaps page) show what a kid still misses, worst first: 🚨 critical (e.g. material on a test within 10 days below 50 %, or the same task wrong in several runs), ⚠️ attention, 💡 minor. Each shows the reason and what the kid typed.",
        "**Moje napake**: every task that wasn't right first time comes back after 1, 3, 7 and 14 days. Right first time four times in a row makes it \"corrected for good\" (a ✅ that stays). 3 days before a test, every mistake from the test's topics comes back.",
      ],
    },
  },
  {
    id: "mockoral",
    icon: "📝",
    title: { sl: "Poskusni test in ustno spraševanje", en: "Mock test and oral exam" },
    body: {
      sl: [
          "Dostopni poskusni testi so tudi pod pripadajočimi temami na otrokovi začetni strani, v razdelku **Teme**.",
        "**Poskusni test** je kot pravi: časovna omejitev, brez namigov, točke, rešitve na koncu. Najbolje nastane iz fotografije starega testa (oblika naloge, točkovanje). Odobrite ga na strani Topics (spodaj, »Mock tests«). Otrok vidi točke in kaj ponoviti, **oceno vidite samo starši**.",
        "**Ustno spraševanje**: Foxy prebere vprašanje na glas (glas brskalnika, nič se ne snema), otrok odgovor napiše, Foxy pove »pravilno / skoraj / še ne« in kaj dodati. Vsak preverjen odgovor šteje kot eno vprašanje Foxyju za ta dan. Na strani Tests and gaps vidite, kaj je otrok odgovarjal.",
      ],
      en: [
          "Available mock tests also appear under their linked topics in the **Topics** section of the kid's home page.",
        "A **mock test** is like the real one: a time limit, no hints, points, solutions at the end. It's best made from a photo of an old test (task types, points). Approve it on Topics (bottom, \"Mock tests\"). The kid sees points and what to repeat; **only parents see the grade estimate**.",
        "**Oral exam**: Foxy reads the question aloud (the browser's voice; nothing is recorded), the kid types the answer, Foxy says \"right / almost / not yet\" and what to add. Each checked answer counts as one Foxy question for the day. You see the answers on Tests and gaps.",
      ],
    },
  },
  {
    id: "foxy",
    icon: "🤖",
    title: { sl: "Foxy (inštruktor) in stroški", en: "Foxy (the tutor) and costs" },
    body: {
      sl: [
        ["Foxy najprej pomaga razmisliti (vprašanja, namigi), rešitev pokaže šele po resnih poskusih. Pozna šolske metode in pri temah tudi besede iz otrokove knjige (»Vprašaj Foxyja o tem«).", "Foxy deluje prek Anthropicovega API-ja in se plača iz vašega API dobroimetja. Brez ključa otrok vidi »Foxy še ni pripravljen«.", "Na strani **Foxy** nastavite za vsakega otroka: razred, koliko vprašanj na dan, ali je Foxy vklopljen, interese (za primere) in **zasebne opombe** (otrok jih ne vidi).", "Tam vidite tudi stroške tega meseca in približno ceno na 100 odgovorov, lahko pa nastavite **mesečni proračun**: ko ga porabite, Foxy počiva do 1. v mesecu.", "Cenejši modeli (Sonnet, Haiku) se pokažejo šele, ko prestanejo preizkus matematike in jezika.", "Pogovore otrok preberete na strani Foxy (Chats). Lahko pa Foxyja preizkusite sami (»Try Foxy as Erik«); ti pogovori so označeni kot preizkus in jih otrok ne vidi."],
        "Če Foxy zazna, da je otrok v stiski, ga prijazno napoti k staršem ali drugi odrasli osebi in na **TOM telefon 116 111**.",
      ],
      en: [
        ["Foxy helps the kid think first (questions, hints) and shows the solution only after real attempts. He knows the school's methods and, in topics, the words from the kid's own book (\"Ask Foxy about this\").", "Foxy runs on Anthropic's API and is paid from your API credit. Without a key the kid sees \"Foxy isn't ready yet\".", "On the **Foxy** page set for each kid: grade, questions per day, Foxy on/off, interests (for examples) and **private notes** (the kid never sees them).", "There you also see this month's costs and the approximate price per 100 answers, and you can set a **monthly budget**: when it's used up, Foxy rests until the 1st.", "Cheaper models (Sonnet, Haiku) appear only after they pass the maths and language checks.", "Read the kids' chats on the Foxy page (Chats). You can also try Foxy yourself (\"Try Foxy as Erik\"); those chats are marked as tests and hidden from the kid."],
        "If Foxy notices a kid is in distress, he kindly points them to a parent or another adult and to **TOM telefon 116 111**.",
      ],
    },
  },
  {
    id: "family",
    icon: "🏠",
    title: { sl: "Stran Family", en: "The Family page" },
    body: {
      sl: [
        ["Ime družine in jezik otroških zaslonov.", "**Learners**: ime, razred, jezik, avatar in barva, **običajni študijski dnevi in minute** (za načrt testov). Arhiviran otrok izgine iz seznamov, podatki ostanejo.", "**Sign-in accounts**: prijave za otroka ali drugega starša, novo geslo, brisanje prijave (delo otroka ostane).", "**You**: svetel ali temen videz, menjava gesla, odjava."],
      ],
      en: [
        ["The family's name and the language of the kids' screens.", "**Learners**: name, grade, language, avatar and colour, **usual study days and minutes** (for the test plan). An archived kid disappears from the lists; their data stays.", "**Sign-in accounts**: logins for a kid or the other parent, new passwords, deleting a login (the kid's work stays).", "**You**: light or dark look, change password, sign out."],
      ],
    },
  },
  {
    id: "privacy",
    icon: "🔒",
    title: { sl: "Zasebnost in varnost", en: "Privacy and safety" },
    body: {
      sl: [
        ["Vse je na vašem strežniku, za prijavo; iskalniki strani ne indeksirajo.", "Fotografije domačih nalog niso javne: vidi jih samo otrok in starši, prenesejo se le k Foxyju, ko otrok vpraša.", "Mikrofon in kamera sta za celo stran izklopljena; ustno spraševanje je pisno.", "Vsako noč se naredi varnostna kopija (baza in fotografije)."],
      ],
      en: [
        ["Everything is on your own server, behind sign-in; search engines don't index it.", "Homework photos are never public: only the kid and the parents see them, and they go to Foxy only when the kid asks.", "Microphone and camera are blocked for the whole site; the oral exam is typed.", "A backup (database and photos) is made every night."],
      ],
    },
  },
  {
    id: "faq",
    icon: "❓",
    title: { sl: "Pogosta vprašanja", en: "Questions" },
    body: {
      sl: [
        ["**Otrok ne vidi teme.** Odobrite trenutno verzijo zanj (Topics → izberite temo → kdo jo dobi → Approve). Če piše »Changed: check again«, je bila tema popravljena.", "**Foxy pravi, da ni pripravljen.** Manjka API ključ (enkrat ga vnese, kdor upravlja strežnik), ali je Foxy za otroka izklopljen (stran Foxy).", "**»Za danes je vprašanj dovolj.«** Otrok je porabil dnevno število vprašanj; povečajte ga na strani Foxy.", "**Liga prvakov je zaklenjena.** Odklene se, ko otrok vajo naredi do konca."],
      ],
      en: [
        ["**A kid doesn't see a topic.** Approve the current version for them (Topics → pick it → who gets it → Approve). \"Changed: check again\" means the topic was updated.", "**Foxy says he isn't ready.** The API key is missing (whoever runs the server adds it once), or Foxy is switched off for that kid (Foxy page).", "**\"That's all the questions for today.\"** The kid used the daily number of questions; raise it on the Foxy page.", "**The Champions League is locked.** It opens once the kid finishes the practice."],
      ],
    },
  },
];

function Rich({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}
    </>
  );
}

export default function GuidePage() {
  const { language } = useAuth();
  const [lang, setLang] = useState<L>(language === "en" ? "en" : "sl");
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-4xl leading-none">{lang === "sl" ? "Vodič za starše" : "Guide for parents"}</h1>
          <p className="mt-1.5 text-muted-foreground">
            {lang === "sl" ? "Kako BrightFox deluje, korak za korakom." : "How BrightFox works, step by step."}
          </p>
        </div>
        <Segmented<L>
          value={lang}
          onChange={setLang}
          options={[
            { value: "sl", label: "Slovenščina" },
            { value: "en", label: "English" },
          ]}
          size="sm"
        />
      </div>
      <nav className="flex flex-wrap gap-1.5">
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`} className="rounded-full bg-card-2 px-3 py-1 text-sm hover:bg-muted">
            {s.icon} {s.title[lang]}
          </a>
        ))}
      </nav>
      {SECTIONS.map((s) => (
        <section key={s.id} id={s.id} className="scroll-mt-20 space-y-3 rounded-3xl border border-border bg-card p-5">
          <h2 className="font-display text-2xl">
            {s.icon} {s.title[lang]}
          </h2>
          {s.body[lang].map((b, i) =>
            Array.isArray(b) ? (
              <ul key={i} className={cn("list-disc space-y-1 pl-5 leading-relaxed")}>
                {b.map((li, j) => (
                  <li key={j}>
                    <Rich text={li} />
                  </li>
                ))}
              </ul>
            ) : (
              <p key={i} className="leading-relaxed">
                <Rich text={b} />
              </p>
            ),
          )}
        </section>
      ))}
    </div>
  );
}
