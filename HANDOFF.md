# HANDOFF

Updated 5 Oct 2026 (Claude Code session with Shahzad).

Context for picking this project up in Cowork, Claude Code or Codex. Decisions
and open questions, not a transcript. Pruned items live in `HANDOFF-archive.md`.

## What this is

A shareable Google Calendar of Dawoodi Bohra miqaat dates for Anjuman-e-Burhani
NJ, built so any jamaat can fork it and swap in their own schedule.

Scaffold and sweep are both done. `core/sweep.py` runs daily against real
announcements and writes to the live calendar.

The repo went public on 23 Sep 2026 so other jamaats can fork it. Anything
committed from here on is visible to anyone.

## Current task

Catalog cleanup, 5 Oct 2026. Nine missing miqaats were added and four existing
dates corrected, each checked against mumineen.org and ABNJ's own emails.
Shahzad imported the 15 changed events into the live calendar. Ashara waaz and
majlis times were dropped, Eid ul Adha given a morning placeholder, and the
GitHub Actions schedule stopped. Committed locally, not pushed.

## Decisions

**5 Oct 2026 (Shahzad)**

- **mumineen.org is the authority for the canonical Hijri day** of a miqaat.
  ABNJ's emails decide which evening the jamaat holds it, which is what
  `observed_offset` captures. mumineen.org lists many urus with no programme, so
  check only miqaats the jamaat holds in person. Its calendar data comes from
  `POST https://mumineen.org/api/calendar/monthly-miqaats` with
  `{"month": m, "year": hijri_year}`; a `Fadhil Raat` entry is listed on the
  evening it is held, every other type on its daylight date.
- **No set times for the Ashara waaz or raat majlis.** Removed from ABNJ's
  `observes` (still in `catalog.yaml` for other jamaats). The all-day banner and
  Ashura stay. Reason: ABNJ never announces them by mail, 1448H was a relay
  centre, and a guessed time drifts as Ashara moves eleven days earlier a year.
- **Eid times stay as placeholders.** Shahzad says the jamaat announces Eid
  timings a few days ahead, so the sweep corrects them. A sunrise-based
  calculation was proposed and skipped as unnecessary. Eid ul Adha got a
  04:00–08:00 placeholder (it fell back to the 19:00 default before).
- **Project rules live in `CLAUDE.md`**: the mumineen.org rule and the
  import-only-affected-events rule below.
- **No Ashara ohbat Fridays.** The `seasonal` block in config stays ungenerated
  on purpose.
- **GitHub Actions stays off.** Disabled on GitHub (`gh workflow disable`) and
  the weekly cron removed from `.github/workflows/sweep.yml`, so it runs only
  by hand. The real sweep is the local scheduled task.
- **Change the live calendar by importing only the affected events**, never the
  full `nj-burhani.ics`. Re-import matches by UID, so a full import resets every
  time the sweep has already promoted back to its generated default.

**Earlier decisions, still in force**

- **Two layers, not one.** Miqaat dates are computable; local program times are
  not. Generated dates go in as all-day or default-time events; the
  announcement sweep promotes them to real times. Austin's jamaat independently
  arrived at the same split.
- **Native shared Google Calendar, edited in place.** ICS serves the one-time
  bulk import; after that the calendar is the live artifact. Google serves the
  calendar's own outbound `.ics` with caching disabled, which is how iPhones
  subscribe. See the sharing section in the README.
- **`observed_offset` lives in jamaat config, not in the converter.** An evening
  majlis for Hijri day N is usually held on the Gregorian evening of N−1, but
  that is a per-jamaat, per-year decision. Verified: ABNJ held Chehlum on 20mi
  Safar in 1447H and 19mi in 1448H; Shahadat of Imam Hasan 28mi then 27mi.
  Never assume; this is why the sweep is load-bearing.
