"""API del inventario de red.

Fase 3.3: roles. El lector consulta; el admin además puede modificar.
"""
import json
import os
import secrets
import time
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Rutas absolutas basadas en la ubicación de este archivo.
BASE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE, "certs", "cert.pem")
CLAVE = os.path.join(BASE, "certs", "key.pem")
ARCHIVO_DATOS = os.path.join(BASE, "dispositivos.json")

# Las claves vienen del entorno: nunca se escriben en el código ni en Git.
CLAVE_ADMIN = os.environ.get("API_CLAVE_ADMIN")
CLAVE_LECTOR = os.environ.get("API_CLAVE_LECTOR")
if not CLAVE_ADMIN or not CLAVE_LECTOR:
    raise SystemExit("Define API_CLAVE_ADMIN y API_CLAVE_LECTOR antes de iniciar.")

# Solo se guarda el hash de la clave, no la clave en texto plano.
USUARIOS = {
    "admin": {"hash": generate_password_hash(CLAVE_ADMIN, method="pbkdf2:sha256"), "rol": "admin"},
    "lector": {"hash": generate_password_hash(CLAVE_LECTOR, method="pbkdf2:sha256"), "rol": "lector"},
}

DURACION_TOKEN = 900  # segundos (15 minutos)
TOKENS = {}  # token -> {"usuario", "rol", "expira"}; vive en memoria
ESTADOS_VALIDOS = ("Reachable", "Unreachable")


def cargar_dispositivos():
    """Lee el inventario desde el archivo JSON y lo devuelve como lista."""
    with open(ARCHIVO_DATOS, encoding="utf-8") as archivo:
        return json.load(archivo)


# El inventario se carga una vez al arrancar; los cambios viven en memoria.
DISPOSITIVOS = cargar_dispositivos()


def requiere_token(funcion):
    """Decorador: solo deja pasar si hay un token válido y vigente (si no, 401)."""
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        token = request.headers.get("X-Auth-Token")
        sesion = TOKENS.get(token)
        if sesion is None or sesion["expira"] < time.time():
            return jsonify({"error": "Token ausente, inválido o vencido"}), 401
        g.sesion = sesion  # queda disponible para el resto de la petición
        return funcion(*args, **kwargs)
    return envoltura


def requiere_rol(rol_necesario):
    """Decorador: exige un rol concreto (si no lo tiene, 403)."""
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            if g.sesion["rol"] != rol_necesario:
                return jsonify({"error": "No tienes permiso para esta acción"}), 403
            return funcion(*args, **kwargs)
        return envoltura
    return decorador


@app.errorhandler(404)
def no_encontrado(_error):
    """Responde en JSON cuando la ruta no existe."""
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.route("/api/v1/salud")
def salud():
    """Endpoint de salud: público, responde si el servicio está activo."""
    return jsonify({"estado": "ok"})


@app.route("/api/v1/auth/token", methods=["POST"])
def emitir_token():
    """Recibe usuario y clave (Basic Auth) y devuelve un token temporal."""
    credenciales = request.authorization
    cabecera = {"WWW-Authenticate": 'Basic realm="inventario"'}
    if credenciales is None:
        return jsonify({"error": "Se requieren credenciales (Basic Auth)"}), 401, cabecera

    usuario = USUARIOS.get(credenciales.username)
    if usuario is None or not check_password_hash(usuario["hash"], credenciales.password or ""):
        return jsonify({"error": "Usuario o clave incorrectos"}), 401, cabecera

    token = secrets.token_hex(16)
    TOKENS[token] = {
        "usuario": credenciales.username,
        "rol": usuario["rol"],
        "expira": time.time() + DURACION_TOKEN,
    }
    return jsonify({"token": token, "expira_en": DURACION_TOKEN, "rol": usuario["rol"]})


@app.route("/api/v1/dispositivos")
@requiere_token
def listar_dispositivos():
    """Devuelve todos los dispositivos del inventario."""
    return jsonify({"total": len(DISPOSITIVOS), "dispositivos": DISPOSITIVOS})


@app.route("/api/v1/dispositivos/<int:id_dispositivo>")
@requiere_token
def obtener_dispositivo(id_dispositivo):
    """Devuelve un dispositivo por su id, o 404 si no existe."""
    for dispositivo in DISPOSITIVOS:
        if dispositivo["id"] == id_dispositivo:
            return jsonify(dispositivo)
    return jsonify({"error": "Dispositivo no encontrado"}), 404


@app.route("/api/v1/dispositivos/<int:id_dispositivo>", methods=["PATCH"])
@requiere_token
@requiere_rol("admin")
def actualizar_dispositivo(id_dispositivo):
    """Cambia el estado de un dispositivo. Solo el rol admin (403 si no)."""
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict) or cuerpo.get("estado") not in ESTADOS_VALIDOS:
        return jsonify({"error": "Cuerpo inválido: se espera "
                                 '{"estado": "Reachable" o "Unreachable"}'}), 400

    for dispositivo in DISPOSITIVOS:
        if dispositivo["id"] == id_dispositivo:
            dispositivo["estado"] = cuerpo["estado"]
            return jsonify(dispositivo)
    return jsonify({"error": "Dispositivo no encontrado"}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, ssl_context=(CERT, CLAVE))