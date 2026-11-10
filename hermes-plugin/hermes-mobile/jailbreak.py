"""Jailbreak templates for Hermux: sync them from togg53192/jailbreaks and apply one to a profile's SOUL.md.

Applying a template writes it to the profile's `SOUL.md` — Hermes's identity slot #1 — so every NEW chat in that
profile starts with it. Templates live under `<hermes home>/jailbreak/templates` (a shallow clone of the upstream
collection) and each is normalised to paste-ready text: an Ollama Modelfile's `SYSTEM \"\"\"...\"\"\"` body, or the
file as it stands when it is already a plain operating policy.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_URL = "https://github.com/togg53192-cmd/jailbreaks.git"
BACKUP_SUFFIX = ".pre-jb.bak"
CLONE_TIMEOUT = 60
MAX_TEMPLATE_CHARS = 200_000


def templates_dir() -> Path:
    """The template clone's directory (created on first use)."""
    from hermes_constants import get_hermes_home

    base = Path(get_hermes_home())
    root = base.parent.parent if base.parent.name == "profiles" else base
    d = root / "jailbreak" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _template_files() -> List[Path]:
    """Every template markdown in the clone (recursively — upstream keeps one folder per vendor), README excluded."""
    d = templates_dir()
    return sorted(p for p in d.rglob("*.md") if p.stem.lower() != "readme")


def _unique_names() -> Dict[str, Path]:
    """Stem -> path, suffixing the vendor folder when two folders share a stem so names stay unique."""
    seen: Dict[str, List[Path]] = {}
    for p in _template_files():
        seen.setdefault(p.stem.lower(), []).append(p)
    out: Dict[str, Path] = {}
    for stem_low, paths in seen.items():
        for p in paths:
            if len(paths) == 1:
                out[p.stem] = p
            else:
                out[f"{p.parent.name}/{p.stem}"] = p
    return out


def sync_templates() -> Dict[str, Any]:
    """Clone the collection, or fast-forward an existing clone. Never raises; returns `{ok, count|error}`."""
    d = templates_dir()
    try:
        if (d / ".git").is_dir():
            subprocess.run(["git", "-C", str(d), "pull", "--ff-only"], check=True,
                           timeout=CLONE_TIMEOUT, capture_output=True)
        elif any(d.rglob("*.md")):
            return {"ok": True, "count": len(_template_files())}  # no git here: keep what is there
        else:
            subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(d)], check=True,
                           timeout=CLONE_TIMEOUT, capture_output=True)
        return {"ok": True, "count": len(_template_files())}
    except FileNotFoundError:
        return {"ok": False, "error": "git is not installed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "the template download timed out"}
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        return {"ok": False, "error": detail[-1] if detail else "git failed"}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def _tag(text: str) -> str:
    """A short hint of which model a template targets, for the picker."""
    m = re.search(r"^FROM\s+(\S+)", text, re.M)  # an Ollama Modelfile names its base image
    if m:
        return f"ollama:{m.group(1)}"
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return (m.group(1).strip() if m else "custom")[:60]


def list_templates() -> List[Dict[str, Any]]:
    """Every template as `{name, filename, tag, size}`; syncs once when the folder has nothing yet."""
    d = templates_dir()
    if not any(d.rglob("*.md")):
        sync_templates()
    out: List[Dict[str, Any]] = []
    for name, p in sorted(_unique_names().items()):
        out.append({"name": name, "filename": p.name,
                    "tag": _tag(p.read_text(encoding="utf-8", errors="replace")),
                    "size": p.stat().st_size})
    return out


def _convert(text: str) -> str:
    """Paste-ready body: an Ollama Modelfile's `SYSTEM` block, else the file unchanged."""
    m = re.search(r'^SYSTEM\s+"""(.*?)"""\s*$', text, re.S | re.M)
    return (m.group(1).strip() if m else text.strip())


def _find(name: str) -> Optional[Path]:
    """One template by its unique name (stem, or `vendor/stem` when two folders share a stem), then by a case-insensitive substring."""
    d = templates_dir()
    want = (name or "").strip()
    if not want:
        return None
    if want in _unique_names():
        return _unique_names()[want]
    low = want.lower()
    hits = [p for p in _template_files() if low in p.stem.lower()]
    return hits[0] if hits else None


def apply_template(name: str, home: Path) -> Dict[str, Any]:
    """Write one template into *home*'s `SOUL.md`, keeping the previous file as `SOUL.md.pre-jb.bak`.

    `home` is the profile's directory (the route validates the profile name, so a bad `?profile=` cannot escape the
    Hermes home). The write is atomic: a half-written SOUL.md would truncate the bot's identity.
    """
    p = _find(name)
    if p is None:
        return {"ok": False, "error": f"Template '{name}' was not found — sync the list first"}

    payload = _convert(p.read_text(encoding="utf-8", errors="replace"))
    if not payload:
        return {"ok": False, "error": f"Template '{p.stem}' is empty"}
    if len(payload) > MAX_TEMPLATE_CHARS:
        return {"ok": False, "error": f"Template '{p.stem}' is too large to inject"}

    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    soul, bak = home / "SOUL.md", home / ("SOUL.md" + BACKUP_SUFFIX)
    try:
        # Keep the pre-jailbreak identity once; a second apply must not overwrite it with an injected prompt.
        if soul.is_file() and not bak.exists():
            shutil.copy2(soul, bak)
        tmp = soul.with_name("SOUL.md.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(soul)
    except OSError as e:
        return {"ok": False, "error": f"Could not write SOUL.md: {e}"}
    return {"ok": True, "template": p.stem, "chars": len(payload)}


def restore_soul(home: Path) -> Dict[str, Any]:
    """Put the profile's pre-jailbreak `SOUL.md` back (the backup is kept for another apply)."""
    home = Path(home)
    soul, bak = home / "SOUL.md", home / ("SOUL.md" + BACKUP_SUFFIX)
    if not bak.is_file():
        return {"ok": False, "error": "There is no backup for this bot"}
    try:
        shutil.copy2(bak, soul)
    except OSError as e:
        return {"ok": False, "error": f"Could not restore SOUL.md: {e}"}
    return {"ok": True}


def status(home: Path) -> Dict[str, Any]:
    """What the Jailbreak screen shows for a profile: whether a backup exists, plus the prompt's opening words."""
    home = Path(home)
    soul, bak = home / "SOUL.md", home / ("SOUL.md" + BACKUP_SUFFIX)
    out: Dict[str, Any] = {"backup": bak.is_file(), "chars": 0, "head": ""}
    if soul.is_file():
        text = soul.read_text(encoding="utf-8", errors="replace")
        out["chars"] = len(text)
        out["head"] = " ".join(text[:300].split())
    return out
