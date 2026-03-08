"""
FinancesPro — Application de gestion financière personnelle
Architecture offline-first avec synchronisation cloud
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import os
import json
import uuid

# Charger .env en local (ignoré si la variable est déjà définie, ex: sur Railway)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'changez-moi-en-production-!@#$%')
app.config['REMEMBER_COOKIE_DURATION'] = 60 * 60 * 24 * 30  # 30 jours
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# ── Détection base de données ──
# Sur Railway (DATABASE_URL définie) : PostgreSQL obligatoire, pas de fallback SQLite
# En local sans internet : fallback SQLite automatique
import time as _time

_sqlite_path  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'financespro.db')
_sqlite_url   = 'sqlite:///' + _sqlite_path
_postgres_url = os.environ.get('DATABASE_URL', '')
# Normaliser l'URL et forcer pg8000 (pur Python, pas de libpq nécessaire)
if _postgres_url.startswith('postgres://'):
    _postgres_url = _postgres_url.replace('postgres://', 'postgresql+pg8000://', 1)
elif _postgres_url.startswith('postgresql://'):
    _postgres_url = _postgres_url.replace('postgresql://', 'postgresql+pg8000://', 1)

# Si DATABASE_URL est définie → on est sur Railway → PostgreSQL obligatoire
_force_postgres = bool(_postgres_url)
_using_sqlite   = False
_last_pg_check  = 0.0
_pg_check_ttl   = 30

def _test_postgres():
    if 'pg8000' not in _postgres_url:
        return False
    try:
        import pg8000
        from urllib.parse import urlparse
        p = urlparse(_postgres_url.replace('postgresql+pg8000://', 'postgresql://'))
        conn = pg8000.connect(
            host=p.hostname, port=p.port or 5432,
            user=p.username, password=p.password,
            database=p.path.lstrip('/'), timeout=5
        )
        conn.close()
        return True
    except Exception:
        return False

def _get_db_url():
    """En local : bascule dynamique. Sur Railway : toujours PostgreSQL."""
    global _last_pg_check, _using_sqlite
    if _force_postgres:
        return _postgres_url  # Railway : jamais de SQLite
    now = _time.time()
    if now - _last_pg_check >= _pg_check_ttl:
        _last_pg_check = now
        pg_ok = _test_postgres()
        if pg_ok and _using_sqlite:
            print('[DB] PostgreSQL de nouveau joignable — bascule online ✓')
            _using_sqlite = False
            app.config['SQLALCHEMY_DATABASE_URI'] = _postgres_url
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300, 'connect_args': {}}
            try: db.engine.dispose()
            except: pass
        elif not pg_ok and not _using_sqlite:
            print('[DB] PostgreSQL injoignable — bascule SQLite local')
            _using_sqlite = True
            app.config['SQLALCHEMY_DATABASE_URI'] = _sqlite_url
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300, 'connect_args': {}}
            try: db.engine.dispose()
            except: pass
    return _sqlite_url if _using_sqlite else _postgres_url

# ── Initialisation DB au démarrage ──
if _force_postgres:
    # Railway : PostgreSQL direct, pas de test préalable
    _using_sqlite   = False
    _initial_db_url = _postgres_url
    print('[DB] Mode Railway — PostgreSQL ✓')
else:
    # Local : tester PostgreSQL, sinon SQLite
    _last_pg_check = _time.time()
    if _test_postgres():
        _using_sqlite   = False
        _initial_db_url = _postgres_url
        print('[DB] PostgreSQL connecté ✓')
    else:
        _using_sqlite   = True
        _initial_db_url = _sqlite_url
        os.makedirs(os.path.dirname(_sqlite_path), exist_ok=True)
        print('[DB] PostgreSQL injoignable — mode SQLite local')

app.config['SQLALCHEMY_DATABASE_URI'] = _initial_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle':  300,
    'connect_args':  {},
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)

@app.before_request
def check_db_mode():
    if not _force_postgres:  # seulement en local
        _get_db_url()
login_manager.login_view = 'login'

# ─────────────────────────────────────────
# MODÈLES
# ─────────────────────────────────────────

class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=True)
    password   = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.String(20), default='viewer')  # admin / viewer
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    taux        = db.Column(db.Integer, default=2300)
    profile_pic = db.Column(db.Text, nullable=True)  # photo base64

    revenus    = db.relationship('Revenu', backref='user', lazy=True, cascade='all,delete')
    depenses   = db.relationship('DepenseTemplate', backref='user', lazy=True, cascade='all,delete')
    entrees    = db.relationship('EntreeMensuelle', backref='user', lazy=True, cascade='all,delete')
    dettes     = db.relationship('Dette', backref='user', lazy=True, cascade='all,delete')
    categories = db.relationship('Categorie', backref='user', lazy=True, cascade='all,delete')

class Revenu(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    icon       = db.Column(db.String(10), default='💰')
    type       = db.Column(db.String(30), default='salaire')
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Categorie(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(80), nullable=False)
    icon       = db.Column(db.String(10), default='📦')
    slug       = db.Column(db.String(80))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class DepenseTemplate(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    icon       = db.Column(db.String(10), default='📦')
    cat_slug   = db.Column(db.String(80))
    type       = db.Column(db.String(20), default='fixed')  # fixed / variable
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class EntreeMensuelle(db.Model):
    """Données financières d'un mois donné pour un utilisateur"""
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mois_key   = db.Column(db.String(7), nullable=False)   # format: "2025-06"
    data_json  = db.Column(db.Text, nullable=False, default='{}')
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('user_id', 'mois_key'),)

