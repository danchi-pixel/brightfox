"""Administration commands (run on the server inside the container, or locally against a scratch folder).

    python -m app.manage create-family <slug> --name "Družina Novak" [--timezone Europe/Ljubljana]
    python -m app.manage list-families
    python -m app.manage suspend-family <slug> | activate-family <slug>
    python -m app.manage add-learner <slug> <name> [--grade 6] [--avatar ⚽]
    python -m app.manage set-password <username> --family <slug>                      # a parent (admin)
    python -m app.manage set-password <username> --family <slug> --learner Erik        # a kid's account
    python -m app.manage set-password <username> --stdin ...                           # password from stdin
    python -m app.manage list-users [--family <slug>]
    python -m app.manage delete-user <username>
    python -m app.manage backup [--label daily] [--keep 14]                           # database + files → data/backups

Families are only created here (there is no public sign-up yet). ``set-password`` creates the account if
it doesn't exist (``--family`` needed) or changes its password and signs it out everywhere.

Passwords are never accepted as command-line arguments (they would end up in shell history and process
lists).
"""
from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select


def _db():
    from .db import SessionLocal
    from .migrate import run_migrations

    run_migrations()
    return SessionLocal()


def _family(db, slug: str):
    from .models import Family

    fam = db.scalars(select(Family).where(Family.slug == slug.strip().lower())).first()
    if fam is None:
        raise ValueError(f"No family '{slug}'.")
    return fam


def _learner(db, family_id: int, ref: str):
    """A learner of the family by id or (case-insensitive) name."""
    from .models import Learner

    q = select(Learner).where(Learner.family_id == family_id)
    if ref.isdigit():
        found = db.scalars(q.where(Learner.id == int(ref))).first()
        if found:
            return found
    matches = list(db.scalars(q.where(func.lower(Learner.name) == ref.strip().lower())))
    if len(matches) != 1:
        raise ValueError(f"No single learner called '{ref}' in this family.")
    return matches[0]


def _read_password(use_stdin: bool) -> str | None:
    if use_stdin:
        # Windows PowerShell may prefix piped text with a UTF-8 byte-order mark: never part of a password.
        return sys.stdin.readline().lstrip("﻿").rstrip("\r\n")
    password = getpass.getpass("New password: ")
    if getpass.getpass("Repeat password: ") != password:
        print("The passwords don't match.", file=sys.stderr)
        return None
    return password


def cmd_create_family(args: argparse.Namespace) -> int:
    from .content.checker import SLUG_RE
    from .models import Family
    from .timeutil import family_tz

    slug = args.slug.strip().lower()
    if not SLUG_RE.fullmatch(slug):
        print("Use a-z, 0-9 and - for the slug (it also names the family's content folder).", file=sys.stderr)
        return 1
    if family_tz(args.timezone).key != args.timezone:
        print("Unknown time zone.", file=sys.stderr)
        return 1
    with _db() as db:
        if db.scalars(select(Family).where(Family.slug == slug)).first() is not None:
            print(f"The family '{slug}' already exists.", file=sys.stderr)
            return 1
        db.add(Family(slug=slug, name=args.name.strip(), timezone=args.timezone, language=args.language))
        db.commit()
    print(f"Created family '{slug}'. Next: add-learner, then set-password for a parent account.")
    return 0


def cmd_list_families(_args: argparse.Namespace) -> int:
    from .models import Family, Learner, User

    with _db() as db:
        fams = list(db.scalars(select(Family).order_by(Family.slug)))
        if not fams:
            print("No families yet. Create one with: python -m app.manage create-family <slug> --name <name>")
        for f in fams:
            learners = db.scalar(select(func.count(Learner.id)).where(Learner.family_id == f.id))
            users = db.scalar(select(func.count(User.id)).where(User.family_id == f.id))
            print(f"{f.slug}  ({f.name}; {f.status}; {learners} learners, {users} accounts; {f.timezone})")
    return 0


def _set_status(slug: str, status: str) -> int:
    from . import auth

    with _db() as db:
        try:
            fam = _family(db, slug)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        fam.status = status
        db.commit()
    auth._cache.clear()
    print(f"Family '{slug}' is now {status}.")
    return 0


def cmd_suspend_family(args: argparse.Namespace) -> int:
    return _set_status(args.slug, "suspended")


def cmd_activate_family(args: argparse.Namespace) -> int:
    return _set_status(args.slug, "active")


def cmd_add_learner(args: argparse.Namespace) -> int:
    from .models import Learner

    with _db() as db:
        try:
            fam = _family(db, args.slug)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        learner = Learner(family_id=fam.id, name=args.name.strip(), grade=args.grade, avatar=args.avatar)
        db.add(learner)
        db.commit()
        print(f"Added learner {learner.name} (id {learner.id}) to '{fam.slug}'.")
    return 0


