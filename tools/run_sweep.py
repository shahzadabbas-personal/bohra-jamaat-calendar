"""Runner for the scheduled sweep.

It writes everything to logs/sweep-<year>-<month>.log rather than to stdout,
because a scheduler gives it nowhere to print.

    pythonw.exe tools/run_sweep.py     Windows, via Task Scheduler
    python3 tools/run_sweep.py         macOS or Linux, via cron

On Windows, pythonw.exe allocates no console, so nothing flashes on screen. On
cron there is no console to begin with. Nothing here is platform specific.

Read the log after a scheduled run. The Google authorisation expires seven days
after consent while the OAuth app is in Testing, and when it does this exits
non-zero with the reason and needs a browser to re-approve.

It runs daily rather than weekly for that reason. The seven days run from consent
rather than from last use, so a weekly run lands on the boundary and fails most
weeks, while a daily one turns each re-approval into a week of unattended
operation and puts announcements on the calendar within a day.
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
                "ANTHROPIC_API_KEY is not set for the scheduled run.\n"
                "A scheduler starts with almost no environment, so setting it\n"
                "in your shell is not enough:\n"
                "  Windows      setx ANTHROPIC_API_KEY \"sk-ant-...\"\n"
                "  cron         put ANTHROPIC_API_KEY=sk-ant-... in the crontab\n"
            )
            return 2

        # The OAuth app stays in Testing, so Google expires the authorisation
        # seven days after consent. Record its age here so a failure reads as
        # "the seven days ran out" rather than as something mysterious.
        token = JAMAAT / "token.json"
        if token.exists():
            minted = datetime.datetime.fromtimestamp(token.stat().st_mtime)
            age = (datetime.datetime.now() - minted).days
            log.write(f"authorisation is {age} day(s) old; Google expires it at 7\n")
            if age >= 6:
                log.write("expect to re-approve in a browser shortly\n")

        sys.path.insert(0, str(REPO / "core"))
        sys.argv = ["sweep.py", str(JAMAAT), "--apply"]
        try:
            import sweep

            sweep.main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            log.write(f"exited {code}\n")
            return code
        except Exception as e:
            lapsed = "invalid_grant" in str(e) or "RefreshError" in type(e).__name__
            if lapsed:
                log.write(
                    "The Google authorisation has lapsed. Google expires it seven\n"
                    "days after consent while the OAuth app is in Testing.\n"
                    "Re-approve by running the sweep once in a terminal:\n"
                    "  python core/sweep.py jamaats/nj-burhani\n"
                    "A browser opens; approve it and this task resumes on its own.\n"
                )
            else:
                traceback.print_exc(file=log)
            return 1

        log.write("done\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
