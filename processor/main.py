"""
A test app with two inputs (signals, events) and two outputs (summary,
copies), for trying workflows that link outputs to inputs.

Each input is looked for in its own folder first (INPUT_DIR/<name>/, where a
workflow puts it with placement: subfolder), then at the root of INPUT_DIR by
file extension. The app writes:

  OUTPUT_DIR/summary/report.json   what each input received, and where
  OUTPUT_DIR/copies/<input>/...    each input's files, copied on

and logs the same report, so a run's log shows the layout it was given.
"""
import json
import logging
import os
import shutil
import socket
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("test-ports-processor")
# The Lambda runtime configures the root logger before basicConfig can, at
# WARNING, so the report's INFO lines would be lost without this.
log.setLevel(logging.INFO)

# Each input: its file extensions, for finding it at the root of INPUT_DIR.
INPUTS = {
    "signals": (".csv",),
    "events": (".json",),
}
OUTPUTS = ("summary", "copies")


def tree(root):
    """Every file below root, relative to it, with its size."""
    files = []
    for dirpath, _, filenames in os.walk(root, followlinks=True):
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            files.append({"path": os.path.relpath(path, root), "bytes": os.path.getsize(path)})
    return sorted(files, key=lambda f: f["path"])


def llm_access():
    """
    Whether the step was given LLM access. This app doesn't declare
    runtime.llm, so on a node with opt-in LLM access all three are false.
    """
    sidecar = False
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            sidecar = True
    except OSError:
        pass
    return {
        "LLM_GOVERNOR_FUNCTION_NAME": bool(os.environ.get("LLM_GOVERNOR_FUNCTION_NAME")),
        "ANTHROPIC_BASE_URL": bool(os.environ.get("ANTHROPIC_BASE_URL")),
        "sidecarListening": sidecar,
    }


def find_input(input_dir, name, extensions):
    """
    Where an input's files are: its own folder when there is one, else the
    files at the root with its extensions. Returns (where, paths relative to
    INPUT_DIR).
    """
    folder = os.path.join(input_dir, name)
    if os.path.isdir(folder):
        return f"{name}/", [os.path.join(name, f["path"]) for f in tree(folder)]
    at_root = sorted(
        entry.name
        for entry in os.scandir(input_dir)
        if entry.is_file() and entry.name.lower().endswith(extensions)
    )
    return ("root" if at_root else "missing"), at_root


def main():
    input_dir = os.environ.get("INPUT_DIR")
    output_dir = os.environ.get("OUTPUT_DIR")
    fail_if_missing = os.environ.get("FAIL_IF_MISSING", "false").lower() == "true"
    if not input_dir or not output_dir:
        log.error("INPUT_DIR and OUTPUT_DIR must be set")
        return 2
    if not os.path.isdir(input_dir):
        log.error("INPUT_DIR %s is not a folder", input_dir)
        return 2

    report = {
        "app": "test-ports-processor",
        "at": datetime.now(timezone.utc).isoformat(),
        "inputDir": input_dir,
        "outputDir": output_dir,
        "runtime": "lambda" if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") else "container",
        "inputTree": tree(input_dir),
        "inputs": {},
        "llmAccess": llm_access(),
    }

    for name in OUTPUTS:
        os.makedirs(os.path.join(output_dir, name), exist_ok=True)

    missing = []
    for name, extensions in INPUTS.items():
        where, paths = find_input(input_dir, name, extensions)
        report["inputs"][name] = {"foundIn": where, "files": paths}
        if not paths:
            missing.append(name)
        for rel in paths:
            # Copied by its path inside the input, so a subfolder input's
            # layout is kept.
            inside = os.path.relpath(rel, name) if where == f"{name}/" else rel
            target = os.path.join(output_dir, "copies", name, inside)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(input_dir, rel), target)

    # Files that belong to no input: at the root, without an input's extension.
    claimed = {p for i in report["inputs"].values() for p in i["files"]}
    report["unclaimed"] = [f["path"] for f in report["inputTree"] if f["path"] not in claimed]
    report["missing"] = missing

    with open(os.path.join(output_dir, "summary", "report.json"), "w") as out:
        json.dump(report, out, indent=2)

    log.info("running as a %s; INPUT_DIR %s holds %d files", report["runtime"], input_dir, len(report["inputTree"]))
    for name, found in report["inputs"].items():
        log.info("input %s: %d files, found in %s", name, len(found["files"]), found["foundIn"])
        for path in found["files"]:
            log.info("  %s", path)
    if report["unclaimed"]:
        log.info("files no input claims: %s", ", ".join(report["unclaimed"]))
    log.info("LLM access (expected none, the app doesn't declare it): %s", report["llmAccess"])
    log.info("wrote %s", os.path.join(output_dir, "summary", "report.json"))

    if missing:
        if fail_if_missing:
            log.error("no files for: %s", ", ".join(missing))
            return 1
        log.warning("no files for: %s", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
