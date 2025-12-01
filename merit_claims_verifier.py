"""
Prometheus Analytics - Merit Claims Verifier

Automated system to source, verify, and score "properties of merit" 
(expired BC mineral claims from public mining companies) for real-time staking.

Flow:
1. Fetch live MTO data via WFS (GeoJSON, filter expired); cache locally.
2. Filter recent expired claims (GOOD_TO_DATE < now, TERMINATION_DATE null).
3. Verify availability on MTO via Safari automation (requires credentials in env vars).
4. Confirm merit: Regex on OWNER_NAME, SEDAR+ for NI 43-101 disclosures.
5. Score geodata merit (Haversine to MinCore).
6. Output: merit_claims.csv with recommendations (recommend_stake yes/no if merit_score >50).

Prerequisites:
- Safari with Remote Automation enabled (Develop > Allow Remote Automation)
- Environment variables: MTO_USERNAME, MTO_PASSWORD (or BCEID_USERNAME, BCEID_PASSWORD)
- pip install requests beautifulsoup4 pandas numpy selenium

Ethical note: Public data; FN consultations mandatory before staking (flag in output).
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import os
import time
import re
import logging

from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ## Step 1: Fetch Live MTO Data
# Use WFS for GeoJSON (daily updates). Cache to mta_tenures.csv; load if fails.
# Adjustments: If WFS blocks, check endpoint via web_search ("BC MTO WFS 2025").
def fetch_mto_data(local_path='mta_tenures.csv'):
    base_url = "https://openmaps.gov.bc.ca/geo/pub/wfs"
    now = datetime.now().strftime('%Y-%m-%d')
    recent = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "pub:WHSE_MINERAL_TENURE.MTA_MINERAL_PLACER_COAL_TENURE_SVW",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "cql_filter": f"GOOD_TO_DATE < date '{now}' AND GOOD_TO_DATE > date '{recent}' AND TERMINATION_DATE IS NULL"
    }
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        attributes = [f['properties'] for f in data.get('features', [])]
        df = pd.DataFrame(attributes)
        df.to_csv(local_path, index=False)
        print(f"Fetched {len(df)} tenures from WFS. Cached to {local_path}. Columns: {df.columns.tolist()}")
        return df
    except Exception as e:
        print(f"WFS fetch failed: {e}. Checking local cache: {local_path}")
        if os.path.exists(local_path):
            df = pd.read_csv(local_path, low_memory=False, dtype=str)
            print(f"Loaded {len(df)} tenures from cache. Columns: {df.columns.tolist()}")
            return df
        print("No cache. Run again after fixing WFS or download CSV from https://catalogue.data.gov.bc.ca/dataset/mta-mineral-placer-and-coal-tenure-spatial-view.")
        return None

# ## Step 2: Filter Recent Expired Claims
# Filter expired claims (GOOD_TO_DATE recent, TERMINATION_DATE null).
# Debug: Check alternative column names; print sample.
# Adjustments: Update TENURE_NUMBER_ID/GOOD_TO_DATE if CSV columns differ.
def filter_expired(df, days_back=90):
    date_cols = ['ISSUE_DATE', 'GOOD_TO_DATE', 'TERMINATION_DATE', 'ENTRY_TIMESTAMP', 'UPDATE_TIMESTAMP']
    tenure_cols = ['TENURE_NUMBER_ID', 'TENURE_ID']
    owner_cols = ['OWNER_NAME', 'OWNER', 'CLIENT_NAME']
    tenure_col = next((col for col in tenure_cols if col in df.columns), None)
    owner_col = next((col for col in owner_cols if col in df.columns), None)
    if not tenure_col:
        print(f"Error: No tenure ID column. Expected: {tenure_cols}. Available: {df.columns.tolist()}")
        return None
    if not owner_col:
        print(f"Warning: No owner column. Expected: {owner_cols}.")
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    try:
        now = datetime.now()
        recent = now - timedelta(days=days_back)
        df_expired = df[(df['GOOD_TO_DATE'] < now) & (df['GOOD_TO_DATE'] > recent) & df['TERMINATION_DATE'].isnull()].copy()
        if tenure_col != 'TENURE_NUMBER_ID':
            df_expired['TENURE_NUMBER_ID'] = df_expired[tenure_col]
        if owner_col and owner_col != 'OWNER_NAME':
            df_expired['OWNER_NAME'] = df_expired[owner_col]
    except KeyError as e:
        print(f"Error: {e}. Check GOOD_TO_DATE/TERMINATION_DATE: {df.columns.tolist()}")
        return None
    if df_expired.empty:
        print(f"No expired claims found. Try days_back={days_back*2}.")
        return None
    print(f"Filtered {len(df_expired)} expired claims. Sample: {df_expired[['TENURE_NUMBER_ID', 'GOOD_TO_DATE']].head(1).to_dict()}")
    return df_expired

# ## Step 3: Verify Availability on MTO
# Safari-based Selenium login, search tenure for "expired".
# Credentials from environment variables: MTO_USERNAME, MTO_PASSWORD
# Fallback: Assume available if fails.
def verify_availability_mto(df_expired):
    """
    Verify claim availability on MTO using Safari automation.
    
    Requires environment variables:
    - MTO_USERNAME (or BCEID_USERNAME): BCeID username
    - MTO_PASSWORD (or BCEID_PASSWORD): BCeID password
    """
    # Load credentials from environment
    username = os.environ.get("MTO_USERNAME") or os.environ.get("BCEID_USERNAME")
    password = os.environ.get("MTO_PASSWORD") or os.environ.get("BCEID_PASSWORD")
    
    if not username or not password:
        logger.warning(
            "MTO credentials not found in environment. "
            "Set MTO_USERNAME and MTO_PASSWORD. Assuming availability for all claims."
        )
        df_expired['mto_status'] = 'assumed_available'
        return df_expired
    
    driver = None
    try:
        # Initialize Safari driver
        options = SafariOptions()
        driver = webdriver.Safari(options=options)
        driver.implicitly_wait(10)
        
        login_url = 'https://www.bceid.ca/clp/accountlogon.aspx?type=0&appurl=https%3A%2F%2Fwww.mtonline.gov.bc.ca%2Fmtov%2Fhome.do&servicecreds=MTOM&appname=MTO'
        driver.get(login_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'txtUserId')))
        
        # Fill login form with credentials from environment
        driver.find_element(By.NAME, 'txtUserId').send_keys(username)
        driver.find_element(By.NAME, 'txtPassword').send_keys(password)
        driver.find_element(By.NAME, 'btnSubmit').click()
        WebDriverWait(driver, 10).until(EC.url_contains('mtonline'))
        if 'error' in driver.page_source.lower():
            logger.warning("MTO login failed. Assuming availability.")
            df_expired['mto_status'] = 'assumed_available'
            return df_expired
        time.sleep(5)
    except Exception as e:
        logger.error(f"MTO login error: {e}. Assuming availability.")
        df_expired['mto_status'] = 'assumed_available'
        return df_expired
    finally:
        if driver:
            driver.quit()

    # Initialize Safari for tenure search
    options = SafariOptions()
    driver = webdriver.Safari(options=options)
    driver.implicitly_wait(10)
    try:
        mto_search_url = 'https://www.mtonline.gov.bc.ca/mtov/tenureSearch.do'
        verified = []
        for idx, row in df_expired.iterrows():
            try:
                tenure_id = row['TENURE_NUMBER_ID']
                driver.get(mto_search_url)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'tenureNumber')))
                driver.find_element(By.NAME, 'tenureNumber').send_keys(tenure_id)
                driver.find_element(By.NAME, 'searchType').send_keys('tenure')
                driver.find_element(By.CSS_SELECTOR, 'input[type="submit"]').click()
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                status_elem = soup.find('span', class_='status') or soup.find('td', string=re.compile('status', re.I))
                if not status_elem:
                    logger.debug(f"No status for {tenure_id}. HTML: {str(soup)[:500]}. Try class='tenure-status'.")
                    status = 'unknown'
                else:
                    status = status_elem.text.strip().lower()
                row['mto_status'] = 'available' if 'expired' in status or 'forfeited' in status else 'not_available'
                verified.append(row.to_dict())
                time.sleep(5)
            except Exception as e:
                logger.warning(f"Search failed for {tenure_id}: {e}. Assuming available.")
                row['mto_status'] = 'assumed_available'
                verified.append(row.to_dict())
        df_verified = pd.DataFrame(verified)
        logger.info(f"Verified {len(df_verified[df_verified['mto_status'].str.contains('available')])} available claims.")
        return df_verified
    finally:
        driver.quit()

# ## Step 4: Confirm Property of Merit
# Regex on OWNER_NAME, POST to SEDAR+ for NI 43-101 disclosures.
# Fallback: Regex if SEDAR fails.
# Debug: Print HTML snippet if selector fails.
# Adjustments: Update public_companies; inspect SEDAR for class.
def confirm_merit_sedar(df_verified):
    sedar_search_url = 'https://www.sedarplus.ca/landingpage/Search'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    public_companies = [
        r'.*\bInc\b', r'.*\bCorp\b', r'.*\bLtd\b',
        'Teck Resources', 'Newmont', 'Barrick Gold', 'Kinross Gold', 'BHP', 'Eldorado Gold'
    ]
    merit_rows = []
    for idx, row in df_verified.iterrows():
        owner = str(row.get('OWNER_NAME', ''))
        is_public = any(re.search(pattern, owner, re.IGNORECASE) for pattern in public_companies)
        row['is_public_company'] = is_public
        if is_public:
            payload = {'searchText': f"{owner} {row['TENURE_NUMBER_ID']} NI 43-101 property disclosure stock exchange"}
            try:
                response = session.post(sedar_search_url, data=payload, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.find_all('div', class_='search-result') or soup.find_all('div', class_='result-item')
                if not results:
                    print(f"No SEDAR results for {row['TENURE_NUMBER_ID']}. HTML: {str(soup)[:500]}. Try class='search-item'.")
                hits = len(results)
                is_merit = hits > 0 or is_public
                merit_score = hits * 10 - row.get('min_core_dist_km', 0)
                row['is_merit'] = is_merit
                row['merit_score'] = merit_score
                row['recommend_stake'] = 'yes' if merit_score > 50 else 'no'
                time.sleep(5)
            except Exception as e:
                print(f"SEDAR failed for {row['TENURE_NUMBER_ID']}: {e}. Using regex merit.")
                row['is_merit'] = is_public
                row['merit_score'] = 10 if is_public else 0
                row['recommend_stake'] = 'yes' if row['merit_score'] > 50 else 'no'
        else:
            row['is_merit'] = False
            row['merit_score'] = 0
            row['recommend_stake'] = 'no'
        merit_rows.append(row.to_dict())
    df_merit = pd.DataFrame(merit_rows)
    print(f"Confirmed {len(df_merit[df_merit['is_merit']])} properties of merit.")
    return df_merit

# ## Step 5: Score Geodata Merit
# Haversine to MinCore; geopandas for SHAPE WKT.
# Fallback: Skip if missing.
# Adjustments: Install geopandas; ensure MinCore path.
def score_geodata(df):
    core_path = "MineralData/Core_Locations/MinCore_Locations_HSA__WebM.csv"
    if not os.path.exists(core_path):
        print(f"MinCore missing at {core_path}; skip.")
        return df
    try:
        df_core = pd.read_csv(core_path)
        if 'LATITUDE' not in df_core.columns or 'LONGITUDE' not in df_core.columns:
            print("MinCore missing LATITUDE/LONGITUDE; skip.")
            return df
    except Exception as e:
        print(f"MinCore load failed: {e}; skip.")
        return df
    try:
        import geopandas as gpd
        if 'SHAPE' in df.columns:
            gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df['SHAPE'], on_invalid='ignore'))
            df['centroid_lat'] = gdf.geometry.centroid.y
            df['centroid_lon'] = gdf.geometry.centroid.x
        elif 'CENTROID_LATITUDE' in df.columns and 'CENTROID_LONGITUDE' in df.columns:
            df['centroid_lat'] = df['CENTROID_LATITUDE']
            df['centroid_lon'] = df['CENTROID_LONGITUDE']
        else:
            print("No SHAPE or CENTROID_LATITUDE/LONGITUDE; skip.")
            return df
    except ImportError:
        print("Geopandas not installed (pip install geopandas); skip.")
        return df
    except Exception as e:
        print(f"Geo processing failed: {e}; skip.")
        return df
    valid = df.dropna(subset=['centroid_lat', 'centroid_lon'])
    if valid.empty:
        print("No valid centroids; skip.")
        return df
    lat1 = valid['centroid_lat'].values
    lon1 = valid['centroid_lon'].values
    lat2 = df_core['LATITUDE'].values
    lon2 = df_core['LONGITUDE'].values
    dists = haversine(lat1, lon1, lat2, lon2)
    min_dists = np.min(dists, axis=1)
    df.loc[valid.index, 'min_core_dist_km'] = min_dists
    print(f"Added min_core_dist_km to {len(valid)} claims.")
    return df

# ## Haversine Function
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    dlat = np.radians(lat2 - lat1_rad[:, np.newaxis])
    dlon = np.radians(lon2 - lon1_rad[:, np.newaxis])
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad[:, np.newaxis]) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# ## Main Execution
# Run once; cron for daily (0 0 * * * python merit_claims_verifier_auto.py).
if __name__ == "__main__":
    try:
        df = fetch_mto_data()
        if df is None:
            print("Exiting: No tenure data.")
            exit(1)
        df_expired = filter_expired(df)
        if df_expired is None:
            print("Exiting: No expired claims.")
            exit(1)
        df_verified = verify_availability_mto(df_expired)
        df_merit = confirm_merit_sedar(df_verified)
        df_scored = score_geodata(df_merit)
        df_scored.to_csv('merit_claims.csv', index=False)
        print("Complete. Check merit_claims.csv for verified properties of merit.")
        print("Sample output:")
        print(df_scored[['TENURE_NUMBER_ID', 'OWNER_NAME', 'is_merit', 'merit_score', 'recommend_stake', 'mto_status']].head())
        print("FN consult flag: Always consult First Nations before staking any claim.")
    except Exception as e:
        print(f"Global error: {e}. Check internet, credentials, or MinCore path.")

