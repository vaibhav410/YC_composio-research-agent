from common import load_config, open_db


def main():
    cfg = load_config()
    conn = open_db(cfg)

    import time

    from agents.researcher import research_app
    from storage import db
    from tools import llm

    llm.set_rpm(cfg["requests_per_minute"])
    llm.set_fallback(cfg.get("fallback_model"))
    started = time.time()
    pending = db.apps_needing_research(conn)
    print(f"research: {len(pending)} apps pending or retryable")

    for i, app in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {app['name']}", flush=True)
        try:
            research_app(conn, app, cfg)
        except Exception as e:
            if llm.request_too_large(e):
                reason = "CONTEXT_LIMIT"
            elif "tokens per day" in str(e) or "429" in str(e):
                reason = "PROVIDER_QUOTA"
            elif isinstance(e, ValueError):
                reason = "PARSER_FAILURE"
            else:
                reason = "RESEARCH_ERROR"
            print(f"  failed ({reason}): {e}")
            db.log_verification(conn, app["id"], "pipeline", "", "", "research", reason)
            db.save_record(conn, app["id"], {}, "UNRESOLVED", 1)

    durations = db.all_stats(conn).get("stage_durations", {})
    durations["research"] = round(durations.get("research", 0) + time.time() - started)
    db.save_stat(conn, "stage_durations", durations)

    done = len(db.apps_with_status(conn, "RESEARCHED"))
    unresolved = len(db.apps_with_status(conn, "UNRESOLVED"))
    print(f"done: {done} researched, {unresolved} unresolved")


if __name__ == "__main__":
    main()
