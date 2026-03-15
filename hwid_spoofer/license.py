"""
License system - checks key and expiry.
"""
from datetime import datetime, timedelta

# Format: KEY -> expiry date (None = never)
LICENSES = {
    "test": datetime.now() + timedelta(days=30),
    "NEXUS-LIFETIME": None,
}

LICENSE_FILE = "license.dat"


def _save(key: str):
    with open(LICENSE_FILE, "w") as f:
        f.write(key.strip())


def _load() -> str | None:
    try:
        with open(LICENSE_FILE) as f:
            return f.read().strip()
    except:
        return None


def validate(key: str) -> tuple[bool, str]:
    """Returns (valid, message)."""
    key = key.strip()
    if key not in LICENSES:
        return False, "Invalid license key."
    expiry = LICENSES[key]
    if expiry is not None and datetime.now() > expiry:
        return False, f"License expired on {expiry.strftime('%Y-%m-%d')}."
    return True, _expiry_msg(key)


def _expiry_msg(key: str) -> str:
    expiry = LICENSES.get(key)
    if expiry is None:
        return "Lifetime license"
    days = (expiry - datetime.now()).days
    return f"Expires in {days} day{'s' if days != 1 else ''} ({expiry.strftime('%Y-%m-%d')})"


def check_saved() -> tuple[bool, str, str]:
    """Returns (valid, key, message). Loads saved key if exists."""
    key = _load()
    if not key:
        return False, "", ""
    ok, msg = validate(key)
    return ok, key, msg


def activate(key: str) -> tuple[bool, str]:
    ok, msg = validate(key)
    if ok:
        _save(key)
    return ok, msg
