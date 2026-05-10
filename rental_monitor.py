"""
Magis Real Estate Rental Monitor
=================================
Monitors https://magisrealestate.com/for-rent for Eindhoven listings.
Sends email notifications for new availabilities, with priority for Boschdijk.

Works both locally (with config.py) and on GitHub Actions (with secrets).
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
import re
import os

# Load email config from environment variables (GitHub Actions) or config.py (local)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

# Fall back to config.py for local development
if not SENDER_EMAIL:
    try:
        from config import SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL
    except ImportError:
        print("ERROR: No email config found!")
        print("Set environment variables or create config.py")
        exit(1)

# Constants
URL = "https://magisrealestate.com/for-rent"
STATE_FILE = Path(__file__).parent / "seen_listings.json"
CHECK_INTERVAL = 120  # 2 minutes in seconds
GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def load_seen_listings():
    """Load previously seen listings from state file."""
    if os.environ.get("CLEAR_CACHE") == "true":
        print(f"[{datetime.now()}] Cache clear requested via environment variable.")
        return set()
        
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_listings(seen):
    """Save seen listings to state file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)


def fetch_listings():
    """Fetch and parse rental listings from Magis Real Estate."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error fetching page: {e}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    listings = []
    
    # Find all listing cards - they are links to individual properties
    # Looking for links that contain "/for-rent/" in their href
    for link in soup.find_all("a", href=re.compile(r"/for-rent/[^/]+/")):
        href = link.get("href", "")
        text = link.get_text(separator=" ", strip=True)
        
        # Skip if too short or navigation links
        if len(text) < 20 or "filter" in text.lower():
            continue
        
        # Extract details from the listing text
        listing = {
            "id": href,
            "url": f"https://magisrealestate.com{href}" if href.startswith("/") else href,
            "text": text,
            "location": "",
            "title": ""
        }
        
        # Try to extract location (usually contains city name)
        location_match = re.search(r"(Eindhoven|Tilburg|Den Bosch|Amersfoort|Rijswijk)[,\s]+([^\n€]+)", text, re.IGNORECASE)
        if location_match:
            listing["location"] = f"{location_match.group(1)}, {location_match.group(2).strip()}"
        
        # Try to extract title (usually the building/unit name)
        title_match = re.search(r"(The \w+|Mr\. \w+|Novum|[A-Z][a-z]+ [A-Z][a-z]+)\s*[•·]\s*([^\n]+)", text)
        if title_match:
            listing["title"] = f"{title_match.group(1)} • {title_match.group(2).strip()}"
        
        listings.append(listing)
    
    # Remove duplicates by ID
    seen_ids = set()
    unique_listings = []
    for listing in listings:
        if listing["id"] not in seen_ids:
            seen_ids.add(listing["id"])
            unique_listings.append(listing)
    
    return unique_listings


def filter_eindhoven(listings):
    """Filter listings to only include Eindhoven properties."""
    eindhoven_listings = []
    for listing in listings:
        text_lower = listing["text"].lower()
        location_lower = listing["location"].lower()
        
        if "eindhoven" in text_lower or "eindhoven" in location_lower:
            eindhoven_listings.append(listing)
    
    return eindhoven_listings


def is_boschdijk(listing):
    """Check if listing is in the Boschdijk area (priority location)."""
    text_lower = listing["text"].lower()
    location_lower = listing["location"].lower()
    
    # Check various spellings
    priority_terms = ["boschdijk", "bosschijk", "bosschdijk", "bosch dijk"]
    
    for term in priority_terms:
        if term in text_lower or term in location_lower:
            return True
    return False


def send_email(subject, body, is_priority=False):
    """Send email notification."""
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = f"{'[PRIORITY] ' if is_priority else ''}New Rental: {subject}"
        
        # Add HTML body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: {'#e74c3c' if is_priority else '#3498db'};">
                {'BOSCHDIJK ALERT!' if is_priority else 'New Rental Available'}
            </h2>
            {body}
            <hr style="margin-top: 20px;">
            <p style="color: #888; font-size: 12px;">
                Sent by Magis Rental Monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, "html"))
        
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        print(f"[{datetime.now()}] Email sent: {subject}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] Error sending email: {e}")
        return False


def format_listing_html(listing):
    """Format a single listing as HTML for email."""
    return f"""
    <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid {'#e74c3c' if is_boschdijk(listing) else '#3498db'};">
        <h3 style="margin: 0 0 10px 0;">
            <a href="{listing['url']}" style="color: #2c3e50; text-decoration: none;">
                {listing['title'] or 'New Listing'}
            </a>
        </h3>
        <p style="margin: 5px 0; color: #555;">
            Location: {listing['location'] or 'Location in details'}
        </p>
        <a href="{listing['url']}" style="display: inline-block; background: #3498db; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-top: 10px;">
            View Listing →
        </a>
    </div>
    """


def check_for_new_listings():
    """Main function to check for new Eindhoven listings."""
    print(f"[{datetime.now()}] Checking for new listings...")
    
    # Load previously seen listings
    seen = load_seen_listings()
    
    # Fetch current listings
    all_listings = fetch_listings()
    print(f"[{datetime.now()}] Found {len(all_listings)} total listings")
    
    # Filter for Eindhoven
    eindhoven_listings = filter_eindhoven(all_listings)
    print(f"[{datetime.now()}] {len(eindhoven_listings)} in Eindhoven")
    
    # Find new listings
    new_listings = [l for l in eindhoven_listings if l["id"] not in seen]
    
    if new_listings:
        print(f"[{datetime.now()}] NEW: {len(new_listings)} NEW listings found!")
        
        # Separate priority (Boschdijk) and regular listings
        priority_listings = [l for l in new_listings if is_boschdijk(l)]
        regular_listings = [l for l in new_listings if not is_boschdijk(l)]
        
        # Send immediate email for Boschdijk listings
        if priority_listings:
            body = "<p><strong>BOSCHDIJK listing found!</strong></p>"
            body += "".join(format_listing_html(l) for l in priority_listings)
            send_email(
                f"BOSCHDIJK Rental Available! ({len(priority_listings)} listing(s))",
                body,
                is_priority=True
            )
        
        # Send regular email for other Eindhoven listings
        if regular_listings:
            body = "<p>New Eindhoven rentals on Magis Real Estate:</p>"
            body += "".join(format_listing_html(l) for l in regular_listings)
            send_email(
                f"New Eindhoven Rental(s) Available ({len(regular_listings)})",
                body,
                is_priority=False
            )
        
        # Update seen listings
        for listing in new_listings:
            seen.add(listing["id"])
        save_seen_listings(seen)
    else:
        print(f"[{datetime.now()}] No new Eindhoven listings")
    
    return new_listings


def main():
    """Main entry point - runs once on GitHub Actions, loops locally."""
    print("=" * 50)
    print("[MONITOR] Magis Real Estate Rental Monitor")
    print("=" * 50)
    print(f"Monitoring: {URL}")
    print(f"Filter: Eindhoven (priority: Boschdijk)")
    print(f"Notifications: {RECIPIENT_EMAIL}")
    print(f"Mode: {'GitHub Actions' if GITHUB_ACTIONS else 'Local'}")
    print("=" * 50)
    print()
    
    if GITHUB_ACTIONS:
        # On GitHub Actions: run once and exit (Actions handles scheduling)
        try:
            check_for_new_listings()
        except Exception as e:
            print(f"[{datetime.now()}] Error: {e}")
            exit(1)
    else:
        # Locally: run in a loop
        while True:
            try:
                check_for_new_listings()
            except Exception as e:
                print(f"[{datetime.now()}] Error: {e}")
            
            print(f"[{datetime.now()}] Next check in {CHECK_INTERVAL // 60} minutes...")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