class Dette(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    bank       = db.Column(db.String(80))
    total      = db.Column(db.Float, default=0)
    monthly    = db.Column(db.Float, default=0)
    paid       = db.Column(db.Float, default=0)
    notes      = db.Column(db.String(255))
    done       = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class SyncLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'))
    action     = db.Column(db.String(50))
    table_name = db.Column(db.String(50))
    record_id  = db.Column(db.String(36))
    timestamp  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

# ─────────────────────────────────────────
# DONNÉES PAR DÉFAUT
# ─────────────────────────────────────────

DEFAULT_CATEGORIES = [
    {'slug':'loyer',          'name':'Loyer',                    'icon':'🏠'},
    {'slug':'provision',      'name':'Provision',                'icon':'🏪'},
    {'slug':'nourriture',     'name':'Nourriture / Marché',      'icon':'🥩'},
    {'slug':'pain',           'name':'Pain & petit-déjeuner',    'icon':'🥖'},
    {'slug':'essence',        'name':'Essence',                  'icon':'⛽'},
    {'slug':'abonnement',     'name':'Abonnements',              'icon':'📱'},
    {'slug':'argent-poche',   'name':'Argent de poche',          'icon':'👝'},
    {'slug':'salaire-menage', 'name':'Salaire ménagère',         'icon':'🧹'},
    {'slug':'transport-menage','name':'Transport ménagère',      'icon':'🚌'},
    {'slug':'epargne',        'name':'Épargne',                  'icon':'💎'},
    {'slug':'sante',          'name':'Santé',                    'icon':'🏥'},
    {'slug':'education',      'name':'Éducation / Frais scolaires','icon':'📚'},
    {'slug':'electricite',    'name':'Électricité / Eau',        'icon':'💡'},
    {'slug':'loisirs',        'name':'Loisirs',                  'icon':'🎉'},
    {'slug':'autres',         'name':'Autres',                   'icon':'📦'},
]

DEFAULT_REVENUS = [
    {'name':'Prime du Sénat',               'icon':'🏛️', 'type':'prime'},
    {'name':'Salaire Fonction Publique',     'icon':'🏢', 'type':'salaire'},
    {'name':'Salaire DGM',                   'icon':'✈️', 'type':'salaire'},
    {'name':'Frais de Fonctionnement',       'icon':'📋', 'type':'frais'},
    {'name':'Bénéfices Lon Bar & Terrasse',  'icon':'🍺', 'type':'benefice'},
]

DEFAULT_DEPENSES = [
    {'name':'Loyer',                     'icon':'🏠', 'cat':'loyer',           'type':'fixed'},
    {'name':'Provision alimentaire',     'icon':'🏪', 'cat':'provision',        'type':'fixed'},
    {'name':'Nourriture quotidienne',    'icon':'🥩', 'cat':'nourriture',       'type':'variable'},
    {'name':'Pain & petit-déjeuner',     'icon':'🥖', 'cat':'pain',             'type':'variable'},
    {'name':'Essence',                   'icon':'⛽', 'cat':'essence',          'type':'variable'},
    {'name':'Abonnements',               'icon':'📱', 'cat':'abonnement',       'type':'fixed'},
    {'name':'Argent de poche',           'icon':'👝', 'cat':'argent-poche',     'type':'variable'},
    {'name':'Salaire ménagère',          'icon':'🧹', 'cat':'salaire-menage',   'type':'fixed'},
    {'name':'Transport ménagère',        'icon':'🚌', 'cat':'transport-menage', 'type':'fixed'},
    {'name':'Épargne mensuelle',         'icon':'💎', 'cat':'epargne',          'type':'fixed'},
]

def init_user_defaults(user):
    # Créer uniquement les catégories par défaut.
    # Les sources de revenus et les dépenses sont laissées vierges :
    # l'utilisateur les ajoute lui-même selon sa situation.
    for c in DEFAULT_CATEGORIES:
        cat = Categorie(user_id=user.id, name=c['name'], icon=c['icon'], slug=c['slug'])
        db.session.add(cat)
    db.session.commit()

# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        user = User.query.filter_by(username=data.get('username')).first()
        if user and check_password_hash(user.password, data.get('password','')):
            login_user(user, remember=True)
            if request.is_json:
                return jsonify({'ok': True, 'role': user.role})
            return redirect(url_for('index'))
        if request.is_json:
            return jsonify({'ok': False, 'error': 'Identifiants incorrects'}), 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/register', methods=['POST'])
def register():
    # Chaque personne peut créer son propre compte admin librement
    data = request.get_json()
    if not data.get('username') or not data.get('password'):
        return jsonify({'ok': False, 'error': 'Nom d\'utilisateur et mot de passe requis'}), 400
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'ok': False, 'error': 'Nom d\'utilisateur déjà pris'}), 400
    user = User(
        username=data.get('username'),
        email=data.get('email',''),
        password=generate_password_hash(data.get('password','')),
        role='admin'  # tout nouveau compte est admin de ses propres données
    )
    db.session.add(user)
    db.session.commit()
    init_user_defaults(user)
    return jsonify({'ok': True, 'id': user.id, 'role': 'admin'})

