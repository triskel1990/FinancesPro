# FinancesPro 💰
**Application de gestion financière personnelle — Offline-first avec sync cloud**

---

## 🗂️ Structure du projet

```
financespro/
├── app.py               ← Application Flask principale
├── requirements.txt     ← Dépendances Python
├── Procfile             ← Configuration Railway (déploiement)
├── README.md            ← Ce fichier
└── templates/
    ├── login.html       ← Page de connexion
    └── app.html         ← Interface principale
```

---

## 🖥️ INSTALLATION EN LOCAL (Windows)

### Étape 1 — Installer Python
Télécharger Python 3.11+ sur https://python.org/downloads
→ Cocher **"Add Python to PATH"** lors de l'installation

### Étape 2 — Préparer le projet
```bash
# Ouvrir le dossier du projet dans le terminal (cmd ou PowerShell)
cd C:\chemin\vers\financespro

# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
venv\Scripts\activate        # Windows CMD
# ou
venv\Scripts\Activate.ps1    # PowerShell
```

### Étape 3 — Installer les dépendances
```bash
pip install -r requirements.txt
```

### Étape 4 — Lancer l'application
```bash
python app.py
```

### Étape 5 — Ouvrir dans le navigateur
→ http://localhost:5000

### Première utilisation
1. Aller sur http://localhost:5000/login
2. Cliquer **"Créer un compte"**
3. Créer le 1er compte (il sera automatiquement **Admin**)
4. Se connecter et configurer les revenus/dépenses

### Lancer rapidement chaque jour (Windows)
Créer un fichier `demarrer.bat` dans le dossier :
```bat
@echo off
cd /d C:\chemin\vers\financespro
call venv\Scripts\activate
python app.py
pause
```
Double-cliquer dessus pour lancer.

---

## 📱 ACCÈS DEPUIS TÉLÉPHONE (même réseau Wi-Fi)

1. Trouver l'adresse IP locale de ton PC :
   - Windows : `ipconfig` dans le terminal → chercher **IPv4 Address** (ex: 192.168.1.5)

2. Ouvrir sur le téléphone :
   → http://192.168.1.5:5000

---

## ☁️ DÉPLOIEMENT SUR RAILWAY (cloud gratuit)

### Étape 1 — Créer un compte Railway
→ https://railway.app (connexion avec GitHub)

### Étape 2 — Préparer le code sur GitHub
```bash
git init
git add .
git commit -m "FinancesPro initial"
# Créer un repo sur github.com, puis :
git remote add origin https://github.com/TON_USERNAME/financespro.git
git push -u origin main
```

### Étape 3 — Déployer sur Railway
1. Sur railway.app → **New Project** → **Deploy from GitHub repo**
2. Sélectionner ton repo `financespro`
3. Railway détecte automatiquement le `Procfile` et déploie

### Étape 4 — Configurer les variables d'environnement
Dans Railway → Variables → Ajouter :
```
SECRET_KEY = une-chaine-secrete-longue-et-aleatoire-ici-!@#$%
```

### Étape 5 — Obtenir l'URL publique
Railway génère une URL du type : https://financespro-production.railway.app

---

## 🔄 FONCTIONNEMENT DE LA SYNCHRONISATION

```
┌─────────────────────────────────────────────────────────┐
│                   OFFLINE-FIRST SYNC                     │
│                                                          │
│  PC local (Flask)          Cloud (Railway)               │
│  ├─ SQLite locale          ├─ SQLite cloud               │
│  ├─ Travaille toujours     ├─ Accessible partout         │
│  └─ Sync auto quand        └─ Reçoit les données         │
│     connexion revient          et envoie les siennes     │
│                                                          │
│  RÈGLE : La version avec le timestamp le plus récent     │
│           gagne en cas de conflit                        │
└─────────────────────────────────────────────────────────┘
```

- **Sans internet** : L'appli fonctionne normalement, tout est sauvegardé localement
- **Connexion rétablie** : Sync automatique déclenchée, notification affichée
- **Bouton manuel** : "🔄 Synchroniser" dans la barre latérale
- **Multi-appareils** : PC + téléphone + cloud restent synchronisés

---

## 👥 GESTION DES UTILISATEURS

| Rôle    | Droits |
|---------|--------|
| Admin   | Tout faire + gérer les utilisateurs |
| Lecteur | Voir et modifier ses propres données |

- Le **1er compte créé** est toujours Admin
- L'Admin peut créer/supprimer des comptes depuis Paramètres

---

## 💡 CONSEILS D'UTILISATION

1. **Chaque mois** : Saisir les montants dans "Revenus" puis "Dépenses"
2. **Cocher "Payé"** au fur et à mesure des paiements
3. **Dettes** : Enregistrer une fois, puis cliquer "+ Paiement" chaque mois
4. **Statistiques** : Consultables après 2-3 mois de données
5. **Taux** : Modifier dans la sidebar ou les Paramètres à tout moment

---

## 🛠️ EN CAS DE PROBLÈME

```bash
# Réinstaller les dépendances
pip install -r requirements.txt --upgrade

# Réinitialiser la base de données (ATTENTION : efface tout)
del financespro.db   # Windows
python app.py        # Recrée la base

# Voir les erreurs
python app.py        # Les erreurs s'affichent dans le terminal
```
