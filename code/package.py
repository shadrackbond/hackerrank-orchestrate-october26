"""Build a source-only submission archive from an explicit allowlist."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "code.zip")
    args = parser.parse_args()
    files = [root / name for name in ("README.md", "requirements.txt", "agent_trace_instructions.md",
        "evaluation/evaluation_report.md", "evaluation/usage_report.md")]
    files += sorted((root / "code").rglob("*.py"))
    files += sorted((root / "tests").glob("test_*.py"))
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Missing or unsafe package input: " + str(path))
    # Replacement is explicit only for this generated archive; source work is preserved.
    with ZipFile(args.output, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root))
    with ZipFile(args.output) as archive:
        if archive.testzip(): raise ValueError("Archive integrity failure")
        print(f"{args.output}: {len(archive.namelist())} files, {args.output.stat().st_size} bytes")


if __name__ == "__main__": main()
