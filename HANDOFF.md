# HANDOFF

Context for picking this project up in Cowork or Claude Code. Decisions and
open questions, not a transcript.

## What this is

A shareable Google Calendar of Dawoodi Bohra miqaat dates for Anjuman-e-Burhani
NJ, built so any jamaat can fork it and swap in their own schedule.

Scaffold and sweep are both done. `core/sweep.py` has run against a year of real
announcements and has written to the live calendar.

The repo went public on 23 Sep 2026 so other jamaats can fork it. Anything
committed from here on is visible to anyone.

## Decisions already made (and why)

**Two layers, not one.** Miqaat dates are computable; local program times are
not. Generated dates go in as all-day or default-time events; the announcement
sweep promotes them to real times. Austin's jamaat independently arrived at the
same split, which is decent validation.

**Native shared Google Calendar, not a published ICS feed.** ICS serves the
one-time bulk import; after that the calendar is the live artifact and the sweep
edits it directly.

Corrected later: this decision rested on Google polling *inbound* subscriptions
every 12–24 hours, which is a different direction from publishing a calendar's
own `.ics`. Google serves that outbound feed with caching disabled, so
subscribing to it is not stale, and it is how iPhones get the calendar at all.
See the sharing section in the README.

**`observed_offset` lives in jamaat config, not in the converter.** The Islamic
day starts at maghrib, so an evening majlis for Hijri day N is held on the
Gregorian evening of N−1. But this is not a fixed rule — it is a per-jamaat,
per-year decision.

**The offset genuinely varies by year.** Verified: ABNJ held Chehlum on 20mi
Safar in 1447H and 19mi in 1448H. Shahadat of Imam Hasan: 28mi in 1447H, 27mi
in 1448H. Milad un Nabi held at 11mi both years. So some are stable and some
are not — never assume. This is why the sweep is load-bearing rather than a
convenience.

**LLM extraction for the sweep, not regex.** ABNJ's format is clean and regex
would work fine for them. It would not survive porting to another jamaat, which
is the whole point of the repo. Prompt for
`{miqaat, hijri_date, gregorian_date, start_time, venue}` from arbitrary text.

**Publish 1448H only; defer the kabisa question.** We can't get a printed
taqweem past 1448H, so the leap-year cycle stays unverified. Rather than block
the project on it, cap generation at one year — `--years 1` covers 1448H, which
both the announcement emails and the printed calendar confirm. 1448H is safe
whichever way the cycle resolves, because it is the anchor year itself — the
kabisa setting never enters its arithmetic. 1449H is the first year that does
depend on it.

The sweep will settle this without anyone having to remember it. The monthly
roundup carries both the Hijri and the Gregorian date, so the Moharram 1449H
announcement (roughly May 2027) is itself the verification. `sweep.py` must
guard for it: one miqaat off by a day is an `observed_offset` question, but a
whole Hijri month off by the same amount in the same direction is a
`KABISA_REMAINDERS` error, and the sweep must halt.

**No inbox data in the repo.** Jamaat mailing lists carry member names,
especially in teejia and sadaqallah notices. Extract only miqaat/time/venue,
never cache raw bodies.

## Verification status

`core/misri.py` self-tests against 19 dated announcements spanning 1447H–1448H,
covering every month and the year rollover. All pass, roundtrip clean.
Generated 1448H dates match the real emails exactly.

**Unresolved: the kabisa set.** `KABISA_REMAINDERS` is currently
`{2,5,8,10,13,16,19,21,24,27,29}`. The anchor data only covers 1447H (common)
and 1448H, which cannot distinguish between the competing 30-year cycle
variants. Years beyond 1448H are unverified.

Superseded 24 Sep 2026: the mumineen.org check below extends this to 1450H.
`misri.py` and the README now say so, and `VERIFIED_THROUGH = 1450` in
`misri.py` is the single place that horizon lives.

The printed 1448H taqweem does not settle this. 1448H is already an anchor, and
every competing variant agrees on it. Settling the cycle needs a trusted
Gregorian date for 1 Moharram 1449H or later.

`core/test_sweep.py` covers the sweep's pure logic in 94 assertions: idempotency
stamps, the Hijri/Gregorian cross-check, all five ambiguity gates, ayyam fan-out,
correction ordering, the UID rules generate.py and sweep.py must agree on, and
Gmail backoff. Several anchor on `VERIFIED_ANCHORS` pairs. It runs in CI beside
the misri anchors.

