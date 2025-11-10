import os
import time
import random
import hashlib
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

INPUT_FILE = "b_cleaned_list.csv"
OUTPUT_FILE = "b_hashed_list.csv"
BACKUP_FILE = "backup.csv"
TEXT_DIR = "texts"
os.makedirs(TEXT_DIR, exist_ok=True)

def make_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def fetch_text_selenium(driver, url: str) -> str:
    try:
        driver.get(url)

        # Attente du chargement complet du body
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Sélection du conteneur principal
        div = (
            soup.find("div", id="text")
        )
        if not div:
            div = soup

        # 1. Supprimer les balises inutiles (non textuelles ou décoratives)
        for tag in div.find_all(
            ["table", "figure", "img", "svg", "style", "script", "footer", "header", "nav"]
        ):
            tag.decompose()

        # 2. Extraire uniquement les paragraphes
        paragraphs = [p.get_text(" ", strip=True) for p in div.find_all("p")]
        # Supprimer les paragraphes trop courts
        paragraphs = [p for p in paragraphs if len(p) > 5]

        # 3. Fusionner les paragraphes
        text = "\n".join(paragraphs)

        # 4. Nettoyage des résidus textuels
        text = re.sub(r"http\S+", "", text)  # URLs
        text = re.sub(r"(References|Footnotes|EUR-Lex).*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()

        return text

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
        text = fetch_text_selenium(driver, url)
    except Exception as e:
        print(f"[{i}] Erreur critique : {e}")
        df.to_csv(OUTPUT_FILE, index=False)
        df.to_csv(BACKUP_FILE, index=False)
        driver.quit()
        raise SystemExit(1)

    h = make_hash(url)
    path = os.path.join(TEXT_DIR, f"{h}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    df.at[i, "hash_id"] = h

    if i % 50 == 0:
        df.to_csv(OUTPUT_FILE, index=False)
        df.to_csv(BACKUP_FILE, index=False)
        print(f"[{i}] sauvegarde partielle effectuée")

    delay = random.uniform(0.5, 5)
    print(f"Pause {delay:.2f}s avant la page suivante.")
    time.sleep(delay)

driver.quit()

df.to_csv(OUTPUT_FILE, index=False)
print("✅ Terminé. Sauvegarde finale écrite.")
