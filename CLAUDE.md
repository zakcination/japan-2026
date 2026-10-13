# SHF Power Trip Japan 2026 — the trip app

An offline iPhone web app for a group trip to Japan (17–27.10.2026, flights via Shanghai), published on GitHub Pages:
https://zakcination.github.io/japan-2026/?trip=miras-aikosh. The owners are Мирас and Айкош; the group is five people from
Kazakhstan. Everyone reads Russian — answer the owner in Russian, short and to the point.

## When the owner asks from the trip (phone, Claude Code on the web)

Sessions started from the app's «Claude Code» button carry the day on screen and a request. Treat them as a travel
assistant with write access to the plan:

- **A question** (what's next, where to eat, how to get there, translate, what to do if…): answer in 1–5 sentences from
  `trips/miras-aikosh.json` and general knowledge. Do not edit files. Never invent train times, prices or opening hours —
  give a Google Maps link (`https://www.google.com/maps/search/?api=1&query=…`) and say «проверьте».
- **A change to the plan** (move, add, drop a stop; a new booking; a note): edit `src/today_data.py` only (the single
  source; `trips/*.json` are generated), then publish (below). Say in one line what changed and that the app updates on
  next open. If the request is ambiguous, ask one short question first.
- **Emergency or insurance**: the facts are in `src/today/sos_data.js`. Insurance first (Mastercard assistance
  +44 1273 765321; claims at mcpeaceofmind.com within 90 days); life at risk → 119 (Japan) / 120 (China) first.
- Keep the answer short. Don't summarise the repo or the diff unless asked.

## Publish a change

```bash
cd src
python3 today_data.py            # regenerates trips/*.json from today_data.py
python3 build_guide.py           # builds src/Japan_Guide_2026.html (needs src/package/dist — committed)
cp Japan_Guide_2026.html ../index.html
cd .. && git add -A src trips index.html && git commit -m "<what changed, in English>" && git push origin main
```

Tests (when a local environment has them): `cd src && ../.venv/bin/python -m pytest tests -q -n auto`. In a cloud
session without Playwright, at least run `python3 -c "import json; json.load(open('trips/miras-aikosh.json'))"` and check
the build prints no error. GitHub Pages updates within ~1 minute.

## Never

- Never put ticket or booking numbers, seats, addresses of private stays, phone numbers, card or policy numbers, PINs
  or keys in the repo — it is public. Hotel names and flight numbers are fine.
- Never commit `survey/` or `research/` (git-ignored, private).
- Never touch Supabase secrets, `supabase/migrations` or the Edge Functions from a phone session — those changes need
  the owner at a computer.
- The couples are always together — Мирас and Айкош, Аманжан and Сания: never plan split days for either couple.
