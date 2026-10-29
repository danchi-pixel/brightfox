"""Prepare the local household without deleting demo history or setting passwords.

Existing Alan/Erik IDs, settings and child-owned rows are never rewritten. Production never calls this.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .backup import create_backup
from .config import Settings, settings
from .models import Family, Learner, User

ROSTER = {"Alan": 4, "Erik": 6}


def prepare(db: Session, cfg: Settings) -> dict:
    if cfg.local_family != "danijel" or cfg.host not in ("127.0.0.1", "localhost", "::1") or cfg.behind_proxy or cfg.cookie_secure or cfg.static_dir:
        raise ValueError("Household setup is only available in the explicit local classroom mode.")
    families = list(db.scalars(select(Family)))
    family = next((f for f in families if f.slug == cfg.local_family), None)
    demo = next((f for f in families if f.slug == "test"), None)
    learners = list(db.scalars(select(Learner)))
    own = [l for l in learners if family and l.family_id == family.id]
    if any(l.name.casefold() in {n.casefold() for n in ROSTER} and (not family or l.family_id != family.id) for l in learners):
        raise ValueError("Alan or Erik already exists in another family. Keep their IDs and reconcile that family before setup.")
    if any(l.name not in ROSTER for l in own) or len({l.name for l in own}) != len(own):
        raise ValueError("The local family has additional or duplicate learners; refusing to overwrite profiles.")
    if demo and any(l.family_id == demo.id and l.name != "Tina" for l in learners):
        raise ValueError("The test family contains other learners; refusing automatic conversion.")
    parents = list(db.scalars(select(User).where(User.role == "admin", User.family_id == demo.id))) if demo else []
    needs_change = (family is None or family.status != "active" or len(own) != 2
                    or any(l.archived for l in own) or bool(parents)
                    or bool(demo and (demo.status != "suspended" or any(not l.archived for l in learners if l.family_id == demo.id))))
    if not needs_change:
        return {"changed": False, "family": family.slug, "learners": {l.name: l.id for l in own}}
    backup = create_backup("before-local-classroom", cfg)
    if family is None:
        family = Family(slug=cfg.local_family, name="Alan in Erik", timezone="Europe/Ljubljana", language="sl")
        db.add(family)
        db.flush()
    family.status = "active"
    for order, (name, grade) in enumerate(ROSTER.items()):
        existing = next((l for l in own if l.name == name), None)
        if existing:
            existing.archived = False
        else:
            new = Learner(family_id=family.id, name=name, grade=grade, sort_order=order)
            db.add(new)
            own.append(new)
    if demo:
        demo.status = "suspended"
        for l in learners:
            if l.family_id == demo.id:
                l.archived = True
        # Preserve the parent's existing sign-in; no credential is printed or changed.
        for parent in parents:
            parent.family_id = family.id
    db.commit()
    return {"changed": True, "backup": str(backup["path"]), "family": family.slug,
            "learners": {l.name: l.id for l in own}}


def main() -> None:
    import json
    from .db import SessionLocal
    from .migrate import run_migrations

    if not settings.local_family:
        raise SystemExit("Use the local launcher; production setup is not supported here.")
    run_migrations()
    with SessionLocal() as db:
        print(json.dumps(prepare(db, settings), ensure_ascii=False))


if __name__ == "__main__":
    main()
