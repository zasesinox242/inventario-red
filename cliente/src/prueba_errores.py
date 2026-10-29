#!/usr/bin/env python3
"""Pruebas manuales de errores de la API (evidencia para el informe).

Provoca cada tipo de error y muestra el mensaje claro que produce el cliente.
Requiere CLIENTE_CLAVE (clave del lector) y, opcionalmente, CLIENTE_CLAVE_ADMIN.
"""
import os
import sys

import inventario as inv


def intentar(titulo, accion):
    """Ejecuta una acción y muestra su resultado o el ErrorAPI que produce."""
    print(f"\n--- {titulo} ---")
    try:
        print(f"Respuesta: {accion()}")
    except inv.ErrorAPI as error:
        print(f"ErrorAPI: {error}")


def main():
    config = inv.leer_config(os.path.join(inv.CARPETA_DATOS, "config.yaml"))
    api = config["api"]
    api["certificado"] = os.path.join(inv.RAIZ, api["certificado"])
    # Valores cortos para que las pruebas no tarden demasiado.
    api = dict(api, timeout=2, reintentos=1, espera_reintento=1)

    clave_lector = os.environ.get("CLIENTE_CLAVE")
    clave_admin = os.environ.get("CLIENTE_CLAVE_ADMIN")
    if not clave_lector:
        sys.exit("Define CLIENTE_CLAVE (la clave del usuario lector).")

    # Errores de autenticación (401)
    intentar("401 - clave incorrecta",
             lambda: inv.obtener_token(api, "lector", "mala"))
    intentar("401 - petición sin token",
             lambda: inv.llamar_api(api, "GET", "/dispositivos"))

    # Errores de cliente con un token válido
    token_lector = inv.obtener_token(api, "lector", clave_lector)
    intentar("404 - dispositivo inexistente",
             lambda: inv.llamar_api(api, "GET", "/dispositivos/99", token=token_lector))
    intentar("403 - el lector intenta modificar",
             lambda: inv.llamar_api(api, "PATCH", "/dispositivos/4",
                                    token=token_lector, cuerpo={"estado": "Reachable"}))
    intentar("405 - método no permitido",
             lambda: inv.llamar_api(api, "DELETE", "/dispositivos/4", token=token_lector))

    if clave_admin:
        token_admin = inv.obtener_token(api, "admin", clave_admin)
        intentar("400 - cuerpo inválido",
                 lambda: inv.llamar_api(api, "PATCH", "/dispositivos/4",
                                        token=token_admin, cuerpo={"estado": "Roto"}))
    else:
        print("\n(Se omite la prueba 400: define CLIENTE_CLAVE_ADMIN)")

    # Errores del servidor y de red (con reintentos)
    intentar("500 - fallo del servidor",
             lambda: inv.llamar_api(api, "GET", "/falla"))
    intentar("Timeout - respuesta lenta",
             lambda: inv.llamar_api(api, "GET", "/lento"))

    api_caida = dict(api, url_base="https://api-inventario:5999/api/v1")
    intentar("Sin conexión - puerto cerrado",
             lambda: inv.llamar_api(api_caida, "GET", "/salud"))

    api_ssl = dict(api, certificado=True)  # usa los certificados del sistema
    intentar("Certificado no confiable",
             lambda: inv.llamar_api(api_ssl, "GET", "/salud"))


if __name__ == "__main__":
    main()