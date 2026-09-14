"""Dev tool: summarise pyright's output into something readable.

    python tools/lint_report.py [--all]
"""
import collections
import json
import pathlib
import subprocess
import sys

NOISE = {
    "reportUnknownVariableType",
    "reportUnknownArgumentType",
    "reportUnknownMemberType",
    "reportUnknownParameterType",
    "reportUnknownLambdaType",
    "reportMissingTypeArgument",
}


def main(argv: list[str]) -> int:
    raw = subprocess.run([sys.executable, "-m", "pyright", "--outputjson"],
                         capture_output=True, text=True).stdout
    diagnostics = json.loads(raw)["generalDiagnostics"]

    counts = collections.Counter(item["rule"] for item in diagnostics)
    print(f"total {len(diagnostics)}")
    for rule, count in counts.most_common():
        print(f"{count:5}  {rule}")

    show_noise = "--all" in argv
    interesting = [item for item in diagnostics
                   if show_noise or item["rule"] not in NOISE]
    if not interesting:
        return 0

    print(f"\n--- {len(interesting)} not from third-party unknown-types ---")
    for item in interesting:
        path = pathlib.Path(item["file"])
        line = item["range"]["start"]["line"] + 1
        print(f"{path.name}:{line}  [{item['rule']}]")
        print(f"    {item['message'].splitlines()[0][:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
