from common import load_config, open_db


def main():
    cfg = load_config()
    conn = open_db(cfg)

    from verification.accuracy import compute_accuracy
    from verification.sampler import import_audit

    count = import_audit(conn, "data/audit_sample.csv")
    result = compute_accuracy(conn)
    print(f"imported {count} audited fields")
    if result["available"]:
        print(f"first-pass accuracy: {result['pass1_accuracy']:.1%}")
        print(f"final accuracy:      {result['final_accuracy']:.1%}")


if __name__ == "__main__":
    main()
