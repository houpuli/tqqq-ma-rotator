import yfinance as yf
import smtplib
import os
from email.mime.text import MIMEText
from datetime import datetime

# --- CONFIGURATION ---
# These are pulled from GitHub Secrets
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
# EMAIL_RECEIVER = "your_email@gmail.com"  # Replace with your actual email
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

# Tickers: Dow Jones (^DJI) and Nasdaq (^IXIC)
TICKERS = ["^DJI", "^IXIC"]

def get_ma_data(ticker):
    # Fetch 2 years to ensure we have enough data for a 210-day moving average
    data = yf.download(ticker, period="2y", progress=False)
    
    # Calculate Moving Averages
    data['MA2'] = data['Close'].rolling(window=2).mean()
    data['MA3'] = data['Close'].rolling(window=3).mean()
    data['MA210'] = data['Close'].rolling(window=210).mean() # Updated to 210
    
    latest = data.iloc[-1]
    
    return {
        "ticker": ticker,
        "price": latest['Close'],
        "MA2": latest['MA2'],
        "MA3": latest['MA3'],
        "MA210": latest['MA210'],
        "date": latest.name.strftime('%Y-%m-%d')
    }

def send_alert(alerts):
    if not alerts:
        return

    subject = f"MARKET ALERT: MA2 below MA210 Detected"
    body = "The following indices have crossed the threshold:\n\n"
    
    for alert in alerts:
        body += f"--- {alert['ticker']} ---\n"
        body += f"Date: {alert['date']}\n"
        body += f"Price: {alert['price']:.2f}\n"
        body += f"MA2:   {alert['MA2']:.2f}\n"
        body += f"MA3:   {alert['MA3']:.2f}\n"
        body += f"MA210: {alert['MA210']:.2f}\n\n"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Error: Email credentials not found in environment variables.")
        return

    alerts = []
    print(f"Checking markets at {datetime.now()}...")
    
    for ticker in TICKERS:
        try:
            data = get_ma_data(ticker)
            
            # Logic: Send alarm if MA2 is below MA210
            if data['MA2'] < data['MA210']:
                print(f"[ALERT] {ticker}: MA2 ({data['MA2']:.2f}) < MA210 ({data['MA210']:.2f})")
                alerts.append(data)
            else:
                print(f"[OK] {ticker}: MA2 is above MA210")
                
        except Exception as e:
            print(f"Error checking {ticker}: {e}")

    if alerts:
        send_alert(alerts)

if __name__ == "__main__":
    main()
