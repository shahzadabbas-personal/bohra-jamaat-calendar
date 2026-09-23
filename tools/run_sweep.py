"""Runner for the scheduled sweep.

It writes everything to logs/sweep-<year>-<month>.log rather than to stdout,
because a scheduler gives it nowhere to print.

    pythonw.exe tools/run_sweep.py     Windows, via Task Scheduler
    python3 tools/run_sweep.py         macOS or Linux, via cron

On Windows, pythonw.exe allocates no console, so nothing flashes on screen. On
cron there is no console to begin with. Nothing here is platform specific.

Read the log after a scheduled run. If the Google authorisation has lapsed, this
exits non-zero with the reason rather than opening a browser nobody will see.
Re-approve by running the sweep once in a terminal.
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

        sys.path.insert(0, str(REPO / "core"))
        sys.argv = ["sweep.py", str(JAMAAT), "--apply"]
        try:
            import sweep

            sweep.UNATTENDED = True
            sweep.main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            log.write(f"exited {code}\n")
            return code
        except Exception as e:
            lapsed = "invalid_grant" in str(e) or "RefreshError" in type(e).__name__
            if lapsed:
                # pythonw.exe runs the schedule on Windows but has no console.
                exe = Path(sys.executable)
                if exe.name.lower() == "pythonw.exe":
                    exe = exe.with_name("python.exe")
                log.write(
                    "The Google authorisation has lapsed or been revoked.\n"
                    "Re-approve by running the sweep once in a terminal:\n"
                    f'  "{exe}" core/sweep.py jamaats/nj-burhani\n'
                    "A browser opens; approve it and this task resumes on its own.\n"
                )
            else:
                traceback.print_exc(file=log)
            return 1

        log.write("done\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