# ─────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template('app.html', user=current_user)

# ─────────────────────────────────────────
# API — TAUX
# ─────────────────────────────────────────

@app.route('/api/taux', methods=['GET','PUT'])
@login_required
def api_taux():
    if request.method == 'PUT':
        data = request.get_json()
        current_user.taux = int(data.get('taux', 2300))
        db.session.commit()
        return jsonify({'ok': True, 'taux': current_user.taux})
    return jsonify({'taux': current_user.taux})

# ─────────────────────────────────────────
# API — REVENUS (templates)
# ─────────────────────────────────────────

@app.route('/api/revenus', methods=['GET','POST'])
@login_required
def api_revenus():
    if request.method == 'POST':
        d = request.get_json()
        rev = Revenu(user_id=current_user.id, name=d['name'], icon=d.get('icon','💰'), type=d.get('type','salaire'))
        db.session.add(rev)
        db.session.commit()
        return jsonify({'ok':True, 'id': rev.id})
    revs = Revenu.query.filter_by(user_id=current_user.id).all()
    return jsonify([{'id':r.id,'name':r.name,'icon':r.icon,'type':r.type} for r in revs])

@app.route('/api/revenus/<rid>', methods=['PUT','DELETE'])
@login_required
def api_revenu(rid):
    rev = Revenu.query.filter_by(id=rid, user_id=current_user.id).first_or_404()
    if request.method == 'DELETE':
        db.session.delete(rev)
        db.session.commit()
        return jsonify({'ok': True})
    d = request.get_json()
    rev.name = d.get('name', rev.name)
    rev.icon = d.get('icon', rev.icon)
    rev.type = d.get('type', rev.type)
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────
# API — CATÉGORIES
# ─────────────────────────────────────────

