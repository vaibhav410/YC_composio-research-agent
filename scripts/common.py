import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def load_config():
    import yaml

    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def open_db(cfg):
    from storage import db

    conn = db.connect(cfg["db_path"])
    db.load_apps_csv(conn, cfg["apps_csv"])
    return conn
