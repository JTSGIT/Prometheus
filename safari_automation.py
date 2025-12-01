"""
Prometheus Analytics - Safari Selenium Automation Module

Provides Safari-based Selenium automation with intelligent page understanding
for MTO login and claim verification. Uses Safari for better macOS compatibility.
"""

import os
import time
import random
import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    StaleElementReferenceException
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PageState(Enum):
    """Represents the detected state of a web page."""
    LOGIN_PAGE = "login_page"
    LOGIN_SUCCESS = "login_success"
    LOGIN_ERROR = "login_error"
    SEARCH_PAGE = "search_page"
    RESULTS_PAGE = "results_page"
    ERROR_PAGE = "error_page"
    UNKNOWN = "unknown"


@dataclass
class PageElement:
    """Represents a detected page element with context."""
    element_type: str  # input, button, link, text, etc.
    identifier: str  # id, name, or unique selector
    label: Optional[str] = None  # Associated label text
    value: Optional[str] = None  # Current value if applicable
    visible: bool = True
    interactable: bool = True


@dataclass
class PageAnalysis:
    """Result of analyzing a web page."""
    state: PageState
    url: str
    title: str
    elements: List[PageElement]
    forms: List[Dict[str, Any]]
    error_messages: List[str]
    success_messages: List[str]
    raw_text: str


