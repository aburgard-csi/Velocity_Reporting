#!/usr/bin/env python3
"""
issue_reports.py — issues reported from CSM Sheila, queued on the share and filed on GitHub.

Aaron, 2026-10-02: "Add a button to report issues in Sheila that will send issues to
github. I also need a view into those issues so we can make sure we address them."

CSM Sheila runs from the share on each CSM's machine and the repo is PRIVATE, so filing
and reading issues both need GitHub credentials. A token in the released copy under
`Tools\\RPE` would be readable by everyone who can reach the share, so there is none:

    Sheila  ->  queue(...)            a JSON file in Build Artifacts/issue_reports/
    Aaron   ->  sync()                `gh issue create` for each queued report, then
                                      `gh issue list` written back as issues.json
    Sheila  ->  view()                queued reports + that cached issue list

So a CSM machine needs no credentials, no internet and no VPN to report something, the
button answers instantly, and the view still shows what happened to it. The cost is that
an issue reaches GitHub when the sync runs, not when the button is pressed — which is why
a queued report says so in the view rather than looking filed.

    python scripts/issue_reports.py sync          # file the queue, refresh the cache
    python scripts/issue_reports.py list          # what the view shows
"""
import argparse
import datetime as dt
import getpass
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))

import rpe_env as R

REPO = "aburgard-csi/Velocity_Reporting"
LABEL = "sheila"                      # so a report is distinguishable from hand-filed issues
GH_TIMEOUT = 60


def reports_dir(create=True):
    d = R.build_artifacts() / "issue_reports"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path():
    return reports_dir() / "issues.json"


def _slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n] or "report"


# ------------------------------------------------------------------ the queue
def queue(title, body="", client_id=None, reporter=None, page=None):
    """Write one report to the share. -> the saved record.

    Nothing here talks to GitHub: this runs on a CSM's machine, where there are no
    credentials and there may be no VPN.
    """
    title = (title or "").strip()
    if not title:
        raise ValueError("a report needs a title")
    now = dt.datetime.now()
    rec = {
        "id": f"{now:%Y%m%dT%H%M%S}-{_slug(title, 24)}",
        "created": now.isoformat(timespec="seconds"),
        "reporter": reporter or getpass.getuser(),
        "client_id": (client_id or "").strip() or None,
        "page": page or None,
        "title": title,
        "body": (body or "").strip(),
        "status": "queued",
        "issue": None,
    }
    path = reports_dir() / f"{rec['id']}.json"
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def load_reports():
    """Every report on the share, newest first."""
    out = []
    for p in sorted(reports_dir().glob("*.json")):
        if p.name == "issues.json":
            continue
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:                  # a damaged report is shown, never dropped
            out.append({"id": p.stem, "title": f"(unreadable report: {type(e).__name__})",
                        "status": "damaged", "created": "", "reporter": "", "issue": None})
    return sorted(out, key=lambda r: r.get("created") or "", reverse=True)


# ------------------------------------------------------------------ GitHub, from here only
def _gh(args, check=True):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=GH_TIMEOUT)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "gh failed").strip().splitlines()[-1])
    return r.stdout


def _body_for(rec):
    """The issue body: the report, and where it came from."""
    lines = [rec.get("body") or "_(no description)_", "", "---"]
    lines.append(f"Reported in CSM Sheila by **{rec.get('reporter') or 'unknown'}** "
                 f"on {rec.get('created') or 'an unknown date'}.")
    if rec.get("client_id"):
        lines.append(f"Client: **{rec['client_id']}**")
    if rec.get("page"):
        lines.append(f"Page: {rec['page']}")
    lines.append(f"Report id: `{rec.get('id')}`")
    return "\n".join(lines)


def ensure_label(repo=REPO):
    """Create the `sheila` label if the repo has not got one. -> True when it is usable.

    A fresh repo has no such label and `gh issue create --label` fails outright, which left
    the first report queued with "'sheila' not found". The label is a convenience for
    filtering, so a repo that refuses to create it files issues without one rather than
    refusing to file at all.
    """
    try:
        have = json.loads(_gh(["label", "list", "--repo", repo, "--json", "name"]) or "[]")
        if any((l.get("name") or "").lower() == LABEL for l in have):
            return True
        _gh(["label", "create", LABEL, "--repo", repo, "--color", "F47A29",
             "--description", "Reported from CSM Sheila"])
        return True
    except Exception as e:
        print(f"  !! label {LABEL!r} unavailable ({str(e)[:90]}) — filing without it")
        return False


