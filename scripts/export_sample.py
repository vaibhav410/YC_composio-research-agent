from common import load_config, open_db


def main():
    cfg = load_config()
    conn = open_db(cfg)

    from verification.sampler import export_sample

    count = export_sample(conn, "data/audit_sample.csv", cfg["sample_size"], cfg["sample_seed"])
    print(f"exported {count} apps to data/audit_sample.csv")
    print("fill human_value / is_correct (1 or 0) / notes, then run import_audit.py")


if __name__ == "__main__":
    main()
