"""Validated, source-referenced learning banks embedded in the normal topic registry."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]
Text = Annotated[str, Field(min_length=1, max_length=1600)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    id: Id
    file: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]+\.jpg$")]
    label: Text
    rotate: Literal[0, -90, 90] = 0
    width: int = Field(gt=0, le=10000)
    height: int = Field(gt=0, le=10000)
    review: str = ""


class Picture(Strict):
    source: Id
    # Crop in the oriented source's coordinates; pixels remain in private storage.
    box: tuple[float, float, float, float]
    alt: Text

    @model_validator(mode="after")
    def positive_box(self):
        x, y, w, h = self.box
        if min(x, y) < 0 or min(w, h) <= 0:
            raise ValueError("Invalid picture crop")
        return self


class Lesson(Strict):
    id: Id
    title: Text
    icon: Text
    summary: Text
    notes: list[Text] = Field(min_length=1, max_length=12)
    vocabulary: dict[str, Text]
    sources: list[Id] = Field(min_length=1)


class Question(Strict):
    id: Id
    topic: Id
    kind: Literal["oral", "choice", "boolean", "fill", "match", "sort", "sequence", "label"]
    prompt: Text
    answer: Text
    points: list[Text] = Field(min_length=1, max_length=6)
    hints: list[Text] = Field(min_length=1, max_length=3)
    sources: list[Id] = Field(min_length=1)
    difficulty: Literal[1, 2, 3] = 1
    options: list[Text] = Field(default_factory=list, max_length=12)
    correct: list[Text] = Field(default_factory=list, max_length=12)
    items: list[Text] = Field(default_factory=list, max_length=12)
    image: Picture | None = None
    followup: Text | None = None
    followup_answer: Text | None = None
    card: bool = False


class Lab(Strict):
    title: Text
    sources: list[Source] = Field(min_length=1, max_length=100)
    lessons: list[Lesson] = Field(min_length=1, max_length=30)
    questions: list[Question] = Field(min_length=1, max_length=500)
    review_notes: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        sources = {s.id: s for s in self.sources}
        lessons = {s.id for s in self.lessons}
        if len(sources) != len(self.sources) or len(lessons) != len(self.lessons):
            raise ValueError("Duplicate source or lesson id")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Duplicate question id")
        for lesson in self.lessons:
            if set(lesson.sources) - sources.keys():
                raise ValueError("Unknown lesson source")
            if not any(q.topic == lesson.id for q in self.questions):
                raise ValueError("Lesson has no exercises")
        for q in self.questions:
            if q.topic not in lessons or set(q.sources) - sources.keys():
                raise ValueError("Unknown question topic/source")
            if bool(q.followup) != bool(q.followup_answer):
                raise ValueError("Follow-up needs an answer")
            if q.kind != "oral":
                if not q.correct:
                    raise ValueError("Checked exercise needs a correct answer")
                if q.kind in ("choice", "boolean") and (len(q.correct) != 1 or q.correct[0] not in q.options):
                    raise ValueError("Invalid choice answer")
                if q.kind in ("match", "sort", "label") and (len(q.items) != len(q.correct) or set(q.correct) - set(q.options)):
                    raise ValueError("Each item needs a valid match")
                if q.kind == "sequence" and (sorted(q.items) != sorted(q.correct) or len(set(q.items)) != len(q.items)):
                    raise ValueError("Sequence must contain the same unique items")
            if q.image:
                s = sources.get(q.image.source)
                if not s or s.id not in q.sources:
                    raise ValueError("Unknown image source")
                w, h = (s.height, s.width) if s.rotate else (s.width, s.height)
                x, y, cw, ch = q.image.box
                if x + cw > w or y + ch > h:
                    raise ValueError("Crop outside source")
        return self
