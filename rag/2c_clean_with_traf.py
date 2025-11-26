import os
import trafilatura
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

# --- CONFIGURATION ---
RAW_HTML_DIR = "raw_html"
OUTPUT_DIR = "xml_dir"

# --- FONCTIONS ---

def extract_content(html_content: str) -> str:
    """
    Passe directement le HTML brut à Trafilatura.
    L'outil va détecter automatiquement le corps du texte.
    """
    
    result = trafilatura.extract(
        html_content,
        output_format="xml",       # Format de sortie
        include_tables=True,       # Garder les tableaux
        favor_precision=True,      # Préférer la précision à la quantité
        include_comments=False,    # Pas de commentaires HTML
        no_fallback=False          # Tenter d'autres méthodes si la principale échoue
    )

    if not result:
        raise RuntimeError("Trafilatura n'a pas réussi à extraire de texte principal")

    return result

def process_single_file(html_file: Path):
    try:
        # Lecture
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Extraction directe
        extracted_xml = extract_content(html_content)

        # Écriture
        output_path = Path(OUTPUT_DIR) / f"{html_file.stem}.xml"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(extracted_xml)
        
        return None # Succès (renvoie None)
    
    except Exception as e:
        # En cas d'erreur, on renvoie le nom du fichier et l'erreur
        return f"❌ {html_file.name} : {e}"

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    html_files = list(Path(RAW_HTML_DIR).glob("*.html"))
    print(f"{len(html_files)} fichiers HTML détectés.")

    if not html_files:
        print("Dossier vide. Vérifiez le chemin RAW_HTML_DIR.")
        return

    # Configuration du parallélisme
    # On laisse 2 cœurs libres pour que le PC reste utilisable
    nb_workers = max(1, os.cpu_count() - 2)
    print(f"Lancement de l'extraction sur {nb_workers} coeurs...")

    with ProcessPoolExecutor(max_workers=nb_workers) as executor:
        # Lancement avec barre de progression
        results = list(tqdm(executor.map(process_single_file, html_files), total=len(html_files)))

    # Gestion et affichage des erreurs
    errors = [res for res in results if res is not None]
    
    print(f"\nTerminé.")
    if errors:
        print(f"{len(errors)} fichiers en erreur.")
        print("-" * 40)
        print("Exemples d'erreurs :")
        for err in errors[:5]:
            print(err)
    else:
        print("✅ Succès total : 100% des fichiers extraits.")

if __name__ == "__main__":
    main()