@app.route('/api/categories', methods=['GET','POST'])
@login_required
def api_categories():
    if request.method == 'POST':
        d = request.get_json()
        cat = Categorie(user_id=current_user.id, name=d['name'], icon=d.get('icon','📦'), slug=d.get('slug', d['name'].lower().replace(' ','-')))
        db.session.add(cat)
        db.session.commit()
        return jsonify({'ok':True,'id':cat.id})
    cats = Categorie.query.filter_by(user_id=current_user.id).all()
    return jsonify([{'id':c.id,'name':c.name,'icon':c.icon,'slug':c.slug} for c in cats])

@app.route('/api/categories/<cid>', methods=['DELETE'])
@login_required
def api_categorie(cid):
    cat = Categorie.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────
# API — DÉPENSES TEMPLATES
# ─────────────────────────────────────────

@app.route('/api/depenses-templates', methods=['GET','POST'])
@login_required
def api_dep_templates():
    if request.method == 'POST':
        d = request.get_json()
        dep = DepenseTemplate(user_id=current_user.id, name=d['name'], icon=d.get('icon','📦'), cat_slug=d.get('cat_slug','autres'), type=d.get('type','fixed'))
        db.session.add(dep)
        db.session.commit()
        return jsonify({'ok':True,'id':dep.id})
    deps = DepenseTemplate.query.filter_by(user_id=current_user.id).all()
    return jsonify([{'id':d.id,'name':d.name,'icon':d.icon,'cat_slug':d.cat_slug,'type':d.type} for d in deps])

@app.route('/api/depenses-templates/<did>', methods=['DELETE'])
@login_required
def api_dep_template(did):
    dep = DepenseTemplate.query.filter_by(id=did, user_id=current_user.id).first_or_404()
    db.session.delete(dep)
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────
# API — ENTRÉES MENSUELLES (cœur des données)
# ─────────────────────────────────────────

@app.route('/api/mois/<mois_key>', methods=['GET','PUT'])
@login_required
def api_mois(mois_key):
    entree = EntreeMensuelle.query.filter_by(user_id=current_user.id, mois_key=mois_key).first()
    if request.method == 'PUT':
        data = request.get_json()
        if entree:
            existing = json.loads(entree.data_json)
            incoming_ts = data.get('updated_at', '')
            existing_ts = existing.get('updated_at', '')
            if incoming_ts >= existing_ts:
                entree.data_json = json.dumps(data)
                entree.updated_at = datetime.now(timezone.utc)
        else:
            entree = EntreeMensuelle(user_id=current_user.id, mois_key=mois_key, data_json=json.dumps(data))
            db.session.add(entree)
        db.session.commit()
        return jsonify({'ok': True, 'updated_at': entree.updated_at.isoformat()})
    if entree:
        return jsonify(json.loads(entree.data_json))
    revs = Revenu.query.filter_by(user_id=current_user.id).all()
    deps = DepenseTemplate.query.filter_by(user_id=current_user.id).all()
    default = {
        'mois_key': mois_key,
        'updated_at': '',
        'revenus': [{'id':r.id,'name':r.name,'icon':r.icon,'type':r.type,'amount':0} for r in revs],
        'depenses': [{'id':d.id,'name':d.name,'icon':d.icon,'cat_slug':d.cat_slug,'type':d.type,'amount':0,'paid':False} for d in deps],
    }
    return jsonify(default)

@app.route('/api/mois', methods=['GET'])
@login_required
def api_mois_list():
    entries = EntreeMensuelle.query.filter_by(user_id=current_user.id).order_by(EntreeMensuelle.mois_key.desc()).all()
    return jsonify([{'mois_key':e.mois_key,'updated_at':e.updated_at.isoformat()} for e in entries])

# ─────────────────────────────────────────
# API — DETTES
# ─────────────────────────────────────────

