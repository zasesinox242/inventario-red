#!/usr/bin/env python3
"""Cliente del inventario de red (Fase 4.1).

Se autentica en la API por HTTPS, obtiene un token y muestra los dispositivos.
"""
import os
import sys

import requests

# Dirección de la API: el nombre apunta a la PC mediante /etc/hosts.
URL_BASE = "https://api-inventario:5000/api/v1"

# Certificado en el que confiamos (el de la API). Nunca se usa verify=False.
CARPETA = os.path.dirname(os.path.abspath(__file__))
CERTIFICADO = os.path.normpath(
    os.path.join(CARPETA, "..", "..", "servidor", "certs", "cert.pem")
)

TIMEOUT = 10  # segundos máximos de espera por petición


def obtener_token(usuario, clave):
    """Pide un token a la API con Basic Auth y lo devuelve como texto."""
    respuesta = requests.post(
        URL_BASE + "/auth/token",
        auth=(usuario, clave),
        verify=CERTIFICADO,
        timeout=TIMEOUT,
    )
    respuesta.raise_for_status()
    return respuesta.json()["token"]


def obtener_dispositivos(token):
    """Pide el inventario a la API usando el token y devuelve la lista."""
    respuesta = requests.get(
        URL_BASE + "/dispositivos",
        headers={"X-Auth-Token": token},
        verify=CERTIFICADO,
        timeout=TIMEOUT,
    )
    respuesta.raise_for_status()
    return respuesta.json()["dispositivos"]


def main():
    """Punto de entrada: lee credenciales del entorno y muestra el inventario."""
    usuario = os.environ.get("CLIENTE_USUARIO")
    clave = os.environ.get("CLIENTE_CLAVE")
    if not usuario or not clave:
        sys.exit("Define CLIENTE_USUARIO y CLIENTE_CLAVE antes de ejecutar.")

    token = obtener_token(usuario, clave)
    dispositivos = obtener_dispositivos(token)

    print(f"Dispositivos recibidos: {len(dispositivos)}")
    for d in dispositivos:
        print(f"{d['hostname']:<20} {d['ip']:<14} {d['estado']:<12} {d['version']}")


if __name__ == "__main__":
    main()