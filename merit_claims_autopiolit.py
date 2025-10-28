# merit_claims_autopilot.py - Bulletproof Edition
# Sniff JSON, cross TSX, stake fast. With error handling.

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import time
import random
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load TSX hot list once
try:
    tsx_set = set()
    with open("tsx_listings.csv", "r") as f:
        for line in f:
            tsx_set.add(line.strip().split(","))
    logger.info(f"Loaded {len(tsx_set)} TSX claim IDs")
except FileNotFoundError:
    logger.error("tsx_listings.csv not found. Exiting.")
    exit(1)
except Exception as e:
    logger.error(f"Error loading TSX data: {e}")
    exit(1)

options = Options()
options.add_argument("--headless")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
driver = None

try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    logger.error(f"Failed to start Chrome: {e}")
    exit(1)

def get_expired_claims():
    try:
        driver.get("https://minfile.gov.bc.ca/MapViewer/IMF2/MapViewer.aspx?showExpired=true")
        time.sleep(3)
        for request in driver.requests:
            if "claims" in request.url and "application/json" in request.response.headers.get("Content-Type", ""):
                data = request.response.body.decode("utf-8")
                claims = json.loads(data)
                expired =                 logger.info(f"Found {len(expired)} expired claims")
                return expired
        logger.warning("No claims JSON found in network requests")
        return     except Exception as e:
        logger.error(f"Error fetching claims: {e}")
        return 
def check_merit(claim_id):
    return claim_id in tsx_set

try:
    while True:
        batch = get_expired_claims()
        for claim in batch:
            if check_merit(claim):
                logger.info(f"🚀 STAKE NOW: {claim} - merit confirmed")
                # stake_here(claim)
        time.sleep(random.uniform(25, 35))
except KeyboardInterrupt:
    logger.info("Script stopped by user")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
finally:
    if driver:
        driver.quit()
        logger.info("Driver closed")