@app.route('/api/dettes', methods=['GET','POST'])
@login_required
def api_dettes():
    if request.method == 'POST':
        d = request.get_json()
        dette = Dette(user_id=current_user.id, name=d['name'], bank=d.get('bank',''), total=d.get('total',0), monthly=d.get('monthly',0), paid=d.get('paid',0), notes=d.get('notes',''))
        db.session.add(dette)
        db.session.commit()
        return jsonify({'ok':True,'id':dette.id})
    dettes = Dette.query.filter_by(user_id=current_user.id).all()
    return jsonify([{'id':d.id,'name':d.name,'bank':d.bank,'total':d.total,'monthly':d.monthly,'paid':d.paid,'notes':d.notes,'done':d.done,'updated_at':d.updated_at.isoformat()} for d in dettes])

@app.route('/api/dettes/<did>', methods=['PUT','DELETE'])
@login_required
def api_dette(did):
    dette = Dette.query.filter_by(id=did, user_id=current_user.id).first_or_404()
    if request.method == 'DELETE':
        db.session.delete(dette)
        db.session.commit()
        return jsonify({'ok': True})
    d = request.get_json()
    for field in ['name','bank','total','monthly','paid','notes','done']:
        if field in d:
            setattr(dette, field, d[field])
    db.session.commit()
    return jsonify({'ok': True, 'updated_at': dette.updated_at.isoformat()})

# ─────────────────────────────────────────
# API — SYNC (offline-first)
# ─────────────────────────────────────────

@app.route('/api/sync', methods=['POST'])
@login_required
def api_sync():
    """
    Reçoit toutes les données locales, merge avec le serveur,
    retourne l'état complet synchronisé.
    """
    payload = request.get_json()
    merged = {'mois': {}, 'dettes': [], 'taux': current_user.taux}

    if payload.get('taux'):
        current_user.taux = payload['taux']

    for mois_key, mois_data in payload.get('mois', {}).items():
        entree = EntreeMensuelle.query.filter_by(user_id=current_user.id, mois_key=mois_key).first()
        incoming_ts = mois_data.get('updated_at','')
        if entree:
            existing = json.loads(entree.data_json)
            existing_ts = existing.get('updated_at','')
            if incoming_ts >= existing_ts:
                entree.data_json = json.dumps(mois_data)
                entree.updated_at = datetime.now(timezone.utc)
            merged['mois'][mois_key] = json.loads(entree.data_json)
        else:
            entree = EntreeMensuelle(user_id=current_user.id, mois_key=mois_key, data_json=json.dumps(mois_data))
            db.session.add(entree)
            merged['mois'][mois_key] = mois_data

    all_entries = EntreeMensuelle.query.filter_by(user_id=current_user.id).all()
    for e in all_entries:
        if e.mois_key not in merged['mois']:
            merged['mois'][e.mois_key] = json.loads(e.data_json)

    for d_data in payload.get('dettes', []):
        dette = Dette.query.filter_by(id=d_data.get('id'), user_id=current_user.id).first()
        incoming_ts = d_data.get('updated_at','')
        if dette:
            existing_ts = dette.updated_at.isoformat()
            if incoming_ts >= existing_ts:
                for f in ['name','bank','total','monthly','paid','notes','done']:
                    if f in d_data: setattr(dette, f, d_data[f])
        else:
            dette = Dette(id=d_data.get('id', str(uuid.uuid4())), user_id=current_user.id,
                name=d_data.get('name',''), bank=d_data.get('bank',''),
                total=d_data.get('total',0), monthly=d_data.get('monthly',0),
                paid=d_data.get('paid',0), notes=d_data.get('notes',''), done=d_data.get('done',False))
            db.session.add(dette)

    db.session.commit()
    all_dettes = Dette.query.filter_by(user_id=current_user.id).all()
    merged['dettes'] = [{'id':d.id,'name':d.name,'bank':d.bank,'total':d.total,'monthly':d.monthly,'paid':d.paid,'notes':d.notes,'done':d.done,'updated_at':d.updated_at.isoformat()} for d in all_dettes]

    log = SyncLog(user_id=current_user.id, action='sync', table_name='full', record_id='*')
    db.session.add(log)
    db.session.commit()

    return jsonify({'ok': True, 'synced_at': datetime.now(timezone.utc).isoformat(), **merged})

