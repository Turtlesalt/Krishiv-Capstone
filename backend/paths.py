import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

# Every piece of local persistence (groups, sessions, favorites, the OAuth
# token, the geocode cache) lives under this one directory. On a host with
# an ephemeral filesystem (e.g. Railway without a mounted Volume), writes
# here vanish on every redeploy - set DATA_DIR to a mounted volume's path
# to make it durable instead.
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
