from common import load_config, open_db


def main():
    cfg = load_config()
    conn = open_db(cfg)

    from agents.verifier import answers_from_db, verify_app
    from storage import db
    from tools import llm

    import time

    llm.set_rpm(cfg["requests_per_minute"])
    llm.set_fallback(cfg.get("fallback_model"))
    started = time.time()
    todo = db.apps_with_status(conn, "RESEARCHED")
    print(f"verification: {len(todo)} apps to verify")

    for i, app in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {app['name']}", flush=True)
        try:
            answers = answers_from_db(conn, app)
            scores = verify_app(conn, app, answers, cfg)
            low = [f for f, s in scores.items() if s < cfg["confidence_threshold"]]
            if low:
                print(f"  low confidence: {', '.join(low)}")
        except Exception as e:
            print(f"  failed: {e}")

    durations = db.all_stats(conn).get("stage_durations", {})
    durations["verification"] = round(durations.get("verification", 0) + time.time() - started)
    db.save_stat(conn, "stage_durations", durations)

    verified = len(db.apps_with_status(conn, "VERIFIED"))
    unresolved = len(db.apps_with_status(conn, "UNRESOLVED"))
    print(f"done: {verified} verified, {unresolved} unresolved")


if __name__ == "__main__":
    main()