def sync(repo=REPO, apply=True):
    """File every queued report, then cache the issue list for Sheila's view.

    Idempotent: a report is filed once and its record then carries the issue number, so a
    re-run files nothing twice. A report that fails to file STAYS queued and is reported.
    """
    labelled = ensure_label(repo) if apply else True
    filed, failed = [], []
    for rec in load_reports():
        if rec.get("status") != "queued":
            continue
        if not apply:
            filed.append((rec["id"], None))
            continue
        try:
            cmd = ["issue", "create", "--repo", repo, "--title", rec["title"],
                   "--body", _body_for(rec)]
            if labelled:
                cmd += ["--label", LABEL]
            out = _gh(cmd)
            m = re.search(r"/issues/(\d+)", out or "")
            rec["issue"] = {"number": int(m.group(1)) if m else None,
                            "url": (out or "").strip().splitlines()[-1] if out else None}
            rec["status"] = "filed"
            rec["filed_at"] = dt.datetime.now().isoformat(timespec="seconds")
            (reports_dir() / f"{rec['id']}.json").write_text(
                json.dumps(rec, indent=2), encoding="utf-8")
            filed.append((rec["id"], rec["issue"]["number"]))
        except Exception as e:
            failed.append((rec["id"], str(e)[:160]))

    issues, err = [], None
    if apply:
        try:
            cmd = ["issue", "list", "--repo", repo, "--state", "all", "--limit", "200",
                   "--json", "number,title,state,url,createdAt,updatedAt,labels"]
            if labelled:
                cmd += ["--label", LABEL]
            issues = json.loads(_gh(cmd) or "[]")
        except Exception as e:
            err = str(e)[:200]
    if apply and err is None:
        cache_path().write_text(json.dumps(
            {"fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
             "repo": repo, "issues": issues}, indent=2), encoding="utf-8")
    return {"filed": filed, "failed": failed, "issues": len(issues), "list_error": err}


def cached_issues():
    """The issue list the last sync wrote, or an empty one. Never calls gh."""
    p = cache_path()
    if not p.exists():
        return {"fetched_at": None, "issues": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"fetched_at": None, "issues": []}


# ------------------------------------------------------------------ what Sheila shows
def view():
    """Reported issues for the view: filed ones with their GitHub state, then the queue.

    Reads only the share. A queued report is shown AS queued — it has not reached GitHub
    yet, and saying otherwise would have people waiting on an issue nobody can see.
    """
    cache = cached_issues()
    by_number = {i.get("number"): i for i in cache.get("issues") or []}
    rows = []
    for rec in load_reports():
        num = (rec.get("issue") or {}).get("number")
        gh = by_number.pop(num, None) if num else None
        rows.append({
            "id": rec.get("id"), "title": rec.get("title"),
            "reporter": rec.get("reporter"), "created": rec.get("created"),
            "client_id": rec.get("client_id"), "body": rec.get("body"),
            "number": num, "url": (rec.get("issue") or {}).get("url") or (gh or {}).get("url"),
            "state": (gh or {}).get("state", "").lower() or
                     ("filed" if rec.get("status") == "filed" else rec.get("status")),
        })
    # issues filed on GitHub under the label that no report on this share knows about —
    # someone filed by hand, or from another machine. Shown, never hidden.
    for num, gh in by_number.items():
        rows.append({"id": None, "title": gh.get("title"), "reporter": None,
                     "created": gh.get("createdAt"), "client_id": None, "body": None,
                     "number": num, "url": gh.get("url"),
                     "state": (gh.get("state") or "").lower()})
    rows.sort(key=lambda r: (r.get("state") == "closed", -(r.get("number") or 0),
                             r.get("created") or ""), reverse=False)
    return {"fetched_at": cache.get("fetched_at"), "rows": rows,
            "queued": sum(1 for r in rows if r["state"] == "queued")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync").add_argument("--dry-run", action="store_true")
    sub.add_parser("list")
    rp = sub.add_parser("report")
    rp.add_argument("title")
    rp.add_argument("--body", default="")
    rp.add_argument("--client")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        rec = queue(a.title, a.body, client_id=a.client)
        print(f"queued {rec['id']} — run `issue_reports.py sync` to file it")
        return 0
    if a.cmd == "sync":
        res = sync(apply=not a.dry_run)
        for rid, num in res["filed"]:
            print(f"  filed  {rid} -> #{num}" if num else f"  would file  {rid}")
        for rid, why in res["failed"]:
            print(f"  !! NOT filed {rid}: {why}")
        if res["list_error"]:
            print(f"  !! issue list not refreshed: {res['list_error']}")
        else:
            print(f"  {res['issues']} issue(s) cached for Sheila's view")
        return 1 if res["failed"] else 0
    v = view()
    print(f"as of {v['fetched_at'] or 'never synced'} — {len(v['rows'])} reported, "
          f"{v['queued']} not yet filed")
    for r in v["rows"]:
        num = f"#{r['number']}" if r.get("number") else "--"
        print(f"  {num:>5} {r['state']:<8} {(r['title'] or '')[:60]:62} "
              f"{r.get('reporter') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
