# Project rules

Read `HANDOFF.md` first for current state and decisions.

- **mumineen.org decides a miqaat's canonical Hijri day; ABNJ's emails decide
  which evening the jamaat holds it.** The second is what `observed_offset`
  records. mumineen.org lists many urus with no programme, so check only
  miqaats the jamaat holds in person.
- **Change the live calendar by importing only the affected events.** Never
  re-import the full `jamaats/nj-burhani/nj-burhani.ics`: re-import matches by
  UID, so it resets every time the sweep has promoted back to its generated
  default.
