#!/usr/bin/env python3
"""
reset_tout.py — Supprime TOUTES les données (serveur + local)
Utilisation : python reset_tout.py
"""
import os, sys, sqlite3

# ─── Charger .env local ───────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
    print("[.env] Variables chargées.")
except ImportError:
    print("[.env] python-dotenv non installé — variables système utilisées.")

# ─── 1. RESET POSTGRESQL (Railway) ───────────────────
print("\n=== RESET SERVEUR (PostgreSQL Railway) ===")
db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    print("[SKIP] DATABASE_URL non définie — serveur ignoré.")
else:
    try:
        import psycopg2
        # Convertir URL postgres:// → postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        from urllib.parse import urlparse
        p = urlparse(db_url)
        conn = psycopg2.connect(
            host=p.hostname, port=p.port or 5432,
            database=p.path.lstrip("/"),
            user=p.username, password=p.password,
            connect_timeout=10
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Lister toutes les tables
        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tables = [row[0] for row in cur.fetchall()]

        if not tables:
            print("[INFO] Aucune table trouvée — base déjà vide.")
        else:
            print(f"[INFO] Tables trouvées : {', '.join(tables)}")
            confirm = input("\nSupprimer TOUTES ces tables sur Railway ? (oui/non) : ").strip().lower()
            if confirm == "oui":
                # Désactiver les foreign keys le temps de supprimer
                cur.execute("SET session_replication_role = replica;")
                for table in tables:
                    cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                    print(f"  ✓ Table '{table}' supprimée")
                cur.execute("SET session_replication_role = DEFAULT;")
                print("[OK] Toutes les tables supprimées sur Railway.")
                print("[INFO] Elles seront recréées automatiquement au prochain démarrage de l'app.")
            else:
                print("[ANNULÉ] Serveur non modifié.")

        cur.close()
        conn.close()

    except ImportError:
        print("[ERREUR] psycopg2 non installé. Lancez : pip install psycopg2-binary")
    except Exception as e:
        print(f"[ERREUR] Connexion PostgreSQL : {e}")

# ─── 2. RESET SQLITE LOCAL ────────────────────────────
print("\n=== RESET LOCAL (SQLite) ===")
script_dir = os.path.dirname(os.path.abspath(__file__))
sqlite_paths = [
    os.path.join(script_dir, "instance", "financespro.db"),
    os.path.join(script_dir, "financespro.db"),
]

found_sqlite = False
for db_path in sqlite_paths:
    if os.path.exists(db_path):
        found_sqlite = True
        print(f"[INFO] Base SQLite trouvée : {db_path}")
        confirm2 = input("Supprimer la base SQLite locale ? (oui/non) : ").strip().lower()
        if confirm2 == "oui":
            try:
                os.remove(db_path)
                print(f"  ✓ Fichier supprimé : {db_path}")
            except Exception as e:
                print(f"  [ERREUR] {e}")
        else:
            print("[ANNULÉ] SQLite non modifié.")

if not found_sqlite:
    print("[SKIP] Aucune base SQLite locale trouvée.")

# ─── 3. RESET PYCACHE ─────────────────────────────────
print("\n=== NETTOYAGE CACHE PYTHON ===")
import shutil
for root, dirs, files in os.walk(script_dir):
    for d in dirs:
        if d == "__pycache__":
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)
            print(f"  ✓ Supprimé : {os.path.join(root, d)}")

# ─── 4. INSTRUCTIONS LOCALSTORAGE ─────────────────────
print("""
=== RESET NAVIGATEUR (localStorage) ===
Pour effacer les données locales du navigateur :

  Option A : Ouvrez http://localhost:5000 → F12 (DevTools)
             → Console → collez cette commande :
             localStorage.clear(); location.reload();

  Option B : Utilisez le script reset_local.js inclus
             (ouvrir reset_local.html dans le navigateur)
""")

print("\n✅ Reset terminé. Relancez l'application avec lancer_financespro.bat")
input("\nAppuyez sur Entrée pour fermer...")
