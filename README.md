# Adventurebot

A private Telegram bot that connects to your [AdventureLog](https://github.com/seanmorley15/AdventureLog) instance. Browse trips, view location details, manage checklists, and discover nearby places — all from Telegram.

---

## Features

- **My Trips** — list all collections, drill into any trip for locations, transportation, calendar, and checklists
- **Itinerary** — step through each stop in a trip with dates and details
- **Calendar** — view a trip's events (locations + flights/transport) sorted by date
- **Location detail** — name, rating, description, coordinates, and one-tap links to Apple Maps / Google Maps / navigation
- **Checklists** — browse, tick off, and add items to any checklist in a trip
- **Recommendations nearby** — get up to 10 Google Places results near any location; filter by Food, Lodging, or Tourism; choose radius (5–50 km)
- **Search** — full-text search across all locations and collections
- **Where was I on…** — look up which location you were visiting on any given date
- **Schedulers** — evening digest and checklist reminder; configure time and timezone per chat
- **Private by default** — restrict access to a comma-separated allowlist of Telegram chat IDs

---

## Requirements

- Python 3.12+
- A running AdventureLog instance (v0.11 or newer) — see the [official installation guide](https://adventurelog.app/docs/install/)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/t0mer/Adventurebot.git
cd Adventurebot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy the example file and fill in your values:

```bash
cp env.example .env
```

| Variable | Required | Description |
|---|:---:|---|
| `TELEGRAM_TOKEN` | ✓ | Bot token from @BotFather |
| `AL_URL` | ✓ | Full URL of your AdventureLog instance, e.g. `https://adventure.example.com` |
| `AL_USERNAME` | ✓ | AdventureLog username |
| `AL_PASSWORD` | ✓ | AdventureLog password |
| `ALLOWED_IDS` | | Comma-separated Telegram chat IDs that may use the bot. Leave empty to allow everyone. Find your chat ID by messaging [@userinfobot](https://t.me/userinfobot). |

Example `.env`:

```env
TELEGRAM_TOKEN=123456:ABCdefGHIjklMNOpqrSTUvwxYZ
AL_URL=https://adventure.example.com
AL_USERNAME=admin
AL_PASSWORD=secret
ALLOWED_IDS=367468362,112233445
```

### 4. Run the bot

```bash
python3 -m bot.main
```

To keep it running in the background with tmux:

```bash
tmux new-session -d -s adventurebot 'python3 -m bot.main'
```

To attach and check logs:

```bash
tmux attach -t adventurebot
```

---

## Running with Docker

### docker-compose (recommended)

1. Pull the image and start the container:

```bash
docker compose up -d
```

The compose file reads credentials from your `.env` file automatically. Make sure it exists and is filled in (see [Configure environment](#3-configure-environment)).

Scheduler data is persisted in a local `data/` directory mounted into the container.

### docker run

```bash
docker run -d \
  --name adventurebot \
  --restart unless-stopped \
  -e TELEGRAM_TOKEN=your_token \
  -e AL_URL=https://adventure.example.com \
  -e AL_USERNAME=admin \
  -e AL_PASSWORD=secret \
  -e ALLOWED_IDS=123456789 \
  -v $(pwd)/data:/app/data \
  techblog/adventurebot:latest
```

### Viewing logs

```bash
docker compose logs -f
```

---

## Screenshots

### Main Menu

<img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/main_menu.jpeg" width="300" alt="Main menu"/>

Send `/start` to open the main menu. Four options: **My Trips**, **Search by keyword**, **Where was I on…**, and **Schedulers**.

---

### Trips

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/trips_list.jpeg" width="280" alt="Trips list"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/trip_detail.jpeg" width="280" alt="Trip detail"/></td>
</tr>
<tr>
<td>All collections from AdventureLog, each showing its date range.</td>
<td>Tap a trip to choose what to browse: Locations, Transportation, Calendar, Checklists, or Recommendations nearby.</td>
</tr>
</table>

---

### Itinerary & Calendar

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/itinerary_stop.jpeg" width="280" alt="Itinerary stop"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/calendar.jpeg" width="280" alt="Calendar"/></td>
</tr>
<tr>
<td>Step through each stop in a trip. Tap <strong>Details</strong> to see the full location card, or <strong>Next</strong> to advance.</td>
<td>Calendar view lists all events in the trip (locations and transport) sorted by date.</td>
</tr>
</table>

---

### Location Detail

<img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/location_detail.jpeg" width="300" alt="Location detail"/>

Each location shows its name, rating, description, and GPS coordinates. Buttons open Apple Maps, Google Maps, or start turn-by-turn navigation. Tap **Recommendations nearby** to find places around this location.

---

### Recommendations

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/recommendations_category.jpeg" width="280" alt="Choose category"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/recommendations_radius.jpeg" width="280" alt="Choose radius"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/recommendations_results.jpeg" width="280" alt="Results"/></td>
</tr>
<tr>
<td>Choose a category: Food, Lodging, or Tourism.</td>
<td>Choose a search radius: 5, 10, 20, or 50 km.</td>
<td>Up to 10 Google Places results with ratings, review count, and distance. Names link directly to Google.</td>
</tr>
</table>

---

### Checklists

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/checklists_list.jpeg" width="280" alt="Checklists list"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/checklist_items.jpeg" width="280" alt="Checklist items"/></td>
</tr>
<tr>
<td>All checklists for a trip, with item counts.</td>
<td>Tap any item to toggle it done/undone. Tap the trash icon to remove it. Use <strong>+ Add item</strong> to append a new one.</td>
</tr>
</table>

---

### Schedulers

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/schedulers.jpeg" width="280" alt="Schedulers menu"/></td>
<td><img src="https://raw.githubusercontent.com/t0mer/Adventurebot/main/assets/screenshots/scheduler_evening_digest.jpeg" width="280" alt="Evening digest settings"/></td>
</tr>
<tr>
<td>Two built-in schedulers: <strong>Checklist reminder</strong> and <strong>Evening digest</strong>. Each shows its current on/off state.</td>
<td>Configure the evening digest: enable/disable, set the firing time, and set your timezone.</td>
</tr>
</table>

---

## Project Structure

```
bot/
  main.py                      # Entry point; wires all handlers
  client.py                    # AdventureLog API client (httpx, session auth)
  handlers.py                  # Core handlers: trips, locations, checklists, search
  recommendations_handlers.py  # Recommendations flow (ConversationHandler)
  scheduler_handlers.py        # Scheduler configuration handlers
  scheduler_jobs.py            # APScheduler job functions
  scheduler_store.py           # Persist scheduler settings to data/schedulers.json
  keyboards.py                 # Inline keyboard builders
tests/                         # pytest test suite
```

---

## AdventureLog Compatibility

Requires AdventureLog **v0.11 or newer** — this version renamed "Adventures" to "Locations". Older instances use different API paths and are not supported.

---

## Troubleshooting

The bot authenticates to AdventureLog with your **username and password** (a session login). Most "it's not working" reports come down to that sign-in failing. When it does, you'll now see a clear line in the logs and a message in the chat instead of a silent empty result:

```
ERROR bot.client: AdventureLog login failed for user 'admin' (HTTP 400): ... — check AL_USERNAME/AL_PASSWORD.
```

A healthy start logs the opposite:

```
INFO bot.client: AdventureLog login succeeded for user 'admin'
```

### "No trips found" / everything is empty

This is almost always a sign-in failure, not missing data. Check the logs for the `login failed` line above, then work through the causes below.

### Password with special characters gets mangled in `.env`

If your password contains `#`, `!`, or `$`, an unquoted value in `.env` will be **truncated or altered** — `#` in particular is treated as the start of a comment, so `AL_PASSWORD=My#Secret!Pass` silently becomes `My`. Always **quote** it:

```env
AL_PASSWORD='My#Secret!Pass'
```

Then confirm the container actually received the full value (the definitive check):

```bash
docker compose exec adventurebot printenv AL_PASSWORD
# must print the complete password, not a truncated prefix
```

If `printenv` still shows a truncated value even when quoted, either move the variables into an `env_file:` (which parses quotes reliably) or change the AdventureLog password to one without `#`/`!`/`$`.

### Login rejected as invalid *even though the password is correct*

AdventureLog rate-limits repeated **failed** logins. After several bad attempts it will reject sign-in with an "invalid credentials" response for a cool-down window — even for the correct password. If you've been testing with a wrong password, **wait a few minutes** and try again, and avoid rapid retries.

### The account has no trips

The bot only sees data **owned by the account it signs in as**. `AL_USERNAME` must be the AdventureLog user that actually owns your collections/locations — a different or empty account will connect fine but show nothing. Verify by logging into the AdventureLog web UI with the same credentials and confirming your trips are there.

### Why not an API key?

AdventureLog API keys are **not** used: on current instances `/api/collections` returns a `500 Internal Server Error` under API-key authentication, so trips can't be listed. The bot therefore uses username/password session auth, which reads collections and locations correctly.