- **LLM extraction for the sweep, not regex.** Regex would work for ABNJ but
  would not survive a fork. Prompt for
  `{miqaat, hijri_date, gregorian_date, start_time, venue}` from arbitrary text.
- **Generate one year (1448H) by choice.** The kabisa set holds through 1450H
  against 642 date pairs, so `--years 3` is available whenever a longer horizon
  justifies the re-import.
- **No inbox data in the repo.** Mailing lists carry member names, especially
  teejia and sadaqallah notices. Extract only miqaat/time/venue, never cache raw
  bodies.

## Completed

- **Nine miqaats added** to `core/catalog.yaml` and ABNJ's
  `jamaats/nj-burhani/config.yaml`, all `confirmed: false`:
  `salgirah-imamuz-zaman`, `milad-mohammed-burhanuddin`, `pehli-raat-rajab`,
  `milad-amirul-mumineen`, `ayyam-barakat-khuldiyah`, `urus-taher-saifuddin`,
  `urus-abdul-qadir-najmuddin`, `khatmul-quran-shehrullah`,
  `urus-abdul-husain-husamuddin`. Originals listed in `HANDOFF-archive.md`.
  `milad-mohammed-burhanuddin` clears the review flag the sweep raised daily
  since 26 Sep.
- **Four dates corrected** to match mumineen.org:

  | Entry | Was | Now | 1448H date |
  |---|---|---|---|
  | `lailatul-qadr` | 23mi, offset 0 | 23mi, offset −1 (evening of 22mi) | 27 Feb 2027 |
  | `shahadat-ameerul-mumineen` | 21mi | 19mi | 24 Feb 2027 |
  | `urus-mohammed-burhanuddin` | 13mi ×3, offset 0 | 14mi ×3, offset −1 (raats ending on the 16mi urus) | 25–27 Aug 2026, unchanged |
  | `shahadat-fatema` | 9mi, offset −1 | 10mi, offset −1 | **19 Oct 2026** (was 18 Oct) |

- **Imported to the live calendar** by Shahzad on 5 Oct 2026: 15 events (12 new,
  3 moved). Shahzad confirmed the Fatema tuz Zahra majlis now shows on
  Mon 19 Oct 2026. The import file has been deleted.
- `core/test_sweep.py`: `test_day_range_uids` now supplies its own Ashara waaz
  and majlis entries, since ABNJ's config no longer lists them.
- **Published OAuth app no longer expires.** The daily sweep still succeeded on
  5 Oct 2026, past the 30 Sep mark (`logs/sweep-2026-10.log`).

## Checks

- All four test files pass on 5 Oct 2026 with `python_main_env`:
  `core/misri.py`, `core/test_sweep.py` (116 checks), `core/test_dates.py`,
  `core/test_personal.py`.
- `core/generate.py jamaats/nj-burhani --years 1` produces 86 events (102 before
  the Ashara entries came out).
- Each new or moved miqaat was checked against mumineen.org's 1448H list and
  against the ABNJ email that announced it in 1447H; all land on the announced
  evening. The two Khatmul Quran programmes are not on mumineen.org and rest on
  the emails alone.
- **Not run:** lint. `ruff` is not installed in `python_main_env`.
- **Confirmed by Shahzad, not by Claude:** the import result in Google Calendar.

## Open issues

- **Not pushed.** This session's commit is local only. The cron removal in
  `sweep.yml` reaches GitHub on push; the workflow is already disabled there.
- **Eid ul Adha placeholder not yet in the live calendar.** Import
  `jamaats/nj-burhani/nj-burhani-eid-ul-adha.ics` (one event, gitignored).
- **Yaumul Arafa and Ghadir-e-Khum have no start time**, so they default to
  19:00 until the sweep corrects them. Left as is.
- **`khatmul-quran-shehrullah` may have been a one-off** in 1447H. Revisit when:
  the Shehrullah 1448H monthly schedule arrives (about Feb 2027).
