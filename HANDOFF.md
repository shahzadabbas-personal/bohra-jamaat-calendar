# HANDOFF

Context for picking this project up in Cowork or Claude Code. Decisions and
open questions, not a transcript.

## What this is

A shareable Google Calendar of Dawoodi Bohra miqaat dates for Anjuman-e-Burhani
NJ, built so any jamaat can fork it and swap in their own schedule.

Scaffold and sweep are both done. `core/sweep.py` has run against a year of real
announcements and has written to the live calendar.

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

1. Kabisa set: deferred, see the decision above. Cap generation at `--years 1`
   until the Moharram 1449H announcement lands, roughly May 2027.
2. Reconcile `core/catalog.yaml` against the printed calendar — the catalog was
   derived from ~14 months of email, so anything ABNJ observes but didn't email
   about in that window is missing.
3. Re-import the `.ics` after regenerating, then sweep, in that order. Importing
   resets an event's description, so a sweep afterwards restores the
   announcement stamps it overwrote.
4. Decide whether the calendar is ready to share. Most events still carry
   generated timings, and a member reading one cannot tell a confirmed time from
   a default without opening the description.
5. Watch the first multi-day ayyam the sweep meets. Tests cover the fan-out, but
   it has never run against a real announcement; the Burhanuddin urus is the
   next chance.

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