class SafariAutomation:
    """
    Safari-based Selenium automation with intelligent page understanding.
    
    Features:
    - Automatic Safari driver initialization
    - Intelligent page state detection
    - Form detection and auto-fill capabilities
    - Human-like interaction patterns (random delays, typing speed)
    - Comprehensive error handling and recovery
    """
    
    # Common login form indicators
    LOGIN_INDICATORS = [
        'login', 'sign in', 'log in', 'signin', 'userid', 'username',
        'password', 'credential', 'authenticate', 'bceid'
    ]
    
    # Common error message patterns
    ERROR_PATTERNS = [
        r'error', r'invalid', r'incorrect', r'failed', r'denied',
        r'wrong', r'expired', r'locked', r'disabled', r'unauthorized'
    ]
    
    # Common success message patterns
    SUCCESS_PATTERNS = [
        r'welcome', r'success', r'logged in', r'authenticated',
        r'dashboard', r'home', r'account'
    ]
    
    def __init__(self, headless: bool = False, implicit_wait: int = 10):
        """
        Initialize Safari automation.
        
        Args:
            headless: Safari doesn't support headless, but kept for API compatibility
            implicit_wait: Default wait time for element location
        """
        self.driver: Optional[webdriver.Safari] = None
        self.implicit_wait = implicit_wait
        self._initialize_driver()
    
    def _initialize_driver(self) -> None:
        """Initialize Safari WebDriver with optimal settings."""
        try:
            # Safari options (note: Safari doesn't support headless mode)
            options = SafariOptions()
            
            # Initialize Safari driver
            self.driver = webdriver.Safari(options=options)
            self.driver.implicitly_wait(self.implicit_wait)
            
            # Set window size for consistent behavior
            self.driver.set_window_size(1920, 1080)
            
            logger.info("Safari WebDriver initialized successfully")
            
        except WebDriverException as e:
            logger.error(f"Failed to initialize Safari WebDriver: {e}")
            logger.info("Ensure Safari's 'Allow Remote Automation' is enabled:")
            logger.info("Safari > Preferences > Advanced > Show Develop menu")
            logger.info("Develop > Allow Remote Automation")
            raise
    
    def navigate(self, url: str, wait_for_load: bool = True) -> bool:
        """
        Navigate to a URL with intelligent wait.
        
        Args:
            url: Target URL
            wait_for_load: Whether to wait for page load completion
            
        Returns:
            True if navigation successful, False otherwise
        """
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            
            if wait_for_load:
                self._wait_for_page_load()
            
            self._human_delay(1, 3)
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    def analyze_page(self) -> PageAnalysis:
        """
        Perform comprehensive page analysis to understand current state.
        
        Returns:
            PageAnalysis object with detected elements and page state
        """
        try:
            url = self.driver.current_url
            title = self.driver.title
            
            # Get all text content
            body = self.driver.find_element(By.TAG_NAME, "body")
            raw_text = body.text.lower()
            
            # Detect forms
            forms = self._detect_forms()
            
            # Detect all interactable elements
            elements = self._detect_elements()
            
            # Detect error messages
            error_messages = self._detect_messages(raw_text, self.ERROR_PATTERNS)
            
            # Detect success messages  
            success_messages = self._detect_messages(raw_text, self.SUCCESS_PATTERNS)
            
            # Determine page state
            state = self._determine_page_state(
                url, title, raw_text, forms, error_messages, success_messages
            )
            
            analysis = PageAnalysis(
                state=state,
                url=url,
                title=title,
                elements=elements,
                forms=forms,
                error_messages=error_messages,
                success_messages=success_messages,
                raw_text=raw_text[:1000]  # Truncate for logging
            )
            
            logger.info(f"Page analysis complete - State: {state.value}")
            return analysis
            
        except Exception as e:
            logger.error(f"Page analysis failed: {e}")
            return PageAnalysis(
                state=PageState.UNKNOWN,
                url=self.driver.current_url if self.driver else "",
                title="",
                elements=[],
                forms=[],
                error_messages=[str(e)],
                success_messages=[],
                raw_text=""
            )
    
    def _detect_forms(self) -> List[Dict[str, Any]]:
        """Detect and analyze all forms on the page."""
        forms = []
        try:
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            
            for idx, form in enumerate(form_elements):
                form_data = {
                    "index": idx,
                    "action": form.get_attribute("action") or "",
                    "method": form.get_attribute("method") or "get",
                    "inputs": [],
                    "buttons": []
                }
                
                # Find all inputs in this form
                inputs = form.find_elements(By.TAG_NAME, "input")
                for input_elem in inputs:
                    input_type = input_elem.get_attribute("type") or "text"
                    input_name = input_elem.get_attribute("name") or ""
                    input_id = input_elem.get_attribute("id") or ""
                    
                    form_data["inputs"].append({
                        "type": input_type,
                        "name": input_name,
                        "id": input_id,
                        "placeholder": input_elem.get_attribute("placeholder") or ""
                    })
                
                # Find all buttons in this form
                buttons = form.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
                for button in buttons:
                    form_data["buttons"].append({
                        "text": button.text or button.get_attribute("value") or "",
                        "type": button.get_attribute("type") or "submit"
                    })
                
                forms.append(form_data)
                
        except Exception as e:
            logger.debug(f"Form detection error: {e}")
            
        return forms
    
    def _detect_elements(self) -> List[PageElement]:
        """Detect all significant interactive elements on the page."""
        elements = []
        
        # Selectors for interactive elements
        selectors = [
            ("input", "input:not([type='hidden'])"),
            ("button", "button"),
            ("link", "a[href]"),
            ("select", "select"),
            ("textarea", "textarea")
        ]
        
        try:
            for elem_type, selector in selectors:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in found[:20]:  # Limit to avoid performance issues
                    try:
                        elements.append(PageElement(
                            element_type=elem_type,
                            identifier=elem.get_attribute("id") or elem.get_attribute("name") or "",
                            label=self._find_label_for_element(elem),
                            value=elem.get_attribute("value") if elem_type == "input" else elem.text[:50],
                            visible=elem.is_displayed(),
                            interactable=elem.is_enabled()
                        ))
                    except StaleElementReferenceException:
                        continue
                        
        except Exception as e:
            logger.debug(f"Element detection error: {e}")
            
        return elements
    
    def _find_label_for_element(self, element) -> Optional[str]:
        """Find associated label text for an element."""
        try:
            # Check for associated label by 'for' attribute
            elem_id = element.get_attribute("id")
            if elem_id:
                labels = self.driver.find_elements(
                    By.CSS_SELECTOR, f"label[for='{elem_id}']"
                )
                if labels:
                    return labels[0].text
            
            # Check for parent label
            try:
                parent = element.find_element(By.XPATH, "./ancestor::label")
                return parent.text
            except NoSuchElementException:
                pass
            
            # Check placeholder
            placeholder = element.get_attribute("placeholder")
            if placeholder:
                return placeholder
                
        except Exception:
            pass
            
        return None
    
    def _detect_messages(self, text: str, patterns: List[str]) -> List[str]:
        """Detect messages matching given patterns in page text."""
        messages = []
        for pattern in patterns:
            matches = re.findall(rf'\b{pattern}\b[^.]*\.?', text, re.IGNORECASE)
            messages.extend(matches[:3])  # Limit matches per pattern
        return list(set(messages))[:5]  # Deduplicate and limit total
    
    def _determine_page_state(
        self,
        url: str,
        title: str,
        text: str,
        forms: List[Dict],
        errors: List[str],
        successes: List[str]
    ) -> PageState:
        """Determine the current state of the page based on analysis."""
        
        url_lower = url.lower()
        title_lower = title.lower()
        
        # Check for login page indicators
        has_login_form = any(
            any(
                indicator in str(inp).lower() 
                for indicator in ['password', 'userid', 'username', 'login']
                for inp in form.get("inputs", [])
            )
            for form in forms
        )
        
        is_login_url = any(
            indicator in url_lower 
            for indicator in ['login', 'signin', 'logon', 'bceid']
        )
        
        # Determine state
        if errors:
            if has_login_form or is_login_url:
                return PageState.LOGIN_ERROR
            return PageState.ERROR_PAGE
        
        if successes:
            return PageState.LOGIN_SUCCESS
        
        if has_login_form or is_login_url:
            return PageState.LOGIN_PAGE
        
        if 'search' in url_lower or 'search' in title_lower:
            return PageState.SEARCH_PAGE
        
        if 'result' in url_lower or 'result' in title_lower:
            return PageState.RESULTS_PAGE
        
        return PageState.UNKNOWN
    
    def fill_login_form(
        self,
        username: str,
        password: str,
        username_selectors: Optional[List[str]] = None,
        password_selectors: Optional[List[str]] = None
    ) -> bool:
        """
        Intelligently fill and submit a login form.
        
        Args:
            username: Username to enter
            password: Password to enter
            username_selectors: Optional custom selectors for username field
            password_selectors: Optional custom selectors for password field
            
        Returns:
            True if form filled and submitted, False otherwise
        """
        default_username_selectors = [
            "input[name*='user']", "input[name*='User']",
            "input[id*='user']", "input[id*='User']",
            "input[name='txtUserId']", "input[name='username']",
            "input[type='email']", "input[name='email']"
        ]
        
        default_password_selectors = [
            "input[type='password']",
            "input[name*='pass']", "input[name*='Pass']",
            "input[name='txtPassword']"
        ]
        
        username_selectors = username_selectors or default_username_selectors
        password_selectors = password_selectors or default_password_selectors
        
        try:
            # Find and fill username
            username_field = self._find_element_by_selectors(username_selectors)
            if not username_field:
                logger.error("Could not find username field")
                return False
            
            self._human_type(username_field, username)
            self._human_delay(0.5, 1)
            
            # Find and fill password
            password_field = self._find_element_by_selectors(password_selectors)
            if not password_field:
                logger.error("Could not find password field")
                return False
            
            self._human_type(password_field, password)
            self._human_delay(0.5, 1)
            
            # Find and click submit button
            submit_selectors = [
                "input[type='submit']", "button[type='submit']",
                "button[name*='submit']", "button[name*='login']",
                "input[name='btnSubmit']", "button", "input[type='button']"
            ]
            
            submit_button = self._find_element_by_selectors(submit_selectors)
            if submit_button:
                self._human_delay(0.3, 0.7)
                submit_button.click()
                logger.info("Login form submitted")
                
                # Wait for page transition
                self._wait_for_page_load()
                self._human_delay(2, 4)
                return True
            else:
                logger.warning("Could not find submit button, trying Enter key")
                password_field.submit()
                self._wait_for_page_load()
                return True
                
        except Exception as e:
            logger.error(f"Login form fill failed: {e}")
            return False
    
    def _find_element_by_selectors(self, selectors: List[str]):
        """Try multiple selectors to find an element."""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed() and element.is_enabled():
                    return element
            except NoSuchElementException:
                continue
        return None
    
    def _human_type(self, element, text: str) -> None:
        """Type text with human-like delays between keystrokes."""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def _human_delay(self, min_seconds: float, max_seconds: float) -> None:
        """Add human-like random delay."""
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def _wait_for_page_load(self, timeout: int = 30) -> None:
        """Wait for page to fully load."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("Page load timeout - continuing anyway")
    
    def wait_for_element(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        timeout: int = 10
    ):
        """Wait for an element to be present and return it."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
        except TimeoutException:
            logger.warning(f"Timeout waiting for element: {selector}")
            return None
    
    def get_page_text(self) -> str:
        """Get all visible text from the current page."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            return body.text
        except Exception:
            return ""
    
    def take_screenshot(self, filename: str = "screenshot.png") -> bool:
        """Take a screenshot of the current page."""
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False
    
    def close(self) -> None:
        """Close the browser and cleanup."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Safari WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")