def cmd_set_password(args: argparse.Namespace) -> int:
    from . import auth

    password = _read_password(args.stdin)
    if password is None:
        return 1
    problem = auth.check_password_strength(password)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    with _db() as db:
        try:
            user = auth.find_user(db, args.username)
            if user is None:
                if not args.family:
                    raise ValueError("A new account needs --family <slug>.")
                fam = _family(db, args.family)
                learner = _learner(db, fam.id, args.learner) if args.learner else None
                user = auth.create_account(db, fam.id, args.username, password,
                                           role="learner" if learner else "admin",
                                           learner_id=learner.id if learner else None)
                print(f"Created '{user.username}' ({user.role}) in '{fam.slug}'.")
            else:
                if args.family and _family(db, args.family).id != user.family_id:
                    raise ValueError("That username belongs to another family.")
                auth.set_password(db, user, password)
                print(f"Password changed for '{user.username}'. All of this account's sign-ins were ended.")
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    return 0


def cmd_list_users(args: argparse.Namespace) -> int:
    from .models import AuthSession, Family, Learner, User

    with _db() as db:
        q = select(User, Family.slug).join(Family, Family.id == User.family_id).order_by(Family.slug, User.username)
        if args.family:
            q = q.where(Family.slug == args.family.strip().lower())
        rows = db.execute(q).all()
        if not rows:
            print("No accounts.")
        for u, slug in rows:
            sessions = db.scalar(select(func.count(AuthSession.id)).where(AuthSession.user_id == u.id))
            learner = db.get(Learner, u.learner_id) if u.learner_id else None
            linked = f", learner {learner.name}" if learner else ""
            print(f"{slug}: {u.username}  ({u.role}{linked}; created {u.created_at:%Y-%m-%d}, active sign-ins: {sessions})")
    return 0


def cmd_delete_user(args: argparse.Namespace) -> int:
    from . import auth

    with _db() as db:
        user = auth.find_user(db, args.username)
        if user is None:
            print("No such account.", file=sys.stderr)
            return 1
        db.delete(user)
        db.commit()
    auth._cache.clear()
    print(f"Deleted account '{args.username}'.")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from . import backup

    try:
        made = backup.create_backup(args.label)
        removed = backup.prune(args.label, args.keep) if args.keep is not None else []
    except backup.BackupError as exc:
        print(exc, file=sys.stderr)
        return 1
    m = made["manifest"]
    print(f"{made['path']}  ({made['size_bytes'] / 1e6:.1f} MB, {m['files']} files)")
    if removed:
        print(f"Removed {len(removed)} older '{args.label}' backup(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-family", help="create a family (a customer)")
    p.add_argument("slug")
    p.add_argument("--name", required=True)
    p.add_argument("--timezone", default="Europe/Ljubljana")
    p.add_argument("--language", choices=("sl", "en"), default="sl")
    p.set_defaults(func=cmd_create_family)
    p = sub.add_parser("list-families", help="list families")
    p.set_defaults(func=cmd_list_families)
    p = sub.add_parser("suspend-family", help="sign a family out and refuse its sign-ins")
    p.add_argument("slug")
    p.set_defaults(func=cmd_suspend_family)
    p = sub.add_parser("activate-family", help="allow a suspended family again")
    p.add_argument("slug")
    p.set_defaults(func=cmd_activate_family)
    p = sub.add_parser("add-learner", help="add a learner (a kid) to a family")
    p.add_argument("slug")
    p.add_argument("name")
    p.add_argument("--grade", type=int, default=None, choices=range(1, 14), metavar="1-13")
    p.add_argument("--avatar", default="🦊")
    p.set_defaults(func=cmd_add_learner)
    p = sub.add_parser("set-password", help="create an account or change its password")
    p.add_argument("username")
    p.add_argument("--stdin", action="store_true", help="read the password from standard input")
    p.add_argument("--family", default=None, help="family slug (needed for a new account)")
    p.add_argument("--learner", default=None, help="learner (name or id): makes a kid's account")
    p.set_defaults(func=cmd_set_password)
    p = sub.add_parser("list-users", help="list sign-in accounts")
    p.add_argument("--family", default=None)
    p.set_defaults(func=cmd_list_users)
    p = sub.add_parser("delete-user", help="delete a sign-in account")
    p.add_argument("username")
    p.set_defaults(func=cmd_delete_user)
    p = sub.add_parser("backup", help="back up the database and the stored files into data/backups")
    p.add_argument("--label", default="manual", help="a-z, 0-9 and - (daily, weekly, preupdate, ...)")
    p.add_argument("--keep", type=int, default=None, help="then keep only the newest N backups with this label")
    p.set_defaults(func=cmd_backup)
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
