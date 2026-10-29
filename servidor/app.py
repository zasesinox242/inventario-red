"""API mínima del inventario de red (Fase 1: solo comprueba que el servicio vive)."""
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api/v1/salud")
def salud():
    """Endpoint de salud: responde si el servicio está activo."""
    return jsonify({"estado": "ok"})


if __name__ == "__main__":
    # 127.0.0.1: solo acepta conexiones de esta PC (y de la VM por NAT).
    app.run(host="127.0.0.1", port=5000)