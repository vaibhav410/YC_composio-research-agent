import json

from storage import db


def export_dataset(conn):
    apps = []
    for row in db.all_apps(conn):
        app = dict(row)
        try:
            app["auth_methods"] = json.loads(app["auth_methods"]) if app["auth_methods"] else []
        except (json.JSONDecodeError, TypeError):
            app["auth_methods"] = [app["auth_methods"]]
        details = db.confidence_details(conn, app["id"])
        scores = [d["score"] for d in details.values()]
        app["confidence"] = round(sum(scores) / len(scores), 2) if scores else None
        app["confidence_reasons"] = {f: d["reasons"] for f, d in details.items()}
        app["evidence"] = {}
        app["evidence_types"] = {}
        for ev in db.evidence_for(conn, app["id"]):
            app["evidence"].setdefault(ev["field_name"], ev["source_url"])
            app["evidence_types"].setdefault(ev["field_name"], ev["source_type"])
        apps.append(app)
    return apps
