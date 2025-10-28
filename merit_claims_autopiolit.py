# merit_claims_autopilot.py - Zesty Edition
# Sniff JSON, cross TSX, stake fast. No fluff.

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import time
import random
import json

# Load TSX hot list once
tsx_set = set()
with open("tsx_listings.csv", "r") as f:  # column 0 = claim_id
    for line in f:
        tsx_set.add(line.strip().split(","))

options = Options()
options.add_argument("--headless")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
driver = webdriver.Chrome(options=options)

def get_expired_claims():
    driver.get("https://minfile.gov.bc.ca/MapViewer/IMF2/MapViewer.aspx?showExpired=true")
    time.sleep(3)  # let JS run
    for request in driver.requests:
        if "claims" in request.url and "json" in request.response.headers.get("Content-Type", ""):
            data = request.response.body.decode("utf-8")
            claims = json.loads(data)
            return     return 
def check_merit(claim_id):
    return claim_id in tsx_set

while True:
    batch = get_expired_claims()
    for claim in batch:
        if check_merit(claim):
            print(f"🚀 STAKE NOW: {claim} - merit confirmed")
            # stake_here(claim)  # plug in your Selenium stake function
    time.sleep(random.uniform(25, 35))  # chill like a human