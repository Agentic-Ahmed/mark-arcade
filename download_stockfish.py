import os
import requests
import zipfile
import io
import platform

ENGINES_DIR = 'engines'
STOCKFISH_URL = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-windows-x86-64-avx2.zip"

def setup():
    if not os.path.exists(ENGINES_DIR):
        os.makedirs(ENGINES_DIR)
        print(f"Created '{ENGINES_DIR}' folder.")

    print(f"Attempting to download Stockfish 16 for Windows...")
    
    try:
        response = requests.get(STOCKFISH_URL)
        if response.status_code == 200:
            print("Download successful! Extracting...")
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Extract only the exe
                for file in z.namelist():
                    if file.endswith('.exe'):
                        z.extract(file, ENGINES_DIR)
                        print(f"Extracted: {file}")
                        
                        # Rename for simplicity
                        old_path = os.path.join(ENGINES_DIR, file)
                        new_path = os.path.join(ENGINES_DIR, 'stockfish.exe')
                        if os.path.exists(new_path):
                            os.remove(new_path)
                        os.rename(old_path, new_path)
                        print(f"Engine ready at: {new_path}")
                        return
        else:
            print(f"Failed to download. Status Code: {response.status_code}")
    
    except Exception as e:
        print(f"Error during download: {e}")

    print("\n--- MANUAL SETUP REQUIRED ---")
    print(f"Could not automatically setup Stockfish.")
    print(f"1. Go to: https://stockfishchess.org/download/")
    print(f"2. Download the Windows zip file.")
    print(f"3. Extract the '.exe' file.")
    print(f"4. Move it to this folder: {os.path.abspath(ENGINES_DIR)}")

if __name__ == "__main__":
    setup()
