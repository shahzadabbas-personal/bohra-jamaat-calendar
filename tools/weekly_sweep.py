"""Runner for the scheduled weekly sweep.

Task Scheduler launches this with pythonw.exe, which allocates no console, so
nothing flashes on screen. That also means there is nowhere for output to go, so
everything is redirected to logs/sweep-<year>-<month>.log.

    pythonw.exe tools/weekly_sweep.py

Read the log after a scheduled run. The Google authorisation expires seven days
after consent while the OAuth app is in Testing, and when it does this exits
non-zero with the reason and needs a browser to re-approve.
"""

from __future__ import annotations

import datetime
import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JAMAAT = REPO / "jamaats" / "nj-burhani"
LOGS = REPO / "logs"


def main() -> int:
    LOGS.mkdir(exist_ok=True)
    stamp = datetime.datetime.now()
    log_path = LOGS / f"sweep-{stamp:%Y-%m}.log"

    with log_path.open("a", encoding="utf-8") as log:
        sys.stdout = log
        sys.stderr = log
        log.write(f"\n===== {stamp:%Y-%m-%d %H:%M:%S} =====\n")

        if not os.environ.get("ANTHROPIC_API_KEY"):
            log.write(
                "ANTHROPIC_API_KEY is not set for the scheduled task. Set it with\n"
                "  setx ANTHROPIC_API_KEY \"sk-ant-...\"\n"
                "then let the task run again.\n"
            )
            return 2

        sys.path.insert(0, str(REPO / "core"))
        sys.argv = ["sweep.py", str(JAMAAT), "--apply"]
        try:
            import sweep

            sweep.main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            log.write(f"exited {code}\n")
            return code
        except Exception:
            traceback.print_exc(file=log)
            log.write(
                "\nIf this is a Google credentials error, the seven-day Testing\n"
                "authorisation has lapsed. Run the sweep once by hand to re-approve:\n"
                f"  python core/sweep.py {JAMAAT.name and 'jamaats/' + JAMAAT.name}\n"
            )
            return 1

        log.write("done\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
