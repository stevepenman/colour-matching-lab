"""Conservative publication inventory and heuristic secret/address checks.

This is a repeatable guard, not a guarantee of confidentiality or publication rights.
It prints relative paths and finding categories without printing matched values.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ".gitignore", ".gitattributes", "README.md", "requirements.txt", "ui.py",
    "color_matching.py", "demo.py", "generate_demo_library.py",
    "examples/synthetic_colours.csv", "examples/synthetic_products.csv",
    "tests/test_matching.py", "tests/test_gui.py",
    "scripts/audit_publication.py", "scripts/render_demo.py",
    ".github/workflows/ci.yml", "docs/demo.png", "docs/ARCHITECTURE.md",
    "docs/SANITISATION.md", "docs/VERIFICATION.md", "docs/GITHUB_UPLOAD.md",
    "docs/PORTFOLIO.md",
}
LOCAL_DIRS = {".git", ".venv", "venv", "runtime", "__pycache__", ".pytest_cache"}
PATTERNS = {
    "private network address": r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider credential": r"\b(?:AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})\b",
    "credential assignment": r"(?i)\b(?:password|api_key|access_token|secret_key)\s*[:=]\s*['\"][^'\"]{4,}['\"]",
    "personal email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "absolute workstation path": r"(?i)[a-z]:[\\/](?:users|projects)[\\/]",
}


def main():
    files = {
        path.relative_to(ROOT).as_posix(): path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in LOCAL_DIRS for part in path.relative_to(ROOT).parts)
    }
    findings = []
    for missing in sorted(EXPECTED - files.keys()):
        findings.append((missing, "required publication file missing"))
    for name, path in sorted(files.items()):
        if name not in EXPECTED:
            findings.append((name, "unreviewed file outside publication inventory"))
        if path.is_symlink():
            findings.append((name, "symlink requires manual review"))
            continue
        if name == "docs/demo.png":
            if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                findings.append((name, "expected PNG screenshot"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            findings.append((name, "unexpected non-text file"))
            continue
        for category, pattern in PATTERNS.items():
            if re.search(pattern, content):
                findings.append((name, category))
    for name, category in findings:
        print(f"REVIEW {name}: {category}")
    print(f"Reviewed {len(files)} publication files; {len(findings)} findings.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
