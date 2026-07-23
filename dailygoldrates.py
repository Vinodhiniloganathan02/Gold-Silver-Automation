import os
import time
import glob
import traceback
import requests

from datetime import datetime
from urllib.parse import quote_plus

from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# ==========================================================
# CONFIGURATION
# ==========================================================

KJPL_URL = "http://www.kjpl.in/"

POSTER_URL = "https://poster-generator-beta-flax.vercel.app/"

DOWNLOAD_FOLDER = "downloads"

OUTPUT_FOLDER = "output"

HEADLESS = True

WAIT_AFTER_POSTER_UPDATE = 10

CAPTION = "SMS Jewellers Today's Gold Rate"

# ---------------- MongoDB ----------------

MONGO_USERNAME = "inkdabba_dev"

MONGO_PASSWORD = "Dev1234"

username = quote_plus(MONGO_USERNAME)

password = quote_plus(MONGO_PASSWORD)

MONGO_URI = (
    f"mongodb+srv://{username}:{password}"
    "@inkdabba.g1fmygf.mongodb.net/"
    "?appName=Inkdabba"
)

DB_NAME = "Posters"

COLLECTION_NAME = "Prices"

# ---------------- GREEN API ----------------

ID_INSTANCE = "710722684359"
API_TOKEN = "4bc11612f8a947b0a45589addbd966c76b6dbbb8e8df425fb8"
MEDIA_URL = "https://7107.api.greenapi.com"

# Receiver Number

CHAT_ID = "919940183025@c.us"


# ==========================================================
# CREATE FOLDERS
# ==========================================================

for folder in [

    DOWNLOAD_FOLDER,

    OUTPUT_FOLDER,

    "logs"

]:

    os.makedirs(folder, exist_ok=True)


# ==========================================================
# DATABASE
# ==========================================================

client = MongoClient(MONGO_URI)

db = client[DB_NAME]

collection = db[COLLECTION_NAME]


def save_price(gold, silver):

    today = datetime.now().strftime("%Y-%m-%d")

    last = collection.find_one(

        sort=[("updatedAt", -1)]

    )

    if last:

        if (

            last["gold"] == gold

            and

            last["silver"] == silver

            and

            last["date"] == today

        ):

            print("Today's rate already stored.")

            return

    collection.insert_one(

        {

            "date": today,

            "gold": gold,

            "silver": silver,

            "updatedAt": datetime.utcnow()

        }

    )

    print("MongoDB Updated.")

def create_driver():

    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--start-maximized")

    prefs = {
        "download.default_directory": os.path.abspath(DOWNLOAD_FOLDER),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }

    options.add_experimental_option("prefs", prefs)

    # Automatically download and use the correct ChromeDriver
    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)

    return driver


# ==========================================================
# FETCH KJPL RATES
# ==========================================================

def fetch_rates():

    driver = create_driver()
    wait = WebDriverWait(driver, 30)

    try:
        print("Opening KJPL...")
        driver.get(KJPL_URL)

        # Wait until page is fully loaded
        wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        time.sleep(5)

        # Try to close common popups
        popup_selectors = [
            ".fancybox-close",
            ".mfp-close",
            ".modal .close",
            ".close",
            ".popup-close",
            ".btn-close"
        ]

        for selector in popup_selectors:
            try:
                driver.find_element(By.CSS_SELECTOR, selector).click()
                print("Popup closed:", selector)
                time.sleep(1)
            except:
                pass

        # Hide fixed overlays if present
        driver.execute_script("""
            document.querySelectorAll(
                '.fancybox-overlay,.modal,.popup,.overlay'
            ).forEach(e => e.style.display='none');
        """)

        tables = driver.find_elements(By.CSS_SELECTOR, "table.chennairate_table")

        print("Tables found:", len(tables))

        gold = None
        silver = None

        for table in tables:

            rows = table.find_elements(By.TAG_NAME, "tr")

            for row in rows:

                cells = row.find_elements(By.TAG_NAME, "td")

                if len(cells) != 2:
                    continue

                key = cells[0].text.strip().upper()
                value = cells[1].text.strip()

                print(key, "=>", value)

                if "GOLD" in key:
                    gold = value.replace("(₹)", "").strip()

                elif "SILVER" in key:
                    silver = value.replace("(₹)", "").strip()

            if gold and silver:
                break

        print("Gold  :", gold)
        print("Silver:", silver)

        driver.quit()
        return gold, silver

    except Exception:
        import traceback
        traceback.print_exc()

        try:
            driver.quit()
        except:
            pass

        return None, None

def clear_download_folder():

    for file in glob.glob(DOWNLOAD_FOLDER + "/*"):

        try:
            os.remove(file)
        except:
            pass


def set_input(driver, selectors, value):

    """
    Try multiple CSS selectors until one works.
    """

    for selector in selectors:

        try:

            element = driver.find_element(By.CSS_SELECTOR, selector)

            driver.execute_script("""
                arguments[0].value='';
                arguments[0].dispatchEvent(new Event('input',{bubbles:true}));
            """, element)

            element.clear()

            element.send_keys(str(value))

            print("Updated :", selector)

            return True

        except:

            continue

    print("Could not find selector :", selectors)

    return False


def wait_for_png():

    timeout = 40

    while timeout > 0:

        files = glob.glob(DOWNLOAD_FOLDER + "/*.png")

        if files:

            latest = max(files, key=os.path.getctime)

            return latest

        timeout -= 1

        time.sleep(1)

    return None


