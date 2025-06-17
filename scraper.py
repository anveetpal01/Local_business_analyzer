import time
import re
import requests
import instaloader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

def extract_instagram_from_website(website):
    if not website or website == "Not found":
        return None
    try:
        resp = requests.get(website, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        matches = re.findall(r'instagram\.com/([A-Za-z0-9_.]+)', resp.text, re.IGNORECASE)
        if matches:
            return matches[0]  # Return username only, not @handle
    except Exception:
        pass
    return None

def extract_instagram_from_gmaps_panel(driver):
    try:
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'instagram.com')]")
        for link in links:
            href = link.get_attribute('href')
            match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', href)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

def google_search_instagram_handle(business_name):
    query = f"{business_name} instagram"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        matches = re.findall(r'https://www\.instagram\.com/([A-Za-z0-9_.]+)/', resp.text)
        # Filter out common non-profile usernames
        filtered = [m for m in matches if m.lower() not in ["explore", "accounts", "about", "developer", "directory", "p", "reel", "stories", "hashtag"]]
        if filtered:
            return filtered[0]
    except Exception:
        pass
    return None

def get_instagram_details_with_instaloader(username, loader, max_retries=3):
    """Fetch Instagram profile data (bio, followers) using Instaloader, with retries."""
    for attempt in range(max_retries):
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            return (
                f"@{profile.username}",
                profile.biography,
                profile.followers
            )
        except Exception as e:
            print(f"Attempt {attempt+1}: Error fetching '{username}' via Instaloader: {e}")
            time.sleep(5)
    return ("Not found", "Not found", "Not found")

def get_instagram_handle_and_details(driver, name, website, loader):
    # Try all sources for Instagram username
    for extractor in [extract_instagram_from_website, extract_instagram_from_gmaps_panel, google_search_instagram_handle]:
        if extractor == extract_instagram_from_website:
            username = extractor(website)
        elif extractor == extract_instagram_from_gmaps_panel:
            username = extractor(driver)
        else:
            username = extractor(name)
        if username:
            ig_handle, ig_bio, ig_followers = get_instagram_details_with_instaloader(username, loader)
            # Only return if both bio and followers are found (i.e., real profile)
            if ig_handle != "Not found" and (ig_bio or ig_followers):
                return ig_handle, ig_bio, ig_followers
    # If none found, return not found
    return ("Not found", "Not found", "Not found")

def scrape_gmaps(city, keyword, max_results=50, sleep_between=2):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver = webdriver.Chrome(options=options)

    search_query = f"{keyword} in {city}"
    driver.get(f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}")
    time.sleep(5)

    try:
        scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for") or @role="feed"]')
        for _ in range(10):
            driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
            time.sleep(1)
    except Exception:
        pass

    results = []
    seen_names = set()

    loader = instaloader.Instaloader()
    # For best results, login with a throwaway account:
    # loader.login("your_username", "your_password")

    for idx in range(max_results):
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, 'a.hfpxzc')
            if idx >= len(cards):
                break

            card = cards[idx]
            driver.execute_script("arguments[0].scrollIntoView();", card)
            ActionChains(driver).move_to_element(card).click().perform()
            time.sleep(3)

            # Business Name
            try:
                name = driver.find_element(By.CSS_SELECTOR, 'h1.DUwDvf').text
            except:
                name = "Not found"

            # Deduplication
            if not name or name in seen_names:
                try:
                    back_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Back"]')
                    back_button.click()
                    time.sleep(2)
                except Exception:
                    pass
                continue
            seen_names.add(name)

            # Phone Number
            phone = "Not found"
            try:
                phone_elem = driver.find_element(By.XPATH, "//button[contains(@data-tooltip, 'Phone')]")
                phone = phone_elem.text
            except:
                try:
                    details = driver.find_elements(By.XPATH, "//span|//div")
                    for d in details:
                        txt = d.text.strip()
                        if re.search(r'(review|rating|star|votes)', txt, re.IGNORECASE):
                            continue
                        if re.match(r"^\+?\d[\d\s\-().]{7,}$", txt) and not re.match(r"^(\d)\1{7,}$", re.sub(r'\D', '', txt)):
                            if len(re.sub(r'\D', '', txt)) >= 8:
                                phone = txt
                                break
                except:
                    pass

            # Website
            try:
                website_elem = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Website')]")
                website = website_elem.get_attribute('href')
            except:
                website = "Not found"

            # Instagram (robust: only real profiles with bio/followers)
            ig_handle, ig_bio, ig_followers = get_instagram_handle_and_details(driver, name, website, loader)

            results.append({
                'name': name,
                'phone': phone,
                'website': website,
                'instagram': ig_handle,
                'bio': ig_bio,
                'followers': ig_followers
            })

            try:
                back_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Back"]')
                back_button.click()
                time.sleep(2)
            except Exception:
                driver.get(f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}")
                time.sleep(5)
                try:
                    scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for") or @role="feed"]')
                    for _ in range(10):
                        driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                        time.sleep(1)
                except Exception:
                    pass

            time.sleep(sleep_between)

        except Exception as e:
            print(f"Error on business {idx}: {e}")
            continue

    driver.quit()
    
    return results
