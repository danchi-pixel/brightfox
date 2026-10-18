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

### How a run works

A wrong answer shows "have another go". Hints come one by one, and the solution can be opened after
two tries (or once all hints are used). Nothing is scored. At the end the child sees which tasks are
worth another look and can practise just those. Parents see each child's latest run at a glance
("How the kids did": right first time, the tasks that needed help with **what was typed**), and per
task how often it was right first time, the hints used and when the solution was needed. Use those
typed mistakes when writing the next set.
