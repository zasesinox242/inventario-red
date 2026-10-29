"""API del inventario de red.

Fase 3.1: endpoints de lectura del inventario (aún sin autenticación).
"""
import json
import os

from flask import Flask, jsonify

app = Flask(__name__)

# Rutas absolutas basadas en la ubicación de este archivo.
BASE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE, "certs", "cert.pem")
CLAVE = os.path.join(BASE, "certs", "key.pem")
ARCHIVO_DATOS = os.path.join(BASE, "dispositivos.json")


def cargar_dispositivos():
    """Lee el inventario desde el archivo JSON y lo devuelve como lista."""
    with open(ARCHIVO_DATOS, encoding="utf-8") as archivo:
        return json.load(archivo)


@app.errorhandler(404)
def no_encontrado(_error):
    """Responde en JSON cuando la ruta no existe."""
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.route("/api/v1/salud")
def salud():
    """Endpoint de salud: responde si el servicio está activo."""
    return jsonify({"estado": "ok"})


@app.route("/api/v1/dispositivos")
def listar_dispositivos():
    """Devuelve todos los dispositivos del inventario."""
    dispositivos = cargar_dispositivos()
    return jsonify({"total": len(dispositivos), "dispositivos": dispositivos})


@app.route("/api/v1/dispositivos/<int:id_dispositivo>")
def obtener_dispositivo(id_dispositivo):
    """Devuelve un dispositivo por su id, o 404 si no existe."""
    for dispositivo in cargar_dispositivos():
        if dispositivo["id"] == id_dispositivo:
            return jsonify(dispositivo)
    return jsonify({"error": "Dispositivo no encontrado"}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, ssl_context=(CERT, CLAVE))