**The extraction has now run against real mail.** 174 announcements spanning 400
days, no errors, 106 occurrences. It correctly returned nothing for 92 of them.
Reading that output found five miqaats the calendar was missing and a handful of
social announcements the prompt should have excluded, both since fixed.

**Still unproven: the kabisa set past 1450H.** The mumineen.org feed agrees with
misri.py on all 642 of its Hijri/Gregorian pairs across 1448H-1450H, and its
1 Moharram dates give 1448H 355 days and 1449H 354, which matches. That settles
remainders 8 and 9 and supports the Fatimid variant over the common tabular one,
which marks 7 rather than 8. The other eight positions in the cycle are untested,
so generation is safe to 1450H and speculative after it.

**Ashara and Eid timings come from the jamaat, not from mail.** A year of
announcements contains no Ashara timing mail at all -- the Ashara week itself is
nearly silent -- and the only Eid mail is the afternoon zohr/asr one. Those
entries carry hand-set defaults that no sweep will ever correct.

## Next steps

1. **Confirm the published OAuth app really stopped expiring.** Published on
   23 Sep 2026 and re-approved the same day. Google greyed out Publish until the
   Branding page had a home page, privacy policy and authorized domain; the
   `miqaat` Pages site covered all three (`privacy.html` added there,
   `shahzadabbas-personal.github.io` as the domain). No terms of service, no
   Search Console, no verification submitted. The app runs unverified, 1 of 100
   users. If the daily sweep still succeeds after 30 Sep 2026, the 7-day expiry
   is gone; if it lapses, check whether Google treats restricted `gmail.readonly`
   differently for unverified production apps.

   The jamaat's list address was scrubbed from all history on 23 Sep 2026 with
   `git filter-repo --replace-text` and force-pushed. Any other clone made
   before that still carries it; delete such clones rather than pull into them.
   GitHub may still serve the pre-rewrite commits to anyone holding their exact
   hash until it garbage-collects them. A GitHub Support request purges them
   outright; not yet sent.

2. **Ashara and Eid timings will never self-correct.** ABNJ announces neither, so
   those entries carry hand-set defaults. The Ashara raat majlis sits at 19:30,
   which approximates an hour before maghrib only while Ashara falls in June, and
   Ashara moves about eleven days earlier every year. Eid starts at 05:00 to clear
   fajr, which holds while Eid falls in February or March. Both need revisiting as
   they drift.

3. **The GitHub Actions workflow does nothing useful.** Its verify steps run and
   pass; the sweep step is a stubbed echo, and it could not authenticate
   unattended in any case. Either wire it to something real or drop the cron
   trigger and leave it on `workflow_dispatch`.

4. **Generation stops at one year by choice, not by doubt.** The kabisa set holds
   through 1450H against 642 independent date pairs, so `--years 3` is available
   whenever a longer horizon justifies the re-import.

## Daily Bohra dates (live 24 Sep 2026) and personal events (next)

Members asked to see the Misri date on every day, not just miqaat days, and to
keep Hijri birthdays and anniversaries. Google Calendar's built-in Islamic
calendar is not the Misri one, so it cannot do either.

**Decided.**

- **Two shared calendars from one codebase, no fork or branch.** The existing
  Miqaat calendar stays as it is. A new Bohra Dates calendar carries one
  all-day event per day. Shahzad first leaned towards putting the dates in the
  shared calendar and forking a miqaat-only variant. Codex reviewed the question
  independently and made the same recommendation.
- **The share page offers the dates as a separate optional section**, with its
  own iPhone and Google buttons below the miqaat ones. This replaced an earlier
  plan for a combined "Miqaats + Bohra dates" button. Nobody has tested whether
  one Google link can add two calendars, and it cannot be tested from the
  owner's account. iPhone needs two `webcal://` subscriptions either way.
- **Why the dates cannot live in the Miqaat calendar:** `sweep.py --prune
  --apply` deletes every unstamped event in its range that `generate.py` did not
  produce, so it would delete the daily dates. A miqaat-only copy would also
  need the sweep to keep two calendars' timings in sync, and anyone who added
  both would see each miqaat twice. (It would not spam notifications: the sweep
  patches with `sendUpdates="none"`.)
- **Label** reads `13mi Rabi ul Akhar 1448H`. It is the daylight date; from
  maghrib it is the next Hijri day. The share page and the calendar description
  leave that out, because Bohras already know it. Each event's own description
  still says it; removing it would mean a full re-import, which a one-line fix
  does not justify. Drop it from `dates.py` whenever the calendar is next
  re-imported for another reason.
