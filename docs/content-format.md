# BrightFox: topics

A **topic** is one JSON file (in PitchDriven it was called a "practice set"). The file name is the topic's
id and starts with the date, so the newest comes first: `2026-10-17-ulomki-erik.json`. Where it lives
decides who may see it:

- `backend/app/content/data/families/<slug>/topics/`: one family only (made from that family's photos).
- `backend/app/content/data/global/topics/`: offered to every family (each parent still approves it per kid).

Ids are unique across all folders. Check every change with (from `backend`):

```
.venv\Scripts\python.exe -m app.content.checker
```

A topic reaches a learner only after a parent approves its **current version** for that learner. After any
change, raise `version`: the topic is taken away from the kids until it's checked again.

**Local authoring exception:** `start.bat` explicitly enables the household's local mode. Its active
profiles are Alan and Erik. Set `for` to `["Alan"]`, `["Erik"]`, or `["Alan", "Erik"]` in the one topic
or mock JSON file. Refresh localhost and the latest validated content appears for that child, without
another registry or approval step. Unassigned content still requires manual approval; content belonging
to another family never appears. Production keeps the version-specific approval rule above. File edits
are detected automatically; preserve IDs to retain progress. New activities must use this documented
format; an unrelated HTML page or an invalid JSON file is not automatically a BrightFox topic.

## Making a set from photos

The parent sends Claude photos of what a child is learning (textbook pages, a worksheet, notes)
and says who it's for. Claude then:

1. Works out the topic, the grade and the method the book uses (Slovenian terms and notation:
   decimal comma, `·` and `:`, "ulomek", "števec" …).
2. Writes **new** tasks on the same topic. The book's own tasks and text are never copied: the
   numbers, stories and wording change ("twist it"), with a few related bonus tasks beyond the book.
3. Starts **easier than the book** and builds up: about 3–4 warm-ups (level 1), 4–6 practice tasks
   (level 2), 2–3 challenges (level 3). Football stories are welcome.
4. Gives every task 1–2 hints that lead to the answer step by step (never the answer itself) and a
   short worked solution.
5. Writes a **study part** (`study`, below) that puts the pages in order: short notes with tables,
   flashcards for the words, and an "I can" list. The child's path is 📖 Uči se → ✏️ Vaja → 🏆 Liga prvakov.
6. Runs the checker and the backend tests, then deploys. The parent approves the set in the app.

The photos are not kept in the project.

### Language rules (Slovenian)

Never address the child with gendered forms: use the imperative ("Izračunaj", "Zapiši", "Nariši") and
present tense, no l-participles or adjectives about "you" ("Si naredil?", "pripravljen"). Characters in
stories can be anyone ("Luka je igral …"). The checker refuses the common gendered forms after "si",
"boš", "bi" and "nisi".

## Format 2 additions (all optional; format-1 files stay valid)

Set `"format": 2` when using them.

- `skills`: 1–12 `{id, title}`, the small skills a topic is made of ("Država → narodnost", "have got / has
  got"). Tasks, flashcards, goals and sections may name one with `"skill": "<id>"`. Mastery, the test plan
  and the gaps list work per skill, so give every task a skill in new topics.
- `study.goals` as `{id, text, skill}` instead of plain texts. Progress is stored by goal id, so goals can be
  reordered safely. Plain-text goals get the ids `g0, g1, …` by position: don't reorder those.
- `traps` on a task: up to 4 `{answer, why}`, known wrong answers (from the kids' typed mistakes). Typing
  exactly that answer shows the reason instead of a plain "try again".
- `parent`: the parent helper card: `school_method` (how school teaches it, ≤800), `typical_mistakes`
  (1–6), `car_questions` (1–8 `{q, a}`: quick oral questions for the car or dinner), `tips` (1–5).
- `oral`: 1–20 `{id, skill, question, key_points (1–6), model_answer}` for the oral exam. Foxy asks the
  question aloud and checks the typed answer against the key points.
- `terms`: 1–40 `{term, meaning}`, the book's own words, so Foxy explains things the way school does.

## Mock tests ("Poskusni test")

One JSON file per mock in `<scope>/mocks/` (next to `topics/`), approved per learner like topics. It should
look like the teacher's test: ask the parent for a photo of an old test and copy its layout (sections, kinds
of tasks, points), never its tasks.

```json
{
  "id": "2026-10-18-erik-english-people-mock", "version": 1, "subject": "english", "grade": 6,
  "title": "Poskusni test: …", "intro": "Kot pravi test: 30 minut, brez namigov …",
  "source": "For parents: where the layout came from.", "for": ["Erik"],
  "minutes": 30, "topics": ["2026-10-17-erik-english-people"],
  "scale": {"2": 50, "3": 63, "4": 76, "5": 90},
  "sections": [{"title": "A. Besedišče", "tasks": [{"id": "m-uncle", "topic": "…", "skill": "fam", "points": 1,
                 "kind": "text", "prompt": "My mum's brother is my ______.", "answer": "uncle", "solution": "…"}]}]
}
```

- `minutes` 5–120; `topics` 1–6 of the family's (or global) topics; `scale` optional (% of points per grade,
  shown to parents only as a grade estimate).
- Tasks are ordinary tasks plus `topic` (one of `topics`), optional `skill` (a skill of that topic) and
  `points` (0.5–20). No hints. `traps` and `say` work as in topics. Open tasks are self-checked against the
  solution at the end.
- The result feeds readiness (the mock's 25 %), and a test whose topics a mock covers gets the mock on the
  second-to-last study day.

## Oral exam

Topics with `oral` questions get "🎤 Ustno spraševanje": Foxy reads each question aloud (English topics in
English), the learner types the answer, and Foxy (the `oral_grading` AI job) answers right / partly / not
yet with one or two sentences, checked against `key_points`. Each checked answer counts as one Foxy
question for the day. Write the questions the way the teacher asks them.

## Video lesson ("🎬 Video lekcija")

An optional `video` makes an animated, narrated lesson that plays like a football match. The kid's topic
gets a 🎬 row, and parents get a 🎬 Video preview on Topics. There's no film file: the app animates the
scenes. Foxy's Slovene lines are captions (read aloud where the device has a Slovene voice), and English
lines are read aloud by the device's English voice. `{name}` becomes the learner's first name. Nothing is
saved: quizzes in the video only count "goals" for fun.

```json
"video": {
  "title": "⚽ Tekma: People are people",
  "scenes": [
    {"type": "intro", "emoji": "🏟️", "title": "People are people", "sub": "Unit 1", "foxy": "Živjo, {name}! Gremo!"},
    {"type": "rule", "skill": "hasgot", "title": "have got ali has got?", "foxy": "Kaj kdo ima?",
     "steps": [{"sl": "He, she, it → has got", "en": "Oblak has got big hands."}]},
    {"type": "pairs", "skill": "nat", "title": "Država → narodnost", "say": [0, 1], "pairs": [["Japan", "Japanese"], ["Holland", "Dutch"]]},
    {"type": "quiz", "skill": "poss", "question": "___ favourite player is Mbappé.", "options": ["He's", "His"], "answer": 1,
     "explain": "»Njegov« → His."},
    {"type": "recap", "title": "Končni žvižg!", "foxy": "Bravo, {name}!", "points": ["his = njegov, he's = he is"]}
  ]
}
```

The scene types:
- **`intro`:** a title card with `emoji`, `title` and `sub`. Use it for the kick-off and for half-time.
- **`rule`:** 1–8 `steps`, each with `sl` (a caption, ≤200 characters) and/or `en` (read aloud, ≤160 characters).
- **`pairs`:** a flip board of 2–12 `[left, right]` pairs. `say` lists which sides are read aloud.
- **`quiz`:** a `question`, 2–4 `options`, the `answer` index, an `explain` sentence, and an optional
  English `say`. The kid gets 6 seconds to tap.
- **`recap`:** 1–6 `points` at the final whistle.

Every scene may have `foxy`, a Slovene line said when it opens, and a `skill`. Rules for writing them:
- Use 3–30 scenes; about 15–20 makes roughly 5 minutes.
- Aim at the kid's real mistakes. The video is for the kid only and never leaves the family.
- Keep the Slovene gender-neutral (the checker includes the video).
- Raise `version`: parents approve the topic again.

## Format

```json
{
  "id": "2026-10-17-ulomki-erik",
  "version": 1,
  "subject": "math",
  "grade": 4,
  "title": "Ulomki: deli celote",
  "intro": "One or two sentences the child sees first.",
  "source": "For parents only: where it came from (e.g. 'Svet matematičnih čudes 4, p. 34–35').",
  "for": ["Erik"],
  "learn": [
    { "title": "Kaj je ulomek?", "text": "Short recap, simpler than the book.", "example": "Optional example." }
  ],
  "tasks": [ … ]
}
```

* `subject`: `math`, `slovene`, `english`, `science`, `society` or `other`.
* `grade`: 1–9 for primary school (razred), 10–13 for secondary school (1.–4. letnik).
* `for`: optional first names of the children the set was made for; the parent's approval starts with
  them picked ("Approve for Erik", one tap).
* `learn`: 0–8 recap cards shown before the tasks ("Spomni se").
* `tasks`: 1–40 tasks, ordered from easy to harder (levels never go down, bonus tasks aside).

### Tasks

Every task has `id` (unique in the set), `level` (1 warm-up, 2 practice, 3 challenge), `kind`,
`prompt`, `solution`, and optionally `hints` (0–3, shown one at a time), `extra: true` (a bonus
task beyond the book) and `say`: English the browser reads aloud with "Poslušaj" / "Počasi"
buttons (dictation, pronunciation). Nothing is recorded; without speech the words are shown instead.

| kind | Extra fields | Checked how |
|---|---|---|
| `choice` | `options` (2–6 texts), `answer` = the right option's number, counted from 0 | The options are shuffled for the child. |
| `number` | `answer`: `12`, `2.5` (a JSON number), `"2,5"`, `"3/4"` or `"1 3/4"`; optional `unit` (`"cm"`, `"€"`) | By value: for `"3/4"` the child may type 3/4, 0,75 or 0.75; "1.500" counts as 1,5 or 1500; a unit after the number is ignored. |
| `text` | `answer`, optional `accept` (other right answers), optional `exact: true` | Case, spaces, commas, a phone's ’ for ' and a final full stop or question mark never matter, so whole sentences work ("Popravi poved …"). Without `exact`, č/š/ž/é typed as c/s/z/e are accepted too; use `exact` for spelling practice. Capital letters can't be checked here: test those with a `choice` task. |
| `open` | none | Solved in the notebook. The child opens the solution and says "Znam" or "Še ne". |

### The challenge level ("Liga prvakov" 🏆)

Optional `"challenge": [ … ]` next to `"tasks"`: 1–20 harder tasks (all `level: 3`, at most one hint
each, ids different from the practice tasks). It opens for a child once they finish the practice,
and finishing it wins a trophy on the set. Make it real stretch work: no multiple choice, translations
from Slovene, whole-sentence dictation (`say`), the trickiest spellings, reversed tasks ("write the
question for this answer").

### The study part ("Uči se" 📖)

Optional `"study"` block: the topic's own study page, opened from the set's row. It has three tabs
(Snov, Kartice, Kaj znam) and prints cleanly ("Natisni").

```json
"study": {
  "goals": ["Znam povedati, od kod je kdo (I'm from …, I'm …)."],
  "sections": [
    {
      "title": "Države in narodnosti",
      "text": "Short explanation, simpler than the book.",
      "table": { "head": ["država", "narodnost", "slovensko"], "rows": [["Spain", "Spanish", "Španija"]], "say": [0, 1] },
      "examples": ["She's from Spain. She's Spanish."],
      "watch_out": [{ "wrong": "I am spanish.", "right": "I'm Spanish.", "why": "Narodnosti pišemo z veliko." }]
    }
  ],
  "cards": [{ "front": "teta", "back": "aunt" }]
}
```

* `goals`: 1–8 "I can …" lines (≤120 characters). The child ticks them; parents see what's not ticked yet.
* `sections`: 1–12, each with `title` (≤60) and optionally `text` (≤800), a `table` (`head` 2–4 columns,
  1–40 rows of the same length, cells ≤80 characters; `say` = the column numbers, from 0, that the row's
  🔊 button reads), `examples` (1–8 sentences ≤200, read aloud for English) and `watch_out` (1–6 typical
  mistakes `{wrong, right, why}`, shown as "Pazi!").
* `cards`: 0–80 flashcards, `front` in Slovene, `back` in English (read aloud). The back is the card's id,
  so backs must be different (ignoring case). The child sorts them into "Znam" / "Še ne" and can flip
  the direction; parents see how many are known.

Changing the study part is a change like any other: raise `version`.

### Optional source-based learning bank (`lab`)

A format-2 topic can include a `lab` object, validated by `app/content/lab.py`.
The normal family scope, `for` assignment and version approvals still apply. The learner
home links to `/l/:lid/science/:tid` when the topic has a bank.

- `sources`: stable `id`, allowlisted JPEG `file`, readable `label`, original `width`/`height`,
  clockwise `rotate` (0, 90 or -90), and optional `review` note for ambiguity.
- `lessons`: stable `id`, `title`, `icon`, `summary`, paragraph `notes`, `vocabulary` mapping
  and source IDs. Every lesson must have exercises.
- `questions`: stable `id`, lesson ID in `topic`, `kind`, `prompt`, model `answer`, important
  `points`, progressive `hints`, source IDs, and `difficulty` (1–3). Kinds are `oral`,
  `choice`, `boolean`, `fill`, `match`, `sort`, `sequence`, and `label`. Checked kinds use
  `correct`, with `items`/`options` as appropriate. Optional `card: true` enables flashcards;
  `followup` requires `followup_answer`.
- Optional question `image` uses a source ID, accessible `alt` and `box: [x,y,width,height]`
  in the oriented image's pixel coordinates. Inspect crops in the browser, including labels.
- `review_notes`: bank-level limitations. The viewer derives the coverage matrix from the bank.

Keep photos outside Git at `data/files/study/<scope>/<topic-id>/<filename>`. The authenticated
image route checks both learner scope and current topic visibility. Nothing is placed in
public frontend assets. Images load near the viewport and retain their original detail.

Bank progress uses the additive `lab_progress` table, separate from conventional readiness.
Card recall and practice answers are separate. Only self-ratings, counts, due dates and the
current session are stored; typed oral drafts and audio are not stored. Optimistic revisions
protect simultaneous tabs. A content edit must raise the topic `version`, keeping IDs stable.
See [Erik's source coverage and setup](erik-naravoslovje.md) for the first bank.

### How a run works

A wrong answer shows "have another go". Hints come one by one, and the solution can be opened after
two tries (or once all hints are used). Nothing is scored. At the end the child sees which tasks are
worth another look and can practise just those. Parents see each child's latest run at a glance
("How the kids did": right first time, the tasks that needed help with **what was typed**), and per
task how often it was right first time, the hints used and when the solution was needed. Use those
typed mistakes when writing the next set.
# Source groups in learning banks

Each `lab.sources` entry may specify `group: "notebook" | "textbook" | "review"`.
Missing classifications and questions citing multiple groups are held for review.
Notebook questions are active by default; textbook questions require a parent activation
for their `topic` (lesson ID) and learner. `lab.legacy` links existing ordinary `tasks`
(task ID → question ID), study `cards` (back text → question ID), and `sections`
(title → lesson ID), so older practice URLs obey the same policy. Unmapped legacy
practice items remain inactive. These are organization fields; keep all original IDs.
See [science source groups](science-source-groups.md) for behavior and parent controls.
