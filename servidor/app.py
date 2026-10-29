"""API del inventario de red.

Fase 2: el servicio ahora usa HTTPS con un certificado autofirmado.
"""
import os

from flask import Flask, jsonify

app = Flask(__name__)

# Rutas absolutas basadas en la ubicación de este archivo, para que
# funcione sin importar desde qué carpeta se ejecute.
BASE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE, "certs", "cert.pem")
CLAVE = os.path.join(BASE, "certs", "key.pem")


@app.route("/api/v1/salud")
def salud():
    """Endpoint de salud: responde si el servicio está activo."""
    return jsonify({"estado": "ok"})


if __name__ == "__main__":
    # 127.0.0.1: la VM llega por NAT (10.0.2.2) y nadie más en la red.
    app.run(host="127.0.0.1", port=5000, ssl_context=(CERT, CLAVE))