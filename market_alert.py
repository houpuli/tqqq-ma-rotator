import yfinance as yf
import smtplib
import os
import pandas as pd  # Make sure to import pandas
from email.mime.text import MIMEText
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

TICKERS = ["^DJI", "^IXIC"]

def get_market_status(ticker):
    # FIX: Use Ticker().history() instead of download()
    # This avoids the "MultiIndex" formatting issue that caused the error
    stock = yf.Ticker(ticker)
    data = stock.history(period="2y")
    
    if data.empty:
        raise ValueError(f"No data found for {ticker}")
    
    # Calculate Moving Averages
    data['MA2'] = data['Close'].rolling(window=2).mean()
    data['MA210'] = data['Close'].rolling(window=210).mean()
    
    # We need the last two days to detect a "Cross"
    today = data.iloc[-1]
    yesterday = data.iloc[-2]
    
    # helper to ensure we get a simple True/False (scalar), not a list
    def is_below(row):
        return float(row['MA2']) < float(row['MA210'])

    today_below = is_below(today)
    yesterday_below = is_below(yesterday)
    
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
        "price": float(today['Close']),
        "MA2": float(today['MA2']),
        "MA210": float(today['MA210']),
        "status": status,
        "cross_event": cross_event
    }

def send_daily_email(reports):
    if not reports:
        return

    # Check for urgent events
    urgent_flags = [r for r in reports if r['cross_event'] != "None"]
    
    if urgent_flags:
        subject = f"⚠️ MARKET ALERT: Crossover Detected ({datetime.now().strftime('%Y-%m-%d')})"
    else:
        subject = f"Market Daily Update: {datetime.now().strftime('%Y-%m-%d')}"

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
    print(f"Checking markets at {datetime.now()}...")
    
    for ticker in TICKERS:
        try:
            report = get_market_status(ticker)
            reports.append(report)
            print(f"Processed {ticker}: {report['status']}")
        except Exception as e:
            print(f"Error checking {ticker}: {e}")

    if reports:
        send_daily_email(reports)

if __name__ == "__main__":
    main()
