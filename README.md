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
hundred guesses. Anything with `confirmed: false` carries a line in its
description saying the date is a projection and telling the reader to check it
against the taqweem, until a sweep confirms it.

### Google credentials

The sweep reads your jamaat's mail and writes your calendar, so it needs an OAuth
client of your own. Google reorganised this console in 2025; the labels below are
the current ones.

1. Sign in at <https://console.cloud.google.com> with the account that receives
   the announcements. If a different account owns the calendar, share the
   calendar with the mail account rather than splitting the credentials.
2. Create a project. **No organization** is the right parent for a personal
   account.
3. Enable both APIs from the search bar: **Gmail API**, then **Google Calendar
   API**. Missing one fails later, and the two failures look nothing alike.
4. **Google Auth Platform → Branding → Get started.** Give an app name, pick your
   address as the user support email, choose **External**, add a developer
   contact address, accept the policy, Create. Those three fields are all it
   asks for.
5. Do not upload a logo. The page says so itself: a logo forces the app into
   verification.
6. **Audience → Test users → Add users → your own address.** Google refuses the
   login without this, and the error does not say why.
7. **Clients → Create client → Application type: Desktop app → Create.** A Web
   application client fails with a redirect URI error.
8. Download the JSON, rename it `credentials.json`, and drop it in your jamaat
   directory beside `config.yaml`. `.gitignore` already covers it.

The first sweep opens a browser. Google shows "Google hasn't verified this app",
which is normal for a personal client: **Advanced → Go to (your app name)**, then
approve both permissions. A `token.json` appears next to the credentials.

Then the sting. While the app's publishing status is Testing, Google expires that
authorisation **seven days after consent**, no matter how often you use it. The
sweep will fail on the eighth day and the log says so. Publishing the app removes
the expiry, but Google requires a home page, privacy policy and terms of service
on a domain verified in Search Console before an external app can go to
production. For one person running one jamaat, re-approving weekly is usually the
smaller cost.

### Extraction

The sweep needs `ANTHROPIC_API_KEY` in the environment. A week of announcements
costs a fraction of a cent; reading a year of them, which is worth doing once to
find miqaats your catalog is missing, costs a few dollars.

### Your own sharing page

The page this repo points at serves one calendar. Copy `index.html` from
`shahzadabbas-personal/miqaat`, replace the calendar id in the `webcal://` link,
and replace the `cid` value with your own id base64-encoded:

```bash
printf '%s' 'your-id@group.calendar.google.com' | base64
```

Publish it anywhere static. It needs no build step and loads nothing external.

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
