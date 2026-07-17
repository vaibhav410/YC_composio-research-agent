import run_report
import run_research
import run_verification


def main():
    run_research.main()
    run_verification.main()
    run_report.main()
    print("pipeline complete — open output/index.html")
    print("optional: scripts/export_sample.py -> hand audit -> scripts/import_audit.py -> scripts/run_report.py")


if __name__ == "__main__":
    main()
