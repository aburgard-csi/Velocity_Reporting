"""Who is asking: the Windows user, read as the CSM their name is in the Client CSM List.

Windows names here are first.last (james.gilmore), and the list names CSMs "James Gilmore". When that
does not match, CSM Contacts.csv's email (First.Last@csiweb.com) is tried. Nobody types who they are.
"""
import csv
import getpass
import os

import rpe_env as R


def _from_user(user):
    parts = [p for p in user.replace("_", ".").split(".") if p]
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts)


def csm_names():
    """Every CSM the Client CSM List names."""
    p = R.csm_list_file()
    if not p or not p.is_file():
        return set()
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return {(r.get("csm") or "").strip() for r in csv.DictReader(fh)} - {"", "Unassigned"}


def _contacts():
    p = R.data_root() / "CSM Contacts.csv"
    if not p.is_file():
        return {}
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return {(r.get("email") or "").split("@")[0].strip().lower(): (r.get("csm") or "").strip()
                for r in csv.DictReader(fh) if "@" in (r.get("email") or "")}


def current_csm(user=None, names=None):
    """The CSM this Windows user is, or None when the list does not name them."""
    user = (user or os.environ.get("USERNAME") or getpass.getuser() or "").strip()
    names = csm_names() if names is None else names
    guess = _from_user(user)
    if guess in names:
        return guess
    hit = _contacts().get(user.lower())
    return hit if hit in names else None


def resolve_csm(csm, names=None):
    """'me' (or nothing) is the caller; otherwise a first name, last name or full name, any case."""
    names = csm_names() if names is None else names
    if not csm or csm.strip().lower() in ("me", "mine", "my"):
        return current_csm(names=names)
    want = csm.strip().lower()
    exact = [n for n in names if n.lower() == want]
    if exact:
        return exact[0]
    part = [n for n in names if want in n.lower().split()]
    return part[0] if len(part) == 1 else None
