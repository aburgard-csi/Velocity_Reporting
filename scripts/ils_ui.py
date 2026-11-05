"""
ils_ui.py: the routes and field labels behind the ILS cards on a client's page in CSM Sheila.

James Gilmore, 2026-10-28: "a CSM can run either ILS analysis option from the Sheila webpage", on the client's page
beside the Executive Review, Transaction Intelligence and ARS Companion cards ("the option should be when i click a
client"), with an "ILS Review - Coming Soon" card beside them. The cards are drawn by sheila_hub_ils.py (the page
side, in the Hub layout since 2026-11-02); this module is the two route handlers and the labels both share.

Each card is the engine's two steps, in order: **Read the field summary** (step 1, computes nothing), then the codes
the CSM confirms and **Build** (step 2: the report or workbook, and the deck). Until the client's extract has landed
(Inputs/ILS PGL/<id>/ or Inputs/ILS Kickoff/<id>/) the card says where to put it. The codes a client's last run was
confirmed with are offered back with that run's date and file; they are the CSM's to keep or change and are never
applied until Build is pressed. The CSM confirms the codes, never the client (James Gilmore, 2026-10-28: "the user
will confirm the limits. the client wont confirm anything"). The runs and the files are in ils_runs.py.
"""
import ils_runs

LABELS = {
    "open_status": ("Open account status", "the Account Status value(s) meaning open"),
    "od_eligible": ("ILS-eligible OD status", "the OD Status value(s) eligible for ILS, or ALL for every one"),
    "rege_opt_in": ("Reg E opted in", "the Reg E value(s) meaning opted in"),
    "rege_opt_out": ("Reg E opted out", "the value(s) meaning opted out"),
    "personal_code": ("Personal", "the Business Flag value meaning personal"),
    "business_code": ("Business", "the Business Flag value meaning business"),
    "open_code": ("Open account status", "the Account Status value meaning open"),
    "eligible_stat_codes": ("OD-eligible Stat Code(s)", "the Stat Code value(s) eligible for OD"),
}


def get(handler, path, params):
    """GET /api/ils/client and /api/ils/job."""
    kind, cid = params.get("kind", ""), params.get("client", "")
    if not ils_runs.CID_RX.match(cid):
        return handler._send(400, {"error": "not a client number"})
    if path == "/api/ils/client":
        return handler._send(200, ils_runs.client_doc(cid))
    if path == "/api/ils/job":
        if kind not in ils_runs.KINDS:
            return handler._send(400, {"error": "not an ILS analysis"})
        return handler._send(200, ils_runs.job_doc(kind, cid) or {})
    return handler._send(404, {"error": "not found"})


def post(handler, path, body):
    """POST /api/ils/run, /api/ils/inputs and /api/ils/reveal."""
    if path == "/api/ils/inputs":
        code, doc = ils_runs.save_inputs(body)
        return handler._send(code, doc)
    if path == "/api/ils/run":
        code, doc = ils_runs.start(body)
        return handler._send(code, doc)
    if path == "/api/ils/reveal":
        code, doc = ils_runs.reveal(str(body.get("path", "")))
        return handler._send(code, doc)
    return handler._send(404, {"error": "not found"})
