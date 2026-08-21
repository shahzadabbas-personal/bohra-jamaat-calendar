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

Import the resulting `.ics` into a new Google Calendar, then share that calendar
publicly. Do **not** publish the `.ics` as a subscription feed — Google refreshes
feeds only every 12–24 hours, which defeats a same-week timing correction. A
native shared calendar propagates immediately.

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
