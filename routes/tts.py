# routes/tts.py — Piper TTS local + recherche DuckDuckGo
import subprocess, os, tempfile, requests
from flask import Blueprint, request, jsonify, Response

tts_bp = Blueprint("tts", __name__)

PIPER_BIN   = os.environ.get("PIPER_PATH", "piper")
_BASE       = os.path.dirname(os.path.abspath(__file__))
PIPER_MODEL = os.environ.get(
    "PIPER_MODEL",
    os.path.join(_BASE, '..', 'piper_models', 'fr_FR-siwis-medium.onnx')
)

def piper_available():
    try:
        piper = os.path.normpath(PIPER_BIN)
        model = os.path.normpath(PIPER_MODEL)
        r = subprocess.run([piper, '--version'], capture_output=True, timeout=3)
        return r.returncode == 0 and os.path.exists(model)
    except Exception:
        return False

@tts_bp.route("/tts-ping", methods=["GET"])
def tts_ping():
    piper = os.path.normpath(PIPER_BIN)
    model = os.path.normpath(PIPER_MODEL)
    piper_exists = os.path.exists(piper)
    model_exists = os.path.exists(model)
    run_ok = False
    run_err = ""
    if piper_exists:
        try:
            r = subprocess.run([piper, '--version'], capture_output=True, timeout=3)
            run_ok = r.returncode == 0
            run_err = r.stderr.decode('utf-8', errors='replace')
        except Exception as e:
            run_err = str(e)
    # Chercher piper dans PATH si non trouvé
    import shutil
    piper_which = shutil.which('piper') or 'not in PATH'
    # Lister /opt/piper si existe
    opt_piper = []
    try:
        if os.path.exists('/opt/piper'):
            opt_piper = os.listdir('/opt/piper')
    except: pass

    if piper_exists and model_exists and run_ok:
        return jsonify({"ok": True, "engine": "piper", "model": os.path.basename(model)})
    return jsonify({
        "ok": False,
        "piper_path": piper,
        "piper_exists": piper_exists,
        "piper_which": piper_which,
        "opt_piper": opt_piper,
        "model_path": model,
        "model_exists": model_exists,
        "run_ok": run_ok,
        "run_err": run_err
    }), 503

@tts_bp.route("/tts", methods=["POST"])
def tts_piper():
    """Synthese vocale Piper — retourne WAV via fichier temporaire."""
    data = request.get_json()
    text = (data.get("text", "") if data else "").strip()
    if not text:
        return jsonify({"error": "Texte manquant"}), 400

    # Fichier temporaire pour la sortie WAV
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        piper = os.path.normpath(PIPER_BIN)
        model = os.path.normpath(PIPER_MODEL)
        result = subprocess.run(
            [piper, '--model', model, '--output_file', tmp_path],
            input=text.encode('utf-8'),
            capture_output=True,
            timeout=20
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')[:300]
            return jsonify({"error": f"Piper erreur: {err}"}), 500

        with open(tmp_path, 'rb') as f:
            wav_data = f.read()

        return Response(wav_data, mimetype='audio/wav')

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Piper timeout"}), 504
    except FileNotFoundError:
        return jsonify({"error": "Piper non installe"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: os.unlink(tmp_path)
        except: pass

@tts_bp.route("/search", methods=["POST"])
def search_proxy():
    """Proxy DuckDuckGo — recherche gratuite sans cle API."""
    data = request.get_json()
    query = (data.get("q", "") if data else "").strip()
    if not query:
        return jsonify({"error": "Query manquante"}), 400
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": "1",
                    "no_html": "1", "skip_disambig": "1", "kl": "fr-fr"},
            timeout=8,
            headers={"User-Agent": "FinancesPro/1.0"}
        )
        return jsonify(resp.json())
    except requests.exceptions.Timeout:
        return jsonify({"error": "Recherche timeout"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 502
