#!/usr/bin/env python3
"""Cliente del inventario de red (Fase 5.2).

Lee configuración (YAML), sedes (CSV) y políticas (XML); consulta la API por
HTTPS, cruza las fuentes, detecta problemas y guarda un reporte JSON y CSV.
"""
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

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


# ---------- Análisis ----------
def version_a_tupla(version):
    """Convierte '17.3.4' en (17, 3, 4) para poder compararlas como números.

    Devuelve None si el texto no es una versión válida.
    """
    try:
        return tuple(int(parte) for parte in version.split("."))
    except (ValueError, AttributeError):
        return None


def evaluar_dispositivo(dispositivo, sedes, politicas):
    """Cruza un dispositivo de la API con el CSV y las políticas XML.

    Devuelve un diccionario con sus datos y la lista de problemas encontrados.
    """
    problemas = []

    # Regla 1: el estado debe ser el permitido por la política.
    if dispositivo["estado"] != politicas["estado_permitido"]:
        problemas.append(
            f"Estado {dispositivo['estado']} "
            f"(se esperaba {politicas['estado_permitido']})"
        )

    # Regla 2: la versión debe cumplir el mínimo de su plataforma.
    minima = politicas["versiones_minimas"].get(dispositivo["plataforma"])
    if minima is None:
        problemas.append(f"Sin política de versión para {dispositivo['plataforma']}")
    else:
        actual_t = version_a_tupla(dispositivo["version"])
        minima_t = version_a_tupla(minima)
        if actual_t is None or minima_t is None:
            problemas.append("Versión ilegible")
        elif actual_t < minima_t:
            problemas.append(
                f"Versión {dispositivo['version']} menor a la mínima {minima}"
            )

    # Regla 3: el dispositivo debe estar registrado en el CSV de sedes.
    registro = sedes.get(dispositivo["hostname"])
    if registro is None:
        problemas.append("Sin sede registrada en el CSV")

    return {
        "hostname": dispositivo["hostname"],
        "ip": dispositivo["ip"],
        "plataforma": dispositivo["plataforma"],
        "version": dispositivo["version"],
        "estado": dispositivo["estado"],
        "sede": registro["sede"] if registro else "SIN REGISTRO",
        "criticidad": registro["criticidad"] if registro else "desconocida",
        "responsable": registro["responsable"] if registro else "N/A",
        "problemas": problemas,
    }


def resumir_por_sede(resultados):
    """Cuenta, por sede, cuántos dispositivos hay y cuántos tienen problemas."""
    resumen = {}
    for r in resultados:
        datos = resumen.setdefault(r["sede"], {"dispositivos": 0, "con_problemas": 0})
        datos["dispositivos"] += 1
        if r["problemas"]:
            datos["con_problemas"] += 1
    return resumen


# ---------- Reportes ----------
def guardar_reportes(resultados, resumen, carpeta):
    """Guarda el reporte en JSON y CSV con la fecha y hora en el nombre."""
    os.makedirs(carpeta, exist_ok=True)
    ahora = datetime.now()
    marca = ahora.strftime("%Y%m%d_%H%M%S")
    ruta_json = os.path.join(carpeta, f"reporte_{marca}.json")
    ruta_csv = os.path.join(carpeta, f"reporte_{marca}.csv")

    with open(ruta_json, "w", encoding="utf-8") as archivo:
        json.dump(
            {
                "generado": ahora.isoformat(timespec="seconds"),
                "resumen_por_sede": resumen,
                "dispositivos": resultados,
            },
            archivo,
            indent=2,
            ensure_ascii=False,
        )

    campos = ["hostname", "ip", "plataforma", "version", "estado",
              "sede", "criticidad", "responsable", "problemas"]
    with open(ruta_csv, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        for r in resultados:
            fila = dict(r)
            fila["problemas"] = "; ".join(r["problemas"])
            escritor.writerow(fila)

    return ruta_json, ruta_csv


def main():
    """Punto de entrada: carga datos, consulta la API, analiza y guarda reportes."""
    usuario = os.environ.get("CLIENTE_USUARIO")
    clave = os.environ.get("CLIENTE_CLAVE")
    if not usuario or not clave:
        sys.exit("Define CLIENTE_USUARIO y CLIENTE_CLAVE antes de ejecutar.")

    # 1. Archivos locales (YAML, CSV, XML)
    config = leer_config(os.path.join(CARPETA_DATOS, "config.yaml"))
    sedes = leer_sedes(os.path.join(CARPETA_DATOS, "sedes.csv"))
    politicas = leer_politicas(os.path.join(CARPETA_DATOS, "politicas.xml"))

    api = config["api"]
    # Las rutas del YAML son relativas a la raíz del repositorio.
    api["certificado"] = os.path.join(RAIZ, api["certificado"])
    carpeta_reportes = os.path.join(RAIZ, config["reportes"]["carpeta"])

    # 2. Datos de la API (JSON)
    token = obtener_token(api, usuario, clave)
    dispositivos = obtener_dispositivos(api, token)
    print(f"Dispositivos recibidos: {len(dispositivos)}")

    # 3. Análisis: cruzar las tres fuentes
    resultados = [evaluar_dispositivo(d, sedes, politicas) for d in dispositivos]
    resumen = resumir_por_sede(resultados)

    print("\n=== Resumen por sede ===")
    for sede, datos in sorted(resumen.items()):
        print(f"{sede:<18} {datos['dispositivos']} dispositivos, "
              f"{datos['con_problemas']} con problemas")

    print("\n=== Dispositivos con problemas ===")
    con_problemas = [r for r in resultados if r["problemas"]]
    if not con_problemas:
        print("Ninguno")
    for r in con_problemas:
        print(f"{r['hostname']} [{r['sede']}]")
        for problema in r["problemas"]:
            print(f"   - {problema}")

    # 4. Reportes
    ruta_json, ruta_csv = guardar_reportes(resultados, resumen, carpeta_reportes)
    print(f"\nReportes guardados:\n  {ruta_json}\n  {ruta_csv}")


if __name__ == "__main__":
    main()