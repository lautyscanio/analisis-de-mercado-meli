"""Configuracion y constantes de entorno. Sin logica de negocio, solo lectura de .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Credenciales ML ------------------------------------------------
CLIENT_ID     = os.environ.get("ML_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "")
REDIRECT_URI  = "https://httpbin.org/get"   # ML redirige aca; el codigo queda visible en JSON

ML_AUTH_URL  = "https://auth.mercadolibre.com.ar/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ML_API       = "https://api.mercadolibre.com"
TOKEN_FILE   = Path(".ml_token.json")

# El debugger de Werkzeug (activado por debug=True) expone una consola interactiva
# con ejecucion de codigo remoto ante un traceback -- default apagado, se prende
# a proposito con FLASK_DEBUG=1 (ver checklist de seguridad del DPP de ML).
DEBUG = os.environ.get("FLASK_DEBUG", "") == "1"

PORT = int(os.environ.get("PORT", 5050))

# Historial de precios (SQLite local). No incluye sold_quantity: ese dato no esta
# disponible para publicaciones de terceros via API (solo scrapeando el HTML
# publico, algo que este proyecto descarta explicitamente, ver PROJECT_SPEC.md 7).
DB_PATH = Path("data/mercadata.db")
