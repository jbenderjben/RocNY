import streamlit as st
import pandas as pd
import re
import httpx
from icalevents.icalevents import parse_events
from datetime import datetime, timedelta, timezone

# --- PAGE CONFIG ---
st.set_page_config(page_title="Roc Protest Calendar Audit", layout="wide")

# --- UTILS ---
def sanitize_text(text):
    """Clean descriptions of HTML, newlines, and carriage returns."""
    if not text or text == "N/A":
        return "N/A"
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
    text = text.replace('\r', ' ').replace('\n', ' ')
    return ' '.join(text.split())

def fetch_calendar(name, url):
    try:
        response = requests.get(url, impersonate="chrome110", timeout=30)
        response.raise_for_status()
        content = response.text

        if 'BEGIN:VCALENDAR' not in content.upper():
            return []

        start = datetime.now(timezone.utc)
        end = start + timedelta(days=30)
        evs = parse_events(content, start=start, end=end)
        
        data = []
        for ev in evs:
            local_start = ev.start.astimezone()
            data.append({
                'FromCal': name,
                'Summary': sanitize_text(ev.summary),
                'DateTime': local_start.strftime('%Y-%m-%d %I:%M %p'),
                'DateTime24': local_start,
                'Weekday': local_start.strftime('%A'),
                'Location': sanitize_text(ev.location),
                'Description': sanitize_text(ev.description),
                'Recurring': bool(ev.recurring),
                'UID': str(ev.uid) if hasattr(ev, 'uid') else "N/A"
            })
        return data
    except Exception as e:
        st.error(f"Failed to fetch {name}: {e}")
        return []

# --- CONFIGURATION ---
MASTER_URL = "https://calendar.google.com/calendar/ical/eisn9fqjjq1it4hjmd2f2ril4g66hb61%40import.calendar.google.com/public/basic.ics"
COMMUNITY_SOURCES = {
    "GVI": "https://calendar.google.com/calendar/ical/gjpdrjkt0hsf4j7v0mgrq8lfsjmf2vjb%40import.calendar.google.com/public/basic.ics",
    "IndiWMC": "https://calendar.google.com/calendar/ical/v63g68dgvie9csadovgiaq4v4q4jds96%40import.calendar.google.com/public/basic.ics",
    "Gritroc": "https://calendar.google.com/calendar/ical/grit.roc%40gmail.com/public/basic.ics",
}

# --- UI HEADER ---
st.title("📅 Rochester Protest Calendar Audit")
st.markdown("Comparing the **Master RocNY Calendar** against community sources for the next 30 days.")

if st.button("Run Audit Sync"):
    with st.status("Fetching calendar data...", expanded=True) as status:
        st.write("Syncing Master Calendar...")
        master_events = fetch_calendar("RocNY", MASTER_URL)
        master_df = pd.DataFrame(master_events)

        all_community = []
        for name, url in COMMUNITY_SOURCES.items():
            st.write(f"Syncing {name}...")
            all_community.extend(fetch_calendar(name, url))
        community_df = pd.DataFrame(all_community)
        
        status.update(label="Sync Complete!", state="complete", expanded=False)

    if master_df.empty and community_df.empty:
        st.error("Critical Error: No data retrieved from any source.")
    else:
        # Create Fingerprints for comparison
        master_df['fingerprint'] = master_df['Summary'].str.lower() + master_df['DateTime']
        community_df['fingerprint'] = community_df['Summary'].str.lower() + community_df['DateTime']
        
        master_keys = set(master_df['fingerprint'])
        community_keys = set(community_df['fingerprint'])

        # --- TABS FOR RESULTS ---
        tab1, tab2, tab3 = st.tabs([
            "❌ Missing from RocNY", 
            "✅ Successfully Synced", 
            "🔍 Only on RocNY"
        ])

        with tab1:
            st.subheader("Events on Community Calendars NOT on RocNY")
            missing = community_df[~community_df['fingerprint'].isin(master_keys)]
            if not missing.empty:
                st.warning(f"Found {len(missing)} items to add.")
                st.dataframe(missing.sort_values('DateTime24')[['FromCal', 'DateTime', 'Weekday', 'Summary', 'Location']], use_container_width=True)
                
                # Download Button
                csv = missing.to_csv(index=False).encode('utf-8')
                st.download_button("Download Missing Events CSV", csv, "missing_events.csv", "text/csv")
            else:
                st.success("Everything is up to date!")

        with tab2:
            st.subheader("Events already on RocNY")
            synced = community_df[community_df['fingerprint'].isin(master_keys)]
            if not synced.empty:
                st.dataframe(synced.sort_values('DateTime24')[['FromCal', 'DateTime', 'Weekday', 'Summary']], use_container_width=True)

        with tab3:
            st.subheader("Manual Entries (Only on RocNY)")
            io_only = master_df[~master_df['fingerprint'].isin(community_keys)]
            if not io_only.empty:
                st.info("These events were added manually to the Master calendar or came from other sources.")
                st.dataframe(io_only.sort_values('DateTime24')[['DateTime', 'Weekday', 'Summary', 'Location']], use_container_width=True)

else:
    st.info("Click the button above to begin the audit.")
