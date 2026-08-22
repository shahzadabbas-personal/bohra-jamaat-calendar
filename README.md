# bohra-miqaat-calendar

Generate a shareable miqaat calendar for a Dawoodi Bohra jamaat, and keep the
timings current from the jamaat's own announcement emails.

The Misri calendar is tabular, so miqaat dates are computable years ahead. What
is *not* computable is when a given jamaat actually holds the program — that
varies by jamaat and, as it turns out, by year. This repo separates the two.

## Verify before you publish

**The kabisa (leap year) set in `core/misri.py` is unverified.** Anchor data
only covers 1447H–1448H, which cannot distinguish between the competing 30-year
cycle variants. Check `KABISA_REMAINDERS` against your jamaat's printed taqweem
or Bu Saheba's Sahifa before trusting anything past 1448H. An off-by-one there
shifts every subsequent year.

Generated dates carry religious weight. Treat this tool as a scheduling aid,
never as an authority. Reconcile against the printed taqweem.

## Layout

```
core/
  misri.py       Hijri <-> Gregorian. Anchored on 1 Moharram 1448H = 15 Jun 2026,
                 validated against 19 announcement emails spanning a full year.
  catalog.yaml   Superset of miqaats. No jamaat observes all of them.
  generate.py    catalog + jamaat config -> ICS
  sweep.py       announcement email -> timing correction
jamaats/
  _template/     copy this
  nj-burhani/    reference implementation
```

## Use

```bash
pip install -r requirements.txt
python3 core/misri.py                                   # run the anchor tests
python3 core/generate.py jamaats/nj-burhani --years 5
```

Import the resulting `.ics` into a new Google Calendar, then share that calendar.
The import is one-time: from then on the calendar is the live artifact and the
sweep edits it in place.

UIDs are deterministic, so regenerating and re-importing updates events in place
instead of duplicating them.

Once the calendar exists, set `calendar_id` in the jamaat config and sweep the
announcements into it. The sweep prints what it would change and writes nothing
until you pass `--apply`:

```bash
python3 core/sweep.py jamaats/nj-burhani            # show the plan
python3 core/sweep.py jamaats/nj-burhani --apply    # write it
```

The sweep needs a Gmail and Calendar OAuth client at `jamaats/<id>/credentials.json`
and an `ANTHROPIC_API_KEY` in your environment. It leaves anything it cannot read
cleanly untouched and prints it for you to check by hand.

## Sharing it

Google's share link does not survive being passed around. WhatsApp will not
linkify a `webcal://` address, tapping an `https` `.ics` on iOS imports static
copies instead of subscribing, and the Google Calendar app cannot add a calendar
on a phone on any platform. No single link works for everyone.

A small public page gives each platform the route that works:

<https://shahzadabbas-personal.github.io/miqaat/> — source in
`shahzadabbas-personal/miqaat`, two files, nothing but links to a calendar that is
already public.

- **iPhone and iPad** get a `webcal://` button, which Apple Calendar subscribes to.
  Tell people to set Settings → Calendar → Accounts → Fetch New Data → Refresh
  Calendars to the shortest option. The default is weekly, which makes a
  subscription look broken.
- **Android and computers** get the `cid` link, which adds the calendar to a Google
  account and propagates immediately.
- **iPhone users who prefer the Google Calendar app** have to use that second button
  once from a computer. The app itself cannot add a calendar, so there is no way
  around a browser for them.

Sharing the calendar with people one at a time works, but somebody has to do it
for every new member. Sharing it with a Google Group would avoid that, if the
jamaat's list happens to be one.

Google serves a public calendar's `.ics` with caching disabled, so a subscriber
sees a correction as soon as their device refetches. That is the opposite
direction from Google Calendar subscribing to someone else's feed, which it polls
every 12 to 24 hours; do not confuse the two when reasoning about staleness.

Importing can add and update events but never remove one, so an entry you drop
from the config leaves a ghost on the calendar. `--prune` finds those:

```bash
python3 core/sweep.py jamaats/nj-burhani --prune            # list them
python3 core/sweep.py jamaats/nj-burhani --prune --apply    # delete them
```

It reads no mail and calls no model, so it costs nothing to run. It never
deletes an event carrying an announcement stamp, and it ignores anything outside
the range you generated.

## Running it on a schedule

`tools/run_sweep.py` is a runner for Windows Task Scheduler. It launches under
`pythonw.exe`, so no console window appears, and writes to `logs/`.

Schedule it daily rather than weekly. While the OAuth app sits in Testing, Google
expires the authorisation seven days after consent rather than seven days after
last use, so a weekly run lands on that boundary and fails most weeks. A daily
run turns each re-approval into a week of unattended operation, and puts
announcements on the calendar within a day of the jamaat sending them.

When the seven days do run out, the log says so and names the fix: run the sweep
once in a terminal so a browser can open, approve it, and the schedule resumes.

## Adding your jamaat

Copy `jamaats/_template/`, rename it, edit `config.yaml`. No code changes.

The field that matters most is `observed_offset`: days to shift from the
canonical Hijri date. `-1` means the program runs the previous evening — correct
for most evening majlis, since after maghrib it is already that Hijri day.

Start with the miqaats you're sure about. Twenty accurate events beat two
hundred guesses. Anything with `confirmed: false` renders as TENTATIVE and
carries a warning in its description.

## Privacy

Jamaat mailing lists carry personal information about community members —
funeral notices especially. The sweep must extract only miqaat name, date, time
and venue. **Never commit raw email bodies, mailing list addresses, or member
names.** `.gitignore` covers the obvious cases; the rest is discipline.

## Contributing

New miqaats go in `core/catalog.yaml` with canonical Hijri dates only. Local
observance decisions belong in your jamaat config, not the catalog.

If you find a date that disagrees with your printed taqweem, please open an
issue with the taqweem year and page. Corrections are the most valuable thing
you can contribute.

## License

MIT.
