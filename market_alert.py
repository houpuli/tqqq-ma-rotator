import yfinance as yf
import smtplib
import os
from email.mime.text import MIMEText
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

TICKERS = ["^DJI", "^IXIC"]

def get_market_status(ticker):
    # Fetch 2 years to ensure valid MA210
    data = yf.download(ticker, period="2y", progress=False)
    
    # Calculate Moving Averages
    data['MA2'] = data['Close'].rolling(window=2).mean()
    data['MA210'] = data['Close'].rolling(window=210).mean()
    
    # We need the last two days to detect a "Cross"
    # iloc[-1] is Today, iloc[-2] is Yesterday
    today = data.iloc[-1]
    yesterday = data.iloc[-2]
    
    # define states
    today_below = today['MA2'] < today['MA210']
    yesterday_below = yesterday['MA2'] < yesterday['MA210']
    
    status = "Unknown"
    cross_event = "None"
    
    # Determine Status
    if today_below:
        status = "BELOW"
    else:
        status = "ABOVE"

    # Detect Crossover
    if not yesterday_below and today_below:
        cross_event = "JUST CROSSED BELOW (Bearish Alert!)"
    elif yesterday_below and not today_below:
        cross_event = "JUST CROSSED ABOVE (Bullish Alert!)"
        
    return {
        "ticker": ticker,
        "date": today.name.strftime('%Y-%m-%d'),
        "price": today['Close'],
        "MA2": today['MA2'],
        "MA210": today['MA210'],
        "status": status,
        "cross_event": cross_event
    }

def send_daily_email(reports):
    if not reports:
        return

    # Create Subject Line based on urgency
    # If ANY stock has a cross event, mark the subject as URGENT
    urgent_flags = [r for r in reports if r['cross_event'] != "None"]
    
    if urgent_flags:
        subject = f"⚠️ MARKET ALERT: Crossover Detected ({datetime.now().strftime('%Y-%m-%d')})"
    else:
        subject = f"Market Daily Update: {datetime.now().strftime('%Y-%m-%d')}"

    # Build Email Body
    body = "Daily Market Moving Average Report (MA2 vs MA210)\n"
    body += "=" * 40 + "\n\n"
    
    for r in reports:
        body += f"Symbol: {r['ticker']}\n"
        body += f"Status: MA2 is {r['status']} MA210\n"
        
        if r['cross_event'] != "None":
            body += f"EVENT:  *** {r['cross_event']} ***\n"
        else:
            body += f"Event:  No change in trend.\n"
            
        body += f"Price:  {r['price']:.2f}\n"
        body += f"MA2:    {r['MA2']:.2f}\n"
        body += f"MA210:  {r['MA210']:.2f}\n"
        body += "-" * 30 + "\n\n"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Daily email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("Error: Missing environment variables.")
        return

    reports = []
    print(f"Running daily check at {datetime.now()}...")
    
    for ticker in TICKERS:
        try:
            report = get_market_status(ticker)
            reports.append(report)
            print(f"Processed {ticker}: {report['status']}")
        except Exception as e:
            print(f"Error checking {ticker}: {e}")

    # Always send email now, regardless of alerts
    if reports:
        send_daily_email(reports)

if __name__ == "__main__":
    main()
