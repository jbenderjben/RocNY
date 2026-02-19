import pandas as pd
import re
from curl_cffi import requests
from icalevents.icalevents import parse_events
from datetime import datetime, timedelta, timezone
import sys

# ANSI color codes
GREEN, RED, RESET = '\033[92m', '\033[91m', '\033[0m'

def sanitize_text(text):
    """Clean descriptions of HTML, newlines, and carriage returns for Excel."""
    if not text or text == "N/A":
        return "N/A"
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Replace &nbsp; and other entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
    # Replace all newlines and carriage returns with a single space
    text = text.replace('\r', ' ').replace('\n', ' ')
    # Remove extra spaces
    text = ' '.join(text.split())
    return text


def print_left_justified(df, cols):
    """Print a DataFrame subset with left-justified columns for console output."""
    if df.empty:
        return
    sub = df[cols].astype(str)
    widths = {}
    for c in cols:
        max_cell = sub[c].map(len).max() if not sub.empty else 0
        widths[c] = max(len(c), int(max_cell))
    # header
    header = '  '.join(c.ljust(widths[c]) for c in cols)
    print(header)
    for _, row in sub.iterrows():
        print('  '.join(row[c].ljust(widths[c]) for c in cols))

def fetch_calendar(name, url):
    print(f"Syncing: {name}...")
    try:
        # get the entire content string
        response = requests.get(url, impersonate="chrome110", timeout=30)
        response.raise_for_status()
        content = response.text

        # nope out if this is null or not the right content
        if 'BEGIN:VCALENDAR' not in content.upper():
            return []

        # Events will be extracted and parsed within this timeframe
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=30)
        evs = parse_events(content, start=start, end=end)
        
        data = []
        for ev in evs:
            # Convert event start to the local/system timezone and keep it consistent
            local_start = ev.start.astimezone()
            data.append({
                'FromCal': name,
                'Summary': sanitize_text(ev.summary),
                'DateTime': local_start.strftime('%Y-%m-%d %I:%M %p'),  # 12 hour human friendly format
                'DateTime24': local_start,                              # 24 hour format for sorting
                'Weekday': local_start.strftime('%A'),                  # full weekday name
                'Location': sanitize_text(ev.location),
                'Description': sanitize_text(ev.description),
                'Recurring': (ev.recurring),
                'UID': str(ev.uid) if hasattr(ev, 'uid') else "N/A"
            })
        return data
    except Exception as e:
        print(f"  {RED}Failed {name}: {e}{RESET}")
        return []

# --- CONFIGURATION ---
MASTER_URL = "https://calendar.google.com/calendar/ical/eisn9fqjjq1it4hjmd2f2ril4g66hb61%40import.calendar.google.com/public/basic.ics"

COMMUNITY_SOURCES = {
    "GVI": "https://calendar.google.com/calendar/ical/gjpdrjkt0hsf4j7v0mgrq8lfsjmf2vjb%40import.calendar.google.com/public/basic.ics",
    "IndiWMC": "https://calendar.google.com/calendar/ical/v63g68dgvie9csadovgiaq4v4q4jds96%40import.calendar.google.com/public/basic.ics",
    "Gritroc": "https://calendar.google.com/calendar/ical/grit.roc%40gmail.com/public/basic.ics",
}

# --- EXECUTION ---
print("\n" + "="*40 + "\nROCHESTER PROTEST CALENDAR AUDIT\n" + "="*40)
master_events = fetch_calendar("RocNY", MASTER_URL)
master_df = pd.DataFrame(master_events)

all_community = []
for name, url in COMMUNITY_SOURCES.items():
    all_community.extend(fetch_calendar(name, url))
community_df = pd.DataFrame(all_community)

if master_df.empty and community_df.empty:
    sys.exit(f"\n{RED}Critical Error: No data retrieved.{RESET}")

# Fingerprints
master_keys = set(master_df['Summary'].str.lower() + master_df['DateTime']) if not master_df.empty else set()
community_keys = set(community_df['Summary'].str.lower() + community_df['DateTime']) if not community_df.empty else set()

print("\n" + "="*60 + "\nAUDIT STATUS REPORT\n" + "="*60)

# 1. SYNCHRONIZED
if not community_df.empty:
    synced = community_df[community_df.apply(lambda x: (x['Summary'].lower() + x['DateTime']) in master_keys, axis=1)]
    if not synced.empty:
        print(f"\n{GREEN}[ SYNCHRONIZED / ALREADY ON ROCNY ]{RESET}")
        print_left_justified(synced.sort_values(['FromCal', 'DateTime24']), ['FromCal', 'DateTime', 'Weekday', 'Summary', 'Recurring'])

# 2. NOT ON RocNY
    missing = community_df[community_df.apply(lambda x: (x['Summary'].lower() + x['DateTime']) not in master_keys, axis=1)]
    if not missing.empty:
        print(f"\n{RED}[ NOT ON ROCNY ]{RESET}")
        print_left_justified(missing.sort_values(['FromCal', 'DateTime24']), ['FromCal', 'DateTime', 'Weekday', 'Summary', 'Recurring'])

# 3. I/O ONLY
if not master_df.empty:
    io_only = master_df[master_df.apply(lambda x: (x['Summary'].lower() + x['DateTime']) not in community_keys, axis=1)]
    if not io_only.empty:
        print(f"\n{GREEN}[ *ONLY* ON ROCNY ]{RESET}")
        print_left_justified(io_only.sort_values(['FromCal', 'DateTime24']), ['FromCal', 'DateTime', 'Weekday', 'Summary', 'Recurring'])