class MTOAutomation(SafariAutomation):
    """
    Specialized automation for BC Mineral Titles Online (MTO).
    
    Handles:
    - BCeID login flow
    - Tenure search functionality
    - Claim status verification
    """
    
    MTO_LOGIN_URL = (
        "https://www.bceid.ca/clp/accountlogon.aspx?type=0"
        "&appurl=https%3A%2F%2Fwww.mtonline.gov.bc.ca%2Fmtov%2Fhome.do"
        "&servicecreds=MTOM&appname=MTO"
    )
    MTO_SEARCH_URL = "https://www.mtonline.gov.bc.ca/mtov/tenureSearch.do"
    
    def __init__(self):
        super().__init__()
        self._logged_in = False
    
    def login(self, username: str, password: str) -> bool:
        """
        Login to MTO via BCeID.
        
        Args:
            username: BCeID username
            password: BCeID password
            
        Returns:
            True if login successful, False otherwise
        """
        logger.info("Starting MTO login via BCeID...")
        
        # Navigate to login page
        if not self.navigate(self.MTO_LOGIN_URL):
            return False
        
        # Analyze page to confirm we're on login
        analysis = self.analyze_page()
        
        if analysis.state not in [PageState.LOGIN_PAGE, PageState.UNKNOWN]:
            logger.warning(f"Unexpected page state: {analysis.state}")
        
        # Fill login form with BCeID-specific selectors
        success = self.fill_login_form(
            username=username,
            password=password,
            username_selectors=["input[name='txtUserId']", "input[id='txtUserId']"],
            password_selectors=["input[name='txtPassword']", "input[id='txtPassword']"]
        )
        
        if not success:
            return False
        
        # Verify login success
        analysis = self.analyze_page()
        
        if analysis.state == PageState.LOGIN_ERROR:
            logger.error(f"Login failed: {analysis.error_messages}")
            return False
        
        # Check if we're now on MTO site
        if "mtonline" in self.driver.current_url.lower():
            logger.info("MTO login successful")
            self._logged_in = True
            return True
        
        logger.warning("Login result unclear - checking page content")
        if any(msg for msg in analysis.success_messages):
            self._logged_in = True
            return True
            
        return False
    
    def search_tenure(self, tenure_id: str) -> Dict[str, Any]:
        """
        Search for a specific tenure ID and return status.
        
        Args:
            tenure_id: The tenure number to search
            
        Returns:
            Dictionary with tenure information and status
        """
        if not self._logged_in:
            logger.warning("Not logged in - results may be limited")
        
        result = {
            "tenure_id": tenure_id,
            "status": "unknown",
            "available": False,
            "details": {}
        }
        
        try:
            # Navigate to search page
            if not self.navigate(self.MTO_SEARCH_URL):
                result["error"] = "Failed to navigate to search page"
                return result
            
            # Find and fill tenure search field
            search_field = self.wait_for_element(
                "input[name='tenureNumber']",
                timeout=10
            )
            
            if not search_field:
                # Try alternative selectors
                search_field = self._find_element_by_selectors([
                    "input[name='tenureNumber']",
                    "input[id='tenureNumber']",
                    "input[type='text']"
                ])
            
            if not search_field:
                result["error"] = "Could not find search field"
                return result
            
            # Enter tenure ID with human-like typing
            self._human_type(search_field, tenure_id)
            self._human_delay(0.5, 1)
            
            # Submit search
            submit = self._find_element_by_selectors([
                "input[type='submit']",
                "button[type='submit']",
                "button"
            ])
            
            if submit:
                submit.click()
            else:
                search_field.submit()
            
            self._wait_for_page_load()
            self._human_delay(1, 2)
            
            # Analyze results
            page_text = self.get_page_text().lower()
            
            # Check for status indicators
            if "expired" in page_text or "forfeited" in page_text:
                result["status"] = "expired"
                result["available"] = True
            elif "active" in page_text or "good standing" in page_text:
                result["status"] = "active"
                result["available"] = False
            elif "not found" in page_text or "no results" in page_text:
                result["status"] = "not_found"
                result["available"] = False
            
            # Extract any additional details
            result["page_text_snippet"] = page_text[:500]
            
            logger.info(f"Tenure {tenure_id}: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Tenure search failed: {e}")
            result["error"] = str(e)
            return result
    
    def verify_claims_batch(
        self,
        tenure_ids: List[str],
        delay_between: Tuple[float, float] = (3, 7)
    ) -> List[Dict[str, Any]]:
        """
        Verify multiple tenure IDs with rate limiting.
        
        Args:
            tenure_ids: List of tenure IDs to verify
            delay_between: Min/max delay between requests (for rate limiting)
            
        Returns:
            List of verification results
        """
        results = []
        
        for idx, tenure_id in enumerate(tenure_ids):
            logger.info(f"Verifying {idx + 1}/{len(tenure_ids)}: {tenure_id}")
            
            result = self.search_tenure(tenure_id)
            results.append(result)
            
            # Rate limiting
            if idx < len(tenure_ids) - 1:
                self._human_delay(*delay_between)
        
        return results


