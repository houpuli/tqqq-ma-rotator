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
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")
URGENT_EMAIL = os.environ.get("URGENT_EMAIL") 

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
    
    # SYMMETRICAL LOGIC: Explicitly track both Buy and Sell signals
    buy_signal = yesterday_below and not today_below
    sell_signal = not yesterday_below and today_below
    
    status = "BELOW" if today_below else "ABOVE"
    
    if sell_signal:
        cross_event = "JUST CROSSED BELOW (🔴 SELL SIGNAL!)"
    elif buy_signal:
        cross_event = "JUST CROSSED ABOVE (🟢 BUY SIGNAL!)"
    else:
        cross_event = "None"
        
    return {
        "ticker": ticker,
        "date": today.name.strftime('%Y-%m-%d'),
        "price": float(today['Close']),
        "MA2": float(today['MA2']),
        "MA210": float(today['MA210']),
        "status": status,
        "cross_event": cross_event,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "is_below": today_below
    }

def send_daily_email(reports):
    if not reports:
        return

    # 1. Determine trigger states
    urgent_buy = any(r['buy_signal'] for r in reports)
    urgent_sell = any(r['sell_signal'] for r in reports)
    currently_below = any(r['is_below'] for r in reports)
    
    # Action needed if there's a new signal OR the market is currently below MA210
    action_needed = urgent_buy or urgent_sell or currently_below
    
    # 2. Build Subject Line 
    date_str = datetime.now().strftime('%Y-%m-%d')
    if urgent_buy:
        subject = f"🟢 [BUY SIGNAL] Market Alert: MA2 Crossed Above MA210 ({date_str})"
    elif urgent_sell:
        subject = f"🔴 [SELL SIGNAL] Market Alert: MA2 Crossed Below MA210 ({date_str})"
    elif currently_below:
        subject = f"⚠️ [ACTION NEEDED] Market Alert: MA2 is Below MA210 ({date_str})"
    else:
        subject = f"Market Daily Update: {date_str}"

    # 3. Determine Recipients
    recipients = [EMAIL_RECEIVER]
    if action_needed and URGENT_EMAIL:
        recipients.append(URGENT_EMAIL)

    # 4. Build HTML Body
    html_body = f"""
    <html>
    <body>
        <h2>Daily Market Report ({date_str})</h2>
    """
    
    # Add Symmetrical Header Warnings
    if urgent_buy:
        html_body += """
        <h3 style="color: #009900; font-size: 20px;">
            🟢 [BUY SIGNAL] MA2 HAS CROSSED ABOVE MA210 - ADVISE TO PURCHASE
        </h3>
        """
    if urgent_sell:
        html_body += """
        <h3 style="color: red; font-size: 20px;">
            🔴 [SELL SIGNAL] MA2 HAS CROSSED BELOW MA210 - ADVISE TO SELL
        </h3>
        """
    elif currently_below and not urgent_sell:
        # Warning for days where it is below, but didn't *just* cross
        html_body += """
        <h3 style="color: darkorange; font-size: 20px;">
            ⚠️ [WARNING] MA2 IS CURRENTLY BELOW MA210
        </h3>
        """

    html_body += "<table border='1' cellpadding='10' cellspacing='0' style='border-collapse: collapse;'>"
    html_body += "<tr><th>Symbol</th><th>Status</th><th>Price</th><th>MA2</th><th>MA210</th><th>Event</th></tr>"

    for r in reports:
        # Style logic: Highlight the specific rows with the active signals
        if r['buy_signal']:
            status_style = "color: #009900; font-weight: bold; font-size: 18px;"
            row_bg = "#e6ffe6" # Light green
        elif r['sell_signal']:
            status_style = "color: red; font-weight: bold; font-size: 18px;"
            row_bg = "#ffe6e6" # Light red
        elif r['status'] == "BELOW":
            status_style = "color: red; font-weight: bold; font-size: 18px;"
            row_bg = "#fff5f5" # Very faint red for ongoing below status
        else:
            status_style = "color: green; font-weight: bold;"
            row_bg = "#ffffff"

        html_body += f"<tr style='background-color: {row_bg};'>"
        html_body += f"<td><b>{r['ticker']}</b></td>"
        html_body += f"<td style='{status_style}'>{r['status']}</td>"
        html_body += f"<td>{r['price']:.2f}</td>"
        html_body += f"<td>{r['MA2']:.2f}</td>"
        html_body += f"<td>{r['MA210']:.2f}</td>"
        html_body += f"<td><b>{r['cross_event']}</b></td>"
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