- **GitHub Support purge not sent.** The jamaat's list address was scrubbed
  from history on 23 Sep 2026 with `git filter-repo` and force-pushed, but
  GitHub may serve pre-rewrite commits by exact hash until it garbage-collects
  them. Any clone made before that still carries it; delete rather than pull.
- **Kabisa past 1450H is unproven.** The sweep halts if a whole Hijri month
  comes out shifted. Revisit when: the Moharram 1449H roundup arrives (about
  May 2027), which is itself the check.
- Bohra dates and personal dates items and the Codex review findings below.

## Next action

Import `jamaats/nj-burhani/nj-burhani-eid-ul-adha.ics` into the Miqaat calendar,
then push when Shahzad is ready.

## Daily Bohra dates and personal dates (both live 24 Sep 2026)

Members asked to see the Misri date on every day, not just miqaat days, and to
keep Hijri birthdays and anniversaries. Google Calendar's built-in Islamic
calendar is not the Misri one, so it cannot do either.

**Decided.**

- **Two shared calendars from one codebase, no fork or branch.** The Miqaat
  calendar stays as it is. A Bohra Dates calendar carries one all-day event per
  day. Codex reviewed the question independently and agreed.
- **The share page offers the dates as a separate optional section**, with its
  own iPhone and Google buttons. Nobody has tested whether one Google link can
  add two calendars; iPhone needs two `webcal://` subscriptions either way.
- **The dates cannot live in the Miqaat calendar:** `sweep.py --prune --apply`
  deletes every unstamped event in its range that `generate.py` did not produce.
- **Label** reads `13mi Rabi ul Akhar 1448H`, the daylight date. Each event's
  description still notes the maghrib change; drop it from `dates.py` whenever
  the calendar is next re-imported for another reason.
- **Horizon is 1450H**, the last verified year. `dates.py` refuses to go further.
- **Personal events** are a gitignored per-person input file plus a committed
  blank template, generating a private ICS each person imports. Entered in Hijri
  only ("23 Safar"); a 30mi Zilhaj date in a common year falls back to 29mi.
  UIDs come from the entry's name and year, so a corrected date moves the event
  on re-import; renaming leaves the old event behind.
- **Re-import moves an event by UID alone.** Tested 24 Sep 2026 in a throwaway
  calendar, with and without `SEQUENCE`: both moved, no duplicates.
- **Codex reviewed `personal.py` on 24 Sep 2026.** Left: a UID clash only if a
  fork names its jamaat `personal`, a raw carriage return inside a YAML name,
  and names over about 65 characters hitting the shared `fold()` bug.

**Done.**

- **Live calendar** "Anjuman-e-Burhani Bohra Dates", public since 24 Sep 2026,
  1064 events, ID
  `903e3d984a794f7789744ff56a86b900bec9f82b2a343f771cc0d2e3b6adcf4f@group.calendar.google.com`.
- **Share page** carries the Bohra dates section (`miqaat` repo, commit 599d17d).
- `core/dates.py`, `core/test_dates.py`, `core/personal.py`,
  `core/test_personal.py`, `personal/events.template.yaml`.
- **Shahzad's family calendar** "Our Family Bohra Dates" is live and private.
  Its master list is his local, gitignored `personal/events.yaml`; edit there and
  re-import, never in Google. One entry is marked "to confirm".

**Driving Google Calendar's import page from a browser agent.** The "Add to
calendar" list can stay open invisibly, so a click on Import lands on a calendar
row and switches the target (once to the public Miqaat calendar). Set the
target, confirm it in the page, and click Import through the page's own script
with a guard on the selected calendar name. The first Import click sometimes
does nothing, and an import can take 30 seconds.

**Left to do.**

1. **Test the share page's new buttons** once on an iPhone and once on Android.
2. **Personal dates, phase 2:** a form on the share site that downloads the ICS
   with nothing sent anywhere. Deferred 24 Sep 2026.
