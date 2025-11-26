import os
import time
import random
import hashlib
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

INPUT_FILE = "b_cleaned_list.csv"
OUTPUT_FILE = "b_hashed_list.csv"
BACKUP_FILE = "backup.csv"
HTML_DIR = "raw_html"

os.makedirs(HTML_DIR, exist_ok=True)


def make_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fetch_raw_html(driver, url: str) -> str:
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        return driver.page_source
    except Exception as e:
        raise RuntimeError(f"Erreur lors du chargement : {e}")


# reprise automatique
if os.path.exists(OUTPUT_FILE):
    df = pd.read_csv(OUTPUT_FILE)
else:
    df = pd.read_csv(INPUT_FILE)

if "hash_id" not in df.columns:
    df["hash_id"] = ""


# configuration Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)


# boucle principale
for i, row in df.iterrows():
    if pd.isna(row["link"]) or row["hash_id"]:
        continue

    url = str(row["link"])

    try:
        html = fetch_raw_html(driver, url)
    except Exception as e:
        print(f"[{i}] Erreur critique : {e}")
        df.to_csv(OUTPUT_FILE, index=False)
        df.to_csv(BACKUP_FILE, index=False)
        driver.quit()
        raise SystemExit(1)

    h = make_hash(url)
    path = os.path.join(HTML_DIR, f"{h}.html")

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    df.at[i, "hash_id"] = h

    if i % 50 == 0 and i != 0:
        df.to_csv(OUTPUT_FILE, index=False)
        df.to_csv(BACKUP_FILE, index=False)
        print(f"[{i}] sauvegarde partielle effectuée")

    delay = random.uniform(0.5, 5)
    print(f"Pause {delay:.2f}s avant la page suivante.")
    time.sleep(delay)


driver.quit()

df.to_csv(OUTPUT_FILE, index=False)
print("✅ Terminé. Sauvegarde finale écrite.")