import yfinance as yf
import smtplib
import os
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")  # Standard receiver
URGENT_EMAIL = os.environ.get("URGENT_EMAIL")      # <--- Renamed from RECEIVER_2

TICKERS = ["^DJI", "^IXIC"]

def get_market_status(ticker):
    stock = yf.Ticker(ticker)
    data = stock.history(period="2y")
    
    if data.empty:
        raise ValueError(f"No data found for {ticker}")
    
    # Calculate Moving Averages
    data['MA2'] = data['Close'].rolling(window=2).mean()
    data['MA210'] = data['Close'].rolling(window=210).mean()
    
    today = data.iloc[-1]
    yesterday = data.iloc[-2]
    
    def is_below(row):
        return float(row['MA2']) < float(row['MA210'])

    today_below = is_below(today)
    yesterday_below = is_below(yesterday)
    
    status = "Unknown"
    cross_event = "None"
    
    if today_below:
        status = "BELOW"
    else:
        status = "ABOVE"

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
        "cross_event": cross_event,
        "is_bearish": today_below
    }

def send_daily_email(reports):
    if not reports:
        return

    # 1. Determine "Action Needed"
    action_needed = any(r['is_bearish'] for r in reports)
    
    # 2. Build Subject
    date_str = datetime.now().strftime('%Y-%m-%d')
    if action_needed:
        subject = f"[ACTION NEEDED] Market Alert: MA2 Below MA210 ({date_str})"
    else:
        subject = f"Market Daily Update: {date_str}"

    # 3. Determine Recipients
    recipients = [EMAIL_RECEIVER]
    
    # Only add the Urgent Email if action is needed AND the variable is set
    if action_needed and URGENT_EMAIL:
        recipients.append(URGENT_EMAIL)

    # 4. Build HTML Body
    html_body = f"""
    <html>
    <body>
        <h2>Daily Market Report ({date_str})</h2>
    """
    
    if action_needed:
        html_body += """
        <h3 style="color: red; font-size: 20px;">
            ⚠️ [ACTION NEEDED] BEARISH SIGNAL DETECTED
        </h3>
        """

    html_body += "<table border='1' cellpadding='10' cellspacing='0' style='border-collapse: collapse;'>"
    html_body += "<tr><th>Symbol</th><th>Status</th><th>Price</th><th>MA2</th><th>MA210</th><th>Event</th></tr>"

    for r in reports:
        if r['status'] == "BELOW":
            status_style = "color: red; font-weight: bold; font-size: 18px;"
            row_bg = "#ffe6e6"
        else:
            status_style = "color: green; font-weight: bold;"
            row_bg = "#ffffff"

        html_body += f"<tr style='background-color: {row_bg};'>"
        html_body += f"<td><b>{r['ticker']}</b></td>"
        html_body += f"<td style='{status_style}'>{r['status']}</td>"
        html_body += f"<td>{r['price']:.2f}</td>"
        html_body += f"<td>{r['MA2']:.2f}</td>"
        html_body += f"<td>{r['MA210']:.2f}</td>"
        html_body += f"<td>{r['cross_event']}</td>"
        html_body += "</tr>"

    html_body += """
        </table>
        <p><i>Check chart manually to confirm.</i></p>
    </body>
    </html>
    """

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            
            for receiver in recipients:
                msg = MIMEMultipart()
                msg['From'] = EMAIL_SENDER
                msg['To'] = receiver
                msg['Subject'] = subject
                msg.attach(MIMEText(html_body, 'html'))
                
                server.send_message(msg)
                print(f"Email sent to {receiver}")
                
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
