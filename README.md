# Prometheus Analytics 🔥

## 🚀 What It Is
Prometheus is a real-time, AI-powered claim sniper. It watches BC's expired mineral claims like a hawk, cross-references them against TSX listings, and auto-bids on the ones with merit—before the human scouts even log in.
Think of it as a trading bot, but for rocks. Except the rocks can flip for 100x your stake cost.

## 💎 Why It's Lucrative
- Stake cost: $1.75/ha in BC.
- Flip price: $10k-$100k/ha during booms.
- Your edge: You're 30 seconds faster than the guy earning $100/hr to babysit a browser.
- One flip pays for 6 months of coffee.

## 🤖 What's Cutting Edge (And Never Been Done)
- **Live WFS data**: Fetch expired claims directly from BC's open data portal.
- **TSX merit filter**: Claims only get listed if they've got real value. We use that as a cheat code—no geology degree needed.
- **Safari autopilot**: Native macOS Safari automation with intelligent page understanding. Acts human, sleeps random, and avoids detection.
- **SEDAR+ verification**: Cross-reference with NI 43-101 disclosures for merit confirmation.

## 🛠️ How It Works
1. Fetch expired claims via WFS (BC Open Maps).
2. Filter for recently expired claims with public company owners.
3. Verify availability on MTO via Safari automation.
4. Cross-reference with SEDAR+ for merit scoring.
5. Stake instantly if it's hot.
6. Profit.

## 📄 Requirements
- macOS with Safari (Remote Automation enabled)
- Python 3.8+
- Dependencies: `pip install selenium requests beautifulsoup4 pandas numpy`

### Enable Safari Automation
1. Safari > Preferences > Advanced > Show Develop menu in menu bar
2. Develop > Allow Remote Automation

### Environment Variables
Set your BCeID credentials (never commit these!):
```bash
export MTO_USERNAME='your_bceid_username'
export MTO_PASSWORD='your_bceid_password'
```

## 📁 Project Structure
- `safari_automation.py`: Core Safari Selenium automation with intelligent page understanding
- `merit_claims_verifier.py`: Main workflow - fetch, filter, verify, score claims

## ⚠️ Legal Note
This is for educational use. Don't blame me if you become a millionaire.

## 🐉 Future
- Add ML merit scoring (proximity to Golden Triangle, soil assays).
- Auto-sell via MTO API.
- TSX cross-reference via API (instead of web scraping).
- Go full daemon: run on a $5 VPS, wake up to cash.

## 🐦‍🔥 Steal fire back from the gods.