def load_credentials_from_env() -> Tuple[Optional[str], Optional[str]]:
    """
    Load credentials from environment variables.
    
    Returns:
        Tuple of (username, password) or (None, None) if not found
    """
    username = os.environ.get("MTO_USERNAME") or os.environ.get("BCEID_USERNAME")
    password = os.environ.get("MTO_PASSWORD") or os.environ.get("BCEID_PASSWORD")
    
    if not username or not password:
        logger.warning(
            "Credentials not found in environment. "
            "Set MTO_USERNAME and MTO_PASSWORD environment variables."
        )
        return None, None
    
    return username, password


if __name__ == "__main__":
    """Demo of Safari automation capabilities."""
    
    print("=" * 60)
    print("Prometheus Analytics - Safari Selenium Automation Demo")
    print("=" * 60)
    
    # Check for credentials
    username, password = load_credentials_from_env()
    
    if not username or not password:
        print("\nNo credentials found. Running in demo mode.")
        print("To use with MTO, set environment variables:")
        print("  export MTO_USERNAME='your_username'")
        print("  export MTO_PASSWORD='your_password'")
        print("\nStarting basic Safari automation test...")
        
        try:
            automation = SafariAutomation()
            
            # Test navigation
            print("\nNavigating to example.com...")
            automation.navigate("https://example.com")
            
            # Analyze page
            analysis = automation.analyze_page()
            print(f"\nPage State: {analysis.state.value}")
            print(f"Page Title: {analysis.title}")
            print(f"Found {len(analysis.elements)} interactive elements")
            
            # Cleanup
            automation.close()
            print("\nDemo complete!")
            
        except WebDriverException as e:
            print(f"\nError: {e}")
            print("\nTo enable Safari automation:")
            print("1. Open Safari > Preferences > Advanced")
            print("2. Check 'Show Develop menu in menu bar'")
            print("3. Develop > Allow Remote Automation")
    else:
        print("\nCredentials found. Starting MTO automation...")
        
        try:
            mto = MTOAutomation()
            
            # Login
            if mto.login(username, password):
                print("Login successful!")
                
                # Example: search for a tenure (use clearly fake ID for testing)
                # result = mto.search_tenure("TEST_EXAMPLE_ID")
                # print(f"Tenure status: {result['status']}")
            else:
                print("Login failed!")
            
            mto.close()
            
        except Exception as e:
            print(f"Error: {e}")