def download_poster(gold, silver):

    clear_download_folder()

    driver = create_driver()

    wait = WebDriverWait(driver, 20)

    try:

        print("----------------------------------")
        print("Opening Poster Generator")
        print("----------------------------------")

        driver.get(POSTER_URL)

        time.sleep(5)

        today = datetime.now().strftime("%d-%m-%Y")

        # ---------------------------------
        # DATE
        # ---------------------------------

        set_input(

            driver,

            [

                "#date",

                "input[name='date']",

                "input[placeholder*='Date']",

                "input"

            ],

            today

        )

        # ---------------------------------
        # GOLD
        # ---------------------------------

        set_input(

            driver,

            [

                "#gold",

                "input[name='gold']",

                "input[placeholder*='Gold']"

            ],

            gold

        )

        # ---------------------------------
        # SILVER
        # ---------------------------------

        set_input(

            driver,

            [

                "#silver",

                "input[name='silver']",

                "input[placeholder*='Silver']"

            ],

            silver

        )

        print()
        print("Waiting 10 Seconds...")

        time.sleep(WAIT_AFTER_POSTER_UPDATE)

        # ---------------------------------
        # DOWNLOAD BUTTON
        # ---------------------------------

        try:

            download = wait.until(

                EC.element_to_be_clickable(

                    (

                        By.XPATH,

                        "//button[contains(.,'Download PNG')]"

                    )

                )

            )

            download.click()

            print("Download Button Clicked")

        except Exception as e:

            print("Unable to click download button")

            print(e)

            driver.quit()

            return None

        print("Waiting for PNG Download...")

        image = wait_for_png()

        driver.quit()

        if image:

            print()

            print("Poster Downloaded")

            print(image)

            return image

        else:

            print("PNG not downloaded")

            return None

    except Exception as e:

        driver.quit()

        print(e)

        return None
    


def send_whatsapp(image_path):

    print()
    print("---------------------------------------")
    print("Sending Poster to WhatsApp")
    print("---------------------------------------")

    if image_path is None:

        print("No image found.")

        return False

    if not os.path.exists(image_path):

        print("Image does not exist.")

        return False

    url = (
        f"{MEDIA_URL}/waInstance{ID_INSTANCE}"
        f"/sendFileByUpload/{API_TOKEN}"
    )

    print("Sender   : 8248477398")
    print("Receiver : 9940183025")
    print()

    try:

        with open(image_path, "rb") as file:

            files = {

                "file": file

            }

            data = {

                "chatId": CHAT_ID,

                "fileName": os.path.basename(image_path),

                "caption": CAPTION

            }

            response = requests.post(

                url,

                files=files,

                data=data,

                timeout=60

            )

        print()

        print("Status Code :", response.status_code)

        if response.status_code == 200:

            print()
            print("===================================")
            print("MESSAGE SENT SUCCESSFULLY")
            print("===================================")

            try:

                print(response.json())

            except:

                print(response.text)

            return True

        else:

            print()
            print("===================================")
            print("FAILED TO SEND")
            print("===================================")

            print(response.text)

            return False

    except Exception as e:

        print()

        print("Exception")

        print(e)

        return False


# ==========================================================
# OPTIONAL TEST
# ==========================================================

def test_whatsapp():

    pngs = glob.glob(DOWNLOAD_FOLDER + "/*.png")

    if not pngs:

        print("No PNG Available")

        return

    latest = max(

        pngs,

        key=os.path.getctime

    )

    send_whatsapp(latest)


def banner():

    print()
    print("=" * 60)
    print(" SMS JEWELLERS GOLD RATE AUTOMATION ")
    print("=" * 60)
    print()


def automation():

    banner()

    # ------------------------------------------
    # STEP 1
    # ------------------------------------------

    print("[1/4] Fetching Today's Gold & Silver Rate...")

    gold, silver = fetch_rates()

    if gold is None or silver is None:

        print()
        print("Unable to fetch today's rate.")
        return

    print()

    print("--------------------------------")
    print("Today's Rate")
    print("--------------------------------")
    print("Gold  :", gold)
    print("Silver:", silver)
    print("--------------------------------")

    # ------------------------------------------
    # STEP 2
    # ------------------------------------------

    print()

    print("[2/4] Saving into MongoDB...")

    try:

        save_price(gold, silver)

    except Exception as e:

        print(e)

    print("Database Updated.")

    # ------------------------------------------
    # STEP 3
    # ------------------------------------------

    print()

    print("[3/4] Generating Poster...")

    poster = download_poster(gold, silver)

    if poster is None:

        print()

        print("Poster generation failed.")

        return

    print()

    print("--------------------------------")
    print("Poster Saved")
    print("--------------------------------")

    print(poster)

    # ------------------------------------------
    # STEP 4
    # ------------------------------------------

    print()

    print("[4/4] Sending to WhatsApp...")

    success = send_whatsapp(poster)

    if success:

        print()

        print("========================================")
        print(" AUTOMATION COMPLETED SUCCESSFULLY ")
        print("========================================")

        print()

        print("Sender   : 8248477398")

        print("Receiver : 9940183025")

        print()

        print("Poster Sent Successfully")

    else:

        print()

        print("========================================")
        print(" WHATSAPP SENDING FAILED ")
        print("========================================")


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    try:

        automation()

    except KeyboardInterrupt:

        print()

        print("Stopped By User.")

    except Exception:

        print()

        print(traceback.format_exc())