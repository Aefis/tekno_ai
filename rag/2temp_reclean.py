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
SIZE_THRESHOLD = 4096  # Seuil : 4 Ko

os.makedirs(HTML_DIR, exist_ok=True)


def make_hash(value: str) -> str:
    # Le hash dépend uniquement de l'URL. Si l'URL ne change pas, le hash reste le même.
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


# --- CHARGEMENT ---
if os.path.exists(OUTPUT_FILE):
    print(f"Chargement de {OUTPUT_FILE}...")
    df = pd.read_csv(OUTPUT_FILE)
else:
    print(f"Chargement de {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)

if "hash_id" not in df.columns:
    df["hash_id"] = ""
    
df["hash_id"] = df["hash_id"].fillna("")


# --- NETTOYAGE PRÉALABLE ---
print("🔍 Vérification et nettoyage des fichiers existants...")
files_reset_count = 0

for i, row in df.iterrows():
    if row["hash_id"]:
        h = row["hash_id"]
        path = os.path.join(HTML_DIR, f"{h}.html")
        
        should_retry = False
        
        if os.path.exists(path):
            file_size = os.path.getsize(path)
            
            # SI FICHIER TROP PETIT
            if file_size <= SIZE_THRESHOLD:
                print(f"[{i}] Fichier trop petit ({file_size}o) -> SUPPRESSION : {path}")
                try:
                    os.remove(path)  # <--- SUPPRESSION PHYSIQUE DU FICHIER
                except OSError as e:
                    print(f"    ⚠️ Impossible de supprimer {path} : {e}")
                
                should_retry = True
        else:
            # SI FICHIER ABSENT MAIS HASH PRÉSENT DANS CSV
            print(f"[{i}] Fichier manquant sur le disque -> Marquage pour nouvel essai.")
            should_retry = True
            
        if should_retry:
            df.at[i, "hash_id"] = ""  # On vide le hash dans le CSV
            files_reset_count += 1

print(f"--- {files_reset_count} fichiers supprimés/réinitialisés ---\n")


# --- CONFIGURATION SELENIUM ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# User-agent pour simuler un vrai navigateur
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)


# --- BOUCLE PRINCIPALE ---
try:
    for i, row in df.iterrows():
        # On saute si pas de lien ou si hash_id existe déjà (et n'a pas été effacé lors du nettoyage)
        if pd.isna(row["link"]) or (row["hash_id"] != ""):
            continue

        url = str(row["link"])
        print(f"[{i}] Téléchargement : {url}")

        try:
            html = fetch_raw_html(driver, url)
            
            # Vérification de sécurité immédiate après téléchargement
            if len(html.encode('utf-8')) <= SIZE_THRESHOLD:
                 print(f"   ⚠️ Attention : Le nouveau téléchargement est encore petit ({len(html)} chars).")

        except Exception as e:
            print(f"[{i}] Erreur : {e}")
            continue 

        h = make_hash(url)
        path = os.path.join(HTML_DIR, f"{h}.html")

        # Écriture du fichier (si un vieux fichier trainait encore par hasard, il est écrasé ici)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        df.at[i, "hash_id"] = h

        if i % 50 == 0 and i != 0:
            df.to_csv(OUTPUT_FILE, index=False)
            df.to_csv(BACKUP_FILE, index=False)
            print(f"   💾 Sauvegarde auto")

        delay = random.uniform(1.0, 5.0)
        time.sleep(delay)

except KeyboardInterrupt:
    print("\nArrêt manuel...")

finally:
    driver.quit()
    df.to_csv(OUTPUT_FILE, index=False)
    print("✅ Terminé. Sauvegarde finale effectuée.")