#!/usr/bin/env python3
"""Cliente del inventario de red (Fase 5.1).

Lee configuración (YAML), sedes (CSV) y políticas (XML); consulta la API
por HTTPS y muestra el inventario.
"""
import csv
import os
import sys
import xml.etree.ElementTree as ET

import requests
import yaml

# Raíz del repositorio: dos carpetas por encima de este archivo (cliente/src/).
CARPETA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(CARPETA, "..", ".."))
CARPETA_DATOS = os.path.join(RAIZ, "cliente", "data")


# ---------- Lectura de archivos locales ----------
def leer_config(ruta):
    """Lee el archivo YAML de configuración y devuelve un diccionario."""
    with open(ruta, encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def leer_sedes(ruta):
    """Lee el CSV de sedes y devuelve un diccionario: hostname -> fila."""
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return {fila["hostname"]: fila for fila in csv.DictReader(archivo)}


def leer_politicas(ruta):
    """Lee el XML de políticas y devuelve el estado permitido y las versiones mínimas."""
    raiz = ET.parse(ruta).getroot()
    versiones = {
        nodo.get("plataforma"): nodo.text for nodo in raiz.findall("version_minima")
    }
    return {
        "estado_permitido": raiz.findtext("estado_permitido"),
        "versiones_minimas": versiones,
    }


# ---------- Consultas a la API ----------
def obtener_token(api, usuario, clave):
    """Pide un token a la API con Basic Auth y lo devuelve como texto."""
    respuesta = requests.post(
        api["url_base"] + "/auth/token",
        auth=(usuario, clave),
        verify=api["certificado"],
        timeout=api["timeout"],
    )
    respuesta.raise_for_status()
    return respuesta.json()["token"]


def obtener_dispositivos(api, token):
    """Pide el inventario a la API usando el token y devuelve la lista."""
    respuesta = requests.get(
        api["url_base"] + "/dispositivos",
        headers={"X-Auth-Token": token},
        verify=api["certificado"],
        timeout=api["timeout"],
    )
    respuesta.raise_for_status()
    return respuesta.json()["dispositivos"]


def main():
    """Punto de entrada: carga los archivos, consulta la API y muestra un resumen."""
    usuario = os.environ.get("CLIENTE_USUARIO")
    clave = os.environ.get("CLIENTE_CLAVE")
    if not usuario or not clave:
        sys.exit("Define CLIENTE_USUARIO y CLIENTE_CLAVE antes de ejecutar.")

    # 1. Archivos locales (YAML, CSV, XML)
    config = leer_config(os.path.join(CARPETA_DATOS, "config.yaml"))
    sedes = leer_sedes(os.path.join(CARPETA_DATOS, "sedes.csv"))
    politicas = leer_politicas(os.path.join(CARPETA_DATOS, "politicas.xml"))

    api = config["api"]
    # La ruta del certificado en el YAML es relativa a la raíz del repositorio.
    api["certificado"] = os.path.join(RAIZ, api["certificado"])

    print(f"[YAML] API configurada en: {api['url_base']}")
    print(f"[CSV]  Dispositivos con sede registrada: {len(sedes)}")
    print(f"[XML]  Estado permitido: {politicas['estado_permitido']}; "
          f"plataformas con versión mínima: {len(politicas['versiones_minimas'])}")

    # 2. Datos de la API (JSON)
    token = obtener_token(api, usuario, clave)
    dispositivos = obtener_dispositivos(api, token)

    print(f"[JSON] Dispositivos recibidos de la API: {len(dispositivos)}")
    for d in dispositivos:
        print(f"{d['hostname']:<20} {d['ip']:<14} {d['estado']:<12} {d['version']}")


if __name__ == "__main__":
    main()