3. **Before 1451H:** extend `VERIFIED_THROUGH` only against a trusted source,
   then regenerate and re-import the dates calendar.

## Open findings from the Codex review

Codex reviewed the whole repo on 23 Sep 2026. These remain, most severe first.
Only those marked Confirmed were checked against the code.

| Finding | Where | Status |
|---|---|---|
| `seasonal` in config (13 Ashara ohbat Fridays) is never generated | `generate.py` `expand()` | Confirmed. Left as is by decision, 5 Oct 2026 |
| Full mail bodies go to Claude before anything filters them | `sweep.py` `extract()` | Confirmed, by design. `privacy.html` discloses it |
| `--prune --apply` can delete a hand-added event in the generated range | `sweep.py` `prune()` | Confirmed. Manual flag only; the schedule never passes it |
| Sweep writes a miqaat the jamaat does not list in `observes` | `sweep.py` `resolve()` | Unchecked. Now matters for Ashara waaz/majlis, which left `observes` |
| A later correction does not clear an earlier two-mail time conflict | `sweep.py` `merge_day()` | Unchecked |
| Plan groups by Gregorian year but UIDs use Hijri year; a miqaat twice in one Gregorian year may duplicate | `sweep.py` `plan()` | Unchecked |
| Announced venue is extracted but never written to `location` | `sweep.py` `apply()` | Unchecked |
| Timed multi-day miqaats (3-day Mohammed Burhanuddin urus) generate day one only | `generate.py` | Unchecked. The Aug 2026 sweep inserted days 2 and 3 itself (`logs/sweep-2026-08.log`) |
| `24:00` passes the time regex, then crashes mid-run after earlier writes | `sweep.py` `resolve()` | Unchecked |
| ICS line folding can emit a 76-byte line | `generate.py` `fold()` | Unchecked, cosmetic |

## How the sweep behaves

Each rule exists because the obvious implementation is wrong.

- **One mail yields a list of occurrences.** The monthly roundup, per-miqaat
  confirmations and multi-day ayyam share one code path.
- **Corrections need no merge logic.** Mail is processed oldest to newest and
  each write overwrites, so a later "Time change:" wins.
- **Idempotency lives in the description.** `source: generated` becomes
  `source: announcement <date>`, and a re-sweep skips anything already stamped
  at or after that mail's date. Without it every run re-notifies subscribers.
- **Ambiguity is never guessed.** No catalog match, low confidence, or a Hijri
  date that disagrees with the Gregorian one leaves the event untouched and
  prints it for review. A wrong time is worse than no time.
- **An empty Gmail result is not a quiet week.** Zero announcements triggers a
  second query with no sender filter; a dead mailbox errors. 429s and 5xx retry
  with backoff; 401, 403 and 404 fail immediately.
- **A whole month off by one halts the run**, as a `KABISA_REMAINDERS` error
  rather than an `observed_offset` question.
- **Only extracted fields leave the process.** Bodies are held in memory and
  cleared after each call; a bounded evidence snippet is the only quoted text
  that reaches the calendar.

## Source details

- Announcements come from `info@anjuman-e-burhani.org` to the jamaat list. The
  list address stays out of this file on purpose: the repo is public.
- Monthly roundup subject pattern: `<Month> <Year>H Miqaat Monthly Schedule`,
  marked tentative, with per-miqaat confirmations following.
- Mail states the daylight Hijri date of the evening a programme is held, plus
  the Gregorian date and maghrib time, so the sweep cross-checks rather than
  converts.
- Noise to exclude: Teejia/Sadaqallah/sipara notices, FMB thaali, RSVP
  reminders from `mawaid.nj@`, and its52.com mail.
- Austin jamaat's public calendars, for the two-layer pattern:
  `uqlnakio0ildkct3nh1eqjo0u4@group.calendar.google.com` and
  `fh0h90ic2lhhsst6088f2rlhc8@group.calendar.google.com`
