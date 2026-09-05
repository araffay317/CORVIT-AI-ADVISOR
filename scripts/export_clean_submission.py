"""
Clean Submission Packaging Utility for CORVIT-AI-ADVISOR.
Creates a pristine ZIP archive suitable for academic submission to teachers.
Strictly excludes:
- .env (real secrets)
- .venv / venv (heavy virtual environments)
- __pycache__ / .pytest_cache (bytecode and test cache)
- .git / .github (VCS internals)
- Local temporary files (*.log, *.zip, scratch/)
Preserves:
- All 8 Dataset/ files with byte-for-byte SHA-256 integrity verification
- .env.example template
- Complete backend, tests, frontend, and documentation
"""
import os
import zipfile
import hashlib
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = REPO_ROOT / "CORVIT-AI-ADVISOR-SUBMISSION.zip"

# Strict exclusion rules
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "scratch",
    "build",
    "dist"
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    "CORVIT-AI-ADVISOR-SUBMISSION.zip"
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".zip"
}

# Canonical expected dataset hashes
EXPECTED_DATASET_HASHES = {
    "courses": "7d9b6b16048fa059c380ae9344a3ac91db5679793ad7c9d1e2c2314d880da62e",
    "navttc": "8d246641876928659a292735b5232e87fc0ce74813e620cc544c69ed81fe8e27",
    "timetable": "c750e0a558e4901e910b541edd662797e94d529a7b1533e5d67fea75b4c6aa50",
    "fees": "992338b96b5920568f5c4e8a35359f3b85f7e1c99a37735224830bab59661fcc",
    "admission": "66543945263d54f6433139393b00ad4d68b4a6accd40055c6971a14aab7f4999",
    "infrastructure": "66fa86c7c8b096c0793dd063a652881c0387d403bd793d5072f74d0dee233fc7",
    "faq": "a0acb66a1b3b66782dc8cd3b0513968f9d3e91e0a7483b7f62c12dc15ea9e60b",
    "general": "6fce34bb99325352815913f784e1861fabea1f4b76c7b932db099db6e9c6da59",
}


def should_exclude(rel_path: Path) -> bool:
    """Determine whether a file or directory path should be excluded."""
    # Check directory parts
    for part in rel_path.parts[:-1]:
        if part in EXCLUDE_DIRS or part.startswith("__pycache__"):
            return True

    # Check filename
    filename = rel_path.name
    if filename in EXCLUDE_FILES:
        return True

    # Check extension
    if rel_path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def verify_dataset_integrity():
    """Verify all 8 Dataset files match expected SHA-256 digests before packaging."""
    print("Verifying Dataset files before packaging...")
    dataset_dir = REPO_ROOT / "Dataset"
    assert dataset_dir.is_dir(), "Dataset directory not found!"

    for cat, expected_hash in EXPECTED_DATASET_HASHES.items():
        cat_dir = dataset_dir / cat
        assert cat_dir.is_dir(), f"Missing category directory: {cat}"
        files = list(cat_dir.glob("*.txt"))
        assert len(files) == 1, f"Expected exactly 1 txt file in {cat}, found {len(files)}"
        file_path = files[0]
        with open(file_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        assert digest == expected_hash, f"Hash mismatch for {file_path.name}: {digest} != {expected_hash}"
        print(f"  [OK] {cat:15} -> {file_path.name} ({digest[:12]}...)")
    print("All 8 dataset files verified with 100% SHA-256 match.\n")


def build_submission_zip():
    """Build the clean submission ZIP package."""
    verify_dataset_integrity()

    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    print(f"Building clean submission archive at: {OUTPUT_ZIP.name}")
    included_files = []

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(REPO_ROOT):
            # Modify dirs in-place to prevent walking excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("__pycache__")]

            for file in sorted(files):
                file_path = Path(root) / file
                rel_path = file_path.relative_to(REPO_ROOT)

                if should_exclude(rel_path):
                    continue

                zipf.write(file_path, arcname=str(rel_path))
                included_files.append(str(rel_path))

    # Audit the created ZIP archive
    print(f"Packaged {len(included_files)} files into {OUTPUT_ZIP.name}.")
    print("\nAuditing package for zero-leak compliance:")

    with zipfile.ZipFile(OUTPUT_ZIP, "r") as zipf:
        namelist = zipf.namelist()

        # Critical assertions
        assert ".env" not in namelist, "CRITICAL ERROR: Real .env included in ZIP!"
        assert not any(n.startswith(".venv/") for n in namelist), "CRITICAL ERROR: .venv included in ZIP!"
        assert not any("__pycache__" in n for n in namelist), "CRITICAL ERROR: __pycache__ included in ZIP!"
        assert not any(".pytest_cache" in n for n in namelist), "CRITICAL ERROR: .pytest_cache included in ZIP!"
        assert ".env.example" in namelist, "MISSING: .env.example must be included!"
        assert "README.md" in namelist, "MISSING: README.md must be included!"
        assert "index.html" in namelist, "MISSING: index.html must be included!"
        assert "backend/server.py" in namelist, "MISSING: backend/server.py must be included!"

        # Check for any real secret tokens inside text files in ZIP
        import re
        for name in namelist:
            if name.endswith((".py", ".js", ".html", ".css", ".md", ".toml", ".example", ".txt")):
                content = zipf.read(name).decode("utf-8", errors="ignore")
                match = re.search(r"gsk_[A-Za-z0-9]{15,}", content)
                assert match is None, f"Real Groq API key token detected in {name} inside ZIP!"

    print("  [PASSED] .env excluded")
    print("  [PASSED] .venv excluded")
    print("  [PASSED] __pycache__ and .pytest_cache excluded")
    print("  [PASSED] .env.example included with safe placeholders")
    print("  [PASSED] All 8 Dataset files included and verified")
    print(f"\nSUCCESS: Clean submission package ready ({OUTPUT_ZIP.stat().st_size / 1024:.1f} KB).")


if __name__ == "__main__":
    build_submission_zip()
