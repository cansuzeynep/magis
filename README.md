# Magis Rental Monitor (v1.0.1)

Monitors [magisrealestate.com/for-rent](https://magisrealestate.com/for-rent) for Eindhoven rentals and sends email notifications. Priority alerts for Boschdijk listings!

## Setup on GitHub

1. **Push this repo to GitHub**

2. **Add secrets** (Settings → Secrets → Actions):
   - `SENDER_EMAIL` - Your Gmail address
   - `SENDER_PASSWORD` - Gmail App Password ([create one here](https://myaccount.google.com/apppasswords))
   - `RECIPIENT_EMAIL` - Where to receive notifications

3. **Enable Actions** - Go to Actions tab and enable workflows

The monitor will run every 5 minutes automatically!

## Local Development

1. Create `config.py`:
   ```python
   SENDER_EMAIL = "your-gmail@gmail.com"
   SENDER_PASSWORD = "xxxx xxxx xxxx xxxx"
   RECIPIENT_EMAIL = "nonecansu@gmail.com"
   ```

2. Run: `python rental_monitor.py`