# ─────────────────────────────────────────
# API — UTILISATEURS (admin)
# ─────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
@login_required
def api_users():
    if current_user.role != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    users = User.query.all()
    return jsonify([{'id':u.id,'username':u.username,'email':u.email,'role':u.role,'created_at':u.created_at.isoformat()} for u in users])

@app.route('/api/users/<int:uid>', methods=['DELETE','PUT'])
@login_required
def api_user(uid):
    if current_user.role != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    user = User.query.get_or_404(uid)
    if request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return jsonify({'ok': True})
    d = request.get_json()
    if 'role' in d: user.role = d['role']
    if 'password' in d and d['password']: user.password = generate_password_hash(d['password'])
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────
# API — INFOS SESSION
# ─────────────────────────────────────────

@app.route('/api/me')
@login_required
def api_me():
    return jsonify({
        'id':          current_user.id,
        'username':    current_user.username,
        'email':       current_user.email or '',
        'role':        current_user.role,
        'taux':        current_user.taux,
        'profile_pic': current_user.profile_pic or '',
    })

@app.route('/api/me', methods=['PUT', 'DELETE'])
@login_required
def api_me_update():
    if request.method == 'DELETE':
        try:
            user = current_user._get_current_object()
            uid = user.id
            # Supprimer SyncLog manuellement (pas de cascade définie)
            SyncLog.query.filter_by(user_id=uid).delete()
            db.session.flush()
            # Supprimer le compte (cascade supprime le reste)
            db.session.delete(user)
            db.session.commit()
            logout_user()
            return jsonify({'ok': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'ok': False, 'error': str(e)}), 500
    data = request.get_json()
    # Vérification mot de passe actuel si changement demandé
    if data.get('new_password'):
        if not check_password_hash(current_user.password, data.get('current_password', '')):
            return jsonify({'ok': False, 'error': 'Mot de passe actuel incorrect'}), 400
        current_user.password = generate_password_hash(data['new_password'])
    if data.get('username'):
        existing = User.query.filter_by(username=data['username']).first()
        if existing and existing.id != current_user.id:
            return jsonify({'ok': False, 'error': "Ce nom d'utilisateur est déjà pris"}), 400
        current_user.username = data['username']
    if 'email' in data:
        current_user.email = data['email']
    db.session.commit()
    return jsonify({'ok': True, 'username': current_user.username, 'email': current_user.email})

@app.route('/api/me/profile-pic', methods=['PUT', 'DELETE'])
@login_required
def api_profile_pic():
    if request.method == 'DELETE':
        current_user.profile_pic = None
        db.session.commit()
        return jsonify({'ok': True})
    data = request.get_json()
    pic = data.get('profile_pic', '')
    if len(pic) > 3_000_000:
        return jsonify({'ok': False, 'error': 'Image trop grande (max 2 Mo)'}), 400
    current_user.profile_pic = pic
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────
# API — MODE (online/offline)
# ─────────────────────────────────────────

@app.route('/api/mode')
def api_mode():
    """Indique au frontend quel mode la base utilise (mis à jour dynamiquement)."""
    _get_db_url()  # force la vérification si TTL expiré
    return jsonify({
        'mode': 'sqlite' if _using_sqlite else 'postgresql',
        'offline': _using_sqlite
    })

# ─────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────

with app.app_context():
    db.create_all()
    if _using_sqlite:
        count = User.query.count()
        if count == 0:
            print('[DB] Mode offline — aucun compte local trouvé.')
            print('[DB] Créez un compte sur http://localhost:5000 ou reconnectez internet.')
        else:
            print(f'[DB] Mode offline — {count} compte(s) local/locaux trouvé(s) ✓')
    # Créer aussi les tables SQLite en avance pour le mode offline
    if not _using_sqlite:
        try:
            from sqlalchemy import create_engine
            _offline_engine = create_engine(_sqlite_url)
            db.metadata.create_all(_offline_engine)
            _offline_engine.dispose()
        except Exception:
            pass

if __name__ == '__main__':
    mode = 'OFFLINE (SQLite local)' if _using_sqlite else 'ONLINE (PostgreSQL Railway)'
    print(f'[FinancesPro] Démarrage en mode {mode}')
    app.run(debug=True, host='0.0.0.0', port=5000)
