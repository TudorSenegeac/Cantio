"""
Cantio - mdbtools downloader
Descarcă executabilele mdbtools pentru Windows din GitHub releases
și le plasează în <app_dir>/mdbtools/.
"""
import os
import sys
import urllib.request
import zipfile


def download_mdbtools():
    """
    Descarcă mdbtools pentru Windows (lsgunth/mdbtools-win) din GitHub.

    Extrage doar fișierele .exe și .dll direct în <app_dir>/mdbtools/.
    Returnează calea folderului mdbtools dacă a reușit, sau None.
    """
    app_dir = os.path.dirname(os.path.abspath(__file__))
    mdb_dir = os.path.join(app_dir, "mdbtools")
    mdb_exe = os.path.join(mdb_dir, "mdb-tables.exe")

    if os.path.exists(mdb_exe):
        return mdb_dir

    os.makedirs(mdb_dir, exist_ok=True)

    url = (
        "https://github.com/lsgunth/"
        "mdbtools-win/archive/refs/heads/master.zip"
    )
    zip_path = os.path.join(mdb_dir, "mdbtools.zip")

    print("[BIB] Descărcare mdbtools din GitHub…")
    try:
        urllib.request.urlretrieve(url, zip_path)

        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.endswith(".exe") or name.endswith(".dll"):
                    filename = os.path.basename(name)
                    if not filename:
                        continue
                    data = z.read(name)
                    out_path = os.path.join(mdb_dir, filename)
                    with open(out_path, "wb") as f:
                        f.write(data)

        try:
            os.remove(zip_path)
        except Exception:
            pass

        if os.path.exists(mdb_exe):
            print(f"[BIB] mdbtools descărcat OK → {mdb_dir}")
            return mdb_dir

        print("[BIB] Descărcare completă dar mdb-tables.exe nu a fost găsit în arhivă.")
    except Exception as e:
        print(f"[BIB] Descărcare eșuată: {e}")

    return None


if __name__ == "__main__":
    result = download_mdbtools()
    if result:
        print(f"Succes: {result}")
    else:
        print("Eșec.")
        sys.exit(1)