- **Horizon is 1450H**, the last verified year. `dates.py` refuses to go further.
- **Personal events** are for any member who forks the repo: a gitignored
  per-person input file plus a committed blank template, generating a private
  ICS each person imports into their own Google account. Nothing personal is
  committed, because the repo is public.
- **Bohra birthdays** can be entered as a Hijri date or as a Gregorian birth date
  with a "born after maghrib" flag. A 30mi Zilhaj date in a common year (29-day
  Zilhaj) falls back to **29mi Zilhaj**.

**Done.**

- **Live calendar:** "Anjuman-e-Burhani Bohra Dates", created and made public
  on 24 Sep 2026 with See event details. Google reported 1064 of 1064 events
  imported. ID:
  `903e3d984a794f7789744ff56a86b900bec9f82b2a343f771cc0d2e3b6adcf4f@group.calendar.google.com`.
  Spot check: 24 Sep 2026 shows 13mi Rabi ul Akhar 1448H, matching
  mumineen.org. Google's built-in Islamic date shows the 12th that day.
- **Share page** carries the optional Bohra dates section (`miqaat` repo,
  commit 599d17d). The new buttons have not been tapped on a real iPhone or
  Android phone yet.
- `core/dates.py` builds the Bohra Dates ICS: 1064 days, 1448H-1450H, 293 KB
  (Google's import limit is 1 MB per file, not a count of events).
- `core/test_dates.py` covers no gaps or repeats across month and year
  boundaries, all 19 `VERIFIED_ANCHORS`, and unique UIDs. It runs in CI.
- `generate.py`: file writing and the CRLF check moved into `write_ics()` so
  `dates.py` shares them. The miqaat ICS is byte-identical before and after,
  apart from DTSTAMP.
- `misri.py` and the README warn from 1450H, not 1448H. The README has a
  "Daily Bohra dates" section.
- All tests pass. No linter is configured; a one-off `uvx ruff check` flagged
  only `datetime.now()` in `dates.py`, which copies `generate.py` on purpose,
  and findings that already sat in `generate.py` beforehand.

**Left to do.**

1. **Test the share page's new buttons** once on an iPhone and once on Android.
2. **Phase 2, personal events:** input template, gitignore rule, generator,
   tests (including the 30mi Zilhaj fallback and the maghrib flag), README
   steps. Codex's review also asked for a documented way to update or delete a
   personal event after import. Deterministic UIDs update events on re-import
   but never remove them, so a deleted entry needs a stated path.
3. **Before 1451H:** extend `VERIFIED_THROUGH` only against a trusted source,
   then regenerate and re-import the dates calendar.

## Open findings from the Codex review

Codex reviewed the whole repo on 23 Sep 2026. Three findings are fixed (all-day
banners, timeless announcements, same-day corrections), plus the two from its
review of the OAuth fix. These remain, most severe first. Only the first three
were checked against the code; the rest are Codex's word until someone reads
the line.

| Finding | Where | Status |
|---|---|---|
| `seasonal` in config (13 Ashara ohbat Fridays) is never generated | `generate.py` `expand()` | Confirmed. Needs a re-import once fixed |
| Full mail bodies go to Claude before anything filters them | `sweep.py` `extract()` | Confirmed, by design. `privacy.html` discloses it |
| `--prune --apply` can delete a hand-added event in the generated range | `sweep.py` `prune()` | Confirmed. Manual flag only; the schedule never passes it |
| Sweep writes a miqaat the jamaat does not list in `observes` | `sweep.py` `resolve()` | Unchecked |
| A later correction does not clear an earlier two-mail time conflict | `sweep.py` `merge_day()` | Unchecked |
| Plan groups by Gregorian year but UIDs use Hijri year; a miqaat twice in one Gregorian year may duplicate | `sweep.py` `plan()` | Unchecked |
| Announced venue is extracted but never written to `location` | `sweep.py` `apply()` | Unchecked |
| Timed multi-day miqaats (3-day Mohammed Burhanuddin urus) generate day one only | `generate.py` | Unchecked |
| `24:00` passes the time regex, then crashes mid-run after earlier writes | `sweep.py` `resolve()` | Unchecked |
| ICS line folding can emit a 76-byte line | `generate.py` `fold()` | Unchecked, cosmetic |

## Miqaats the inventory found and nobody added

Extracting 400 days of announcements turned up programmes ABNJ holds that
`catalog.yaml` has no entry for. Five went in: Ayyam ul Beez, Lailatus Salaseen,
Aakhri Jumoa, and two that were already in the catalog but missing from ABNJ's
observes list, Lailatul Meraj and Shab-e-Barat.

These did not. They sit here so nobody has to run the inventory again to find
them, which costs a few dollars and 174 extraction calls.

| What the mail called it | Announced | Hijri as stated |
|---|---|---|
| Salgirah mubarak ni raat of Imamuz Zaman (SA) | 25 Sep 2025 | 3mi Rabi ul Akhar |
| Milad raat mubarak of Syedna Mohammed Burhanuddin | 11-12 Oct 2025 | 19-20mi Rabi ul Akhar |
| Pehli raat of Rajab ul Asab | 19 Dec 2025 | not stated |
| Milad ni raat of Amirul Mumineen (AS) | 31 Dec 2025 | 12mi Rajab |
| Ayyamul Barakatil Khuldiyah, Khatmul Quran majlis | 4-5 Jan 2026 | 16-17mi Rajab |
| Lailat Urs Mubarak Syedna Taher Saifuddin, waaz | 6 Jan 2026 | 18mi Rajab |
| Urs Syedna Abdul Qadir Najmuddin (Ujjain) | 14 Jan 2026 | 26mi Rajab |
| Khatmul Quran ni majlis, Shehrullah | 20-22 Feb 2026 | 4th-6th Shehrullah |
| Urus raat majlis, Syedna Abdul Husain Husamuddin | 12 Jun 2026 | 27mi Zilhaj |

Read those Hijri dates carefully before trusting them. They are what the mail
said, and a raat majlis announced as 26mi is usually the eve of 27mi, so the
canonical date is often one higher. Check each against the taqweem rather than
converting from the Gregorian column.

Two notes on the catalog while here. It already holds Syedna Taher Saifuddin's
milad in Zilqad but not his urus in Rajab. And `urus-abdul-qadir-hakimuddin` at
26mi Shawwal is a different person from Abdul Qadir Najmuddin of Ujjain above.

## How the sweep behaves

The rules below started as the spec for `sweep.py` and now describe what it
does. The reasoning is worth keeping — each one exists because the obvious
implementation is wrong.

- **Extraction is Claude, not regex.** ABNJ's format is clean and regex would
  work for them. It would not survive a fork, which is the point of the repo.
- **One mail yields a list of occurrences.** That is what makes the monthly
  roundup, per-miqaat confirmations and multi-day ayyam share one code path: a
  roundup returns a dozen entries, an ayyam returns one per day.
- **Corrections need no merge logic.** The sweep works through mail oldest to
  newest and each write overwrites, so a "Time change:" or "Correction-" that
  arrives later simply wins.
- **Idempotency lives in the description.** `source: generated` becomes
  `source: announcement <date>`, and a re-sweep skips anything already stamped at
  or after that mail's date. Without it every run re-edits every event and mails
  a notification to every subscriber.
- **Ambiguity is never guessed.** No catalog match, low confidence, or a Hijri
  date that disagrees with the Gregorian one leaves the event untouched and
  prints it for review. A wrong time is worse than no time.
- **An empty Gmail result is not a quiet week.** Zero announcements triggers a
  second query with no sender filter. If the mailbox is dead too, the sweep
  errors instead of reporting nothing to do. Transient 429s and 5xx retry with
  backoff; 401, 403 and 404 fail immediately.
- **A whole month off by one halts the run.** One miqaat a day out is an
  `observed_offset` question. An entire Hijri month shifted the same way is a
  `KABISA_REMAINDERS` error, and the sweep stops rather than writing dates on top
  of a broken converter.
- **Only extracted fields leave the process.** The sweep holds bodies in memory,
  clears them after each call, and never writes one to a file or an event. A
  bounded evidence snippet is the only quoted text that reaches the calendar.

## Source details

- Announcements come from `info@anjuman-e-burhani.org` to the jamaat list. The
  list address stays out of this file on purpose: git tracks HANDOFF.md, and the
  repo's own rule forbids committing mailing list addresses.
- Monthly roundup subject pattern: `<Month> <Year>H Miqaat Monthly Schedule`,
  explicitly marked tentative, with per-miqaat confirmations following
- Body format gives both Hijri and Gregorian dates plus maghrib time, so the
  sweep does not need to do its own conversion — it can cross-check instead
- Noise to exclude: Teejia/Sadaqallah/sipara notices, FMB thaali, RSVP
  reminders from `mawaid.nj@`, and its52.com mail (central Dawat, unrelated)
- Austin jamaat's public calendars, for reference on the two-layer pattern:
  `uqlnakio0ildkct3nh1eqjo0u4@group.calendar.google.com` and
  `fh0h90ic2lhhsst6088f2rlhc8@group.calendar.google.com`
