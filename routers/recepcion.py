import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import EjecucionRobot, RegistroClima, RegistroSismo
from routers.schemas import RecepcionRobot

router = APIRouter(prefix="/api", tags=["Recepción Robot"])
logger = logging.getLogger("uvicorn.error")


def asegurar_zona_horaria(valor: datetime | None) -> datetime | None:
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor


def verificar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    api_key = os.getenv("API_KEY")
    if api_key and not hmac.compare_digest(x_api_key or "", api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


def clave_payload(datos: RecepcionRobot) -> str:
    contenido = datos.model_dump(mode="json", exclude={"clave_ejecucion", "ejecucion_id", "ejecucion"})
    serializado = json.dumps(contenido, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def texto_archivos(datos: RecepcionRobot) -> str | None:
    archivos = datos.archivos if datos.archivos is not None else datos.archivos_generados
    drive = datos.enlaces_drive
    if datos.drive_link:
        drive = dict(drive or {})
        drive["reporte"] = datos.drive_link
    if drive:
        archivos = {"archivos": archivos, "drive": drive}
    if archivos is None:
        return None
    if isinstance(archivos, str):
        return archivos
    return json.dumps(archivos, ensure_ascii=False, sort_keys=True)


def grupos_clima(datos: RecepcionRobot) -> list[tuple[datetime | None, dict[str, Any]]]:
    if datos.estaciones:
        fecha = datos.timestamp or datos.fecha_inicio or datos.fecha_ejecucion
        fuente = [(asegurar_zona_horaria(fecha), registro) for registro in datos.estaciones]
    elif datos.data is not None:
        fuente = []
        for elemento in datos.data.clima:
            if isinstance(elemento, dict):
                fecha_ingesta = elemento.get("fecha_ingesta")
                fecha = (
                    datetime.fromisoformat(str(fecha_ingesta).replace("Z", "+00:00"))
                    if fecha_ingesta else None
                )
                registros = elemento.get("clima", [])
            else:
                fecha = elemento.fecha_ingesta
                registros = elemento.clima

            if isinstance(registros, list):
                for registro in registros:
                    if hasattr(registro, "model_dump"):
                        fuente.append((asegurar_zona_horaria(fecha), registro.model_dump()))
                    elif isinstance(registro, dict):
                        fuente.append((asegurar_zona_horaria(fecha), registro))
            elif isinstance(registros, dict):
                fuente.append((asegurar_zona_horaria(fecha), registros))
    else:
        fuente = []
        for elemento in datos.clima or []:
            if isinstance(elemento, dict):
                fecha_ingesta = elemento.get("fecha_ingesta")
                fecha = (
                    datetime.fromisoformat(str(fecha_ingesta).replace("Z", "+00:00"))
                    if fecha_ingesta else None
                )
                registros = elemento.get("clima", [])
            else:
                fecha = elemento.fecha_ingesta
                registros = elemento.clima

            if isinstance(registros, list):
                for registro in registros:
                    if hasattr(registro, "model_dump"):
                        fuente.append((asegurar_zona_horaria(fecha), registro.model_dump()))
                    elif isinstance(registro, dict):
                        fuente.append((asegurar_zona_horaria(fecha), registro))

    unicos: list[tuple[datetime | None, dict[str, Any]]] = []
    vistas: set[str] = set()
    for fecha, registro in fuente:
        ciudad = str(registro.get("ciudad") or registro.get("ubicacion") or "").strip()
        if not ciudad:
            continue

        contenido = {
            "ciudad": ciudad,
            "fecha": fecha.isoformat() if fecha else None,
            "temperatura": registro.get("temperatura"),
            "humedad": registro.get("humedad"),
            "precipitacion": (
                registro.get("precipitacion_mm")
                if "precipitacion_mm" in registro
                else registro.get("precipitacion")
            ),
        }
        clave = hashlib.sha256(
            json.dumps(contenido, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        if clave in vistas:
            continue
        vistas.add(clave)

        registro_normalizado = dict(registro)
        registro_normalizado["ciudad"] = ciudad
        unicos.append((fecha, registro_normalizado))

    return unicos


def grupos_sismos(datos: RecepcionRobot) -> list[tuple[datetime | None, dict[str, Any]]]:
    fecha_predeterminada = datos.timestamp or datos.fecha_inicio or datos.fecha_ejecucion
    fuente: list[tuple[datetime | None, dict[str, Any]]] = []

    if datos.sismos:
        for elemento in datos.sismos:
            if isinstance(elemento, dict):
                fecha_ingesta = elemento.get("fecha_ingesta")
                fecha = (
                    datetime.fromisoformat(str(fecha_ingesta).replace("Z", "+00:00"))
                    if fecha_ingesta else fecha_predeterminada
                )
                sismo = elemento.get("sismo", elemento)
            else:
                fecha = elemento.fecha_ingesta or fecha_predeterminada
                sismo = elemento.sismo.model_dump()
            if isinstance(sismo, dict):
                fuente.append((asegurar_zona_horaria(fecha), sismo))
    elif datos.data is not None:
        for elemento in datos.data.sismos:
            if isinstance(elemento, dict):
                fecha_ingesta = elemento.get("fecha_ingesta")
                fecha = (
                    datetime.fromisoformat(str(fecha_ingesta).replace("Z", "+00:00"))
                    if fecha_ingesta else fecha_predeterminada
                )
                sismo = elemento.get("sismo", elemento)
            else:
                fecha = elemento.fecha_ingesta or fecha_predeterminada
                sismo = elemento.sismo.model_dump()
            if isinstance(sismo, dict):
                fuente.append((asegurar_zona_horaria(fecha), sismo))

    unicos: list[tuple[datetime | None, dict[str, Any]]] = []
    vistas: set[str] = set()
    for fecha, sismo in fuente:
        id_externo = str(sismo.get("id") or "").strip()
        if not id_externo:
            continue
        if id_externo in vistas:
            continue
        vistas.add(id_externo)
        unicos.append((fecha, dict(sismo)))

    return unicos


@router.post("/recepcion", status_code=201)
def recibir_datos_robot(
    datos: RecepcionRobot,
    db: Session = Depends(get_db),
    _api_key: None = Depends(verificar_api_key),
):
    clave = datos.clave_ejecucion or datos.ejecucion or datos.ejecucion_id or clave_payload(datos)

    try:
        ejecucion_existente = db.scalar(
            select(EjecucionRobot).where(EjecucionRobot.clave_ejecucion == clave)
        )
        if ejecucion_existente:
            return {
                "success": True,
                "confirmacion": "ya_procesada",
                "ejecucion_id": str(ejecucion_existente.id),
                "clave_ejecucion": clave,
                "resumen": {
                    "clima_recibidos": 0,
                    "clima_insertados": 0,
                    "clima_actualizados": 0,
                    "clima_duplicados": 0,
                    "sismos_recibidos": 0,
                    "sismos_insertados": 0,
                    "sismos_actualizados": 0,
                    "sismos_duplicados": 0,
                },
            }

        estado = datos.status or datos.estado
        fecha_inicio = asegurar_zona_horaria(
            datos.timestamp or datos.fecha_inicio or datos.fecha_ejecucion
        )
        if fecha_inicio is None:
            fecha_inicio = datetime.now(timezone.utc)

        ejecucion = EjecucionRobot(
            clave_ejecucion=clave,
            computador=datos.computador,
            origen=datos.origen or "Rocketbot",
            estaciones_procesadas=datos.estaciones_procesadas,
            alertas_detectadas=datos.alertas_detectadas,
            semaforo_global=datos.semaforo_global,
            semaforos=(
                json.dumps(datos.semaforos, ensure_ascii=False)
                if datos.semaforos is not None else None
            ),
            totem_exp_epoch=datos.totem_exp_epoch,
            fecha_inicio=fecha_inicio,
            fecha_fin=(
                datetime.now(timezone.utc)
                if estado in {
                    "completada", "fallida", "abandonada",
                    "COMPLETADA", "FALLIDA", "ABANDONADA",
                }
                else None
            ),
            estado=estado,
            mensaje=datos.mensaje,
            archivos_generados=texto_archivos(datos),
        )
        db.add(ejecucion)
        db.flush()

        grupos_clima_recibidos = grupos_clima(datos)
        insertados_clima = 0
        actualizados_clima = 0
        duplicados_clima = 0
        claves_clima_lote: set[str] = set()
        existentes_clima: dict[str, RegistroClima] = {}

        for fecha_ingesta, registro in grupos_clima_recibidos:
            ciudad = str(registro.get("ciudad") or registro.get("ubicacion") or "").strip()
            if not ciudad:
                raise HTTPException(status_code=422, detail="Cada registro climático requiere ciudad")

            fecha_registro = asegurar_zona_horaria(fecha_ingesta) or fecha_inicio
            clima_contenido = {
                "ciudad": ciudad,
                "fecha": fecha_registro.isoformat(),
                "temperatura": registro.get("temperatura"),
                "humedad": registro.get("humedad"),
                "precip": (
                    registro.get("precipitacion_mm")
                    if "precipitacion_mm" in registro
                    else registro.get("precipitacion")
                ),
            }
            clave_clima = hashlib.sha256(
                json.dumps(clima_contenido, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest()
            if clave_clima in claves_clima_lote:
                duplicados_clima += 1
                continue
            claves_clima_lote.add(clave_clima)

            existente = existentes_clima.get(clave_clima)
            if existente is None:
                existente = db.scalar(
                    select(RegistroClima).where(RegistroClima.clave_unica == clave_clima)
                )
                if existente is not None:
                    existentes_clima[clave_clima] = existente
            if existente:
                actualizados_clima += 1
                existente.temperatura = registro.get("temperatura")
                existente.humedad = registro.get("humedad")
                existente.velocidad_viento = registro.get("viento_velocidad")
                existente.viento_direccion = registro.get("viento_direccion")
                existente.presion = registro.get("presion")
                existente.radiacion_uv = registro.get("radiacion_uv")
                existente.calidad_aire_pm25 = registro.get("calidad_aire_pm25")
                existente.precipitacion = (
                    registro.get("precipitacion_mm")
                    if "precipitacion_mm" in registro
                    else registro.get("precipitacion")
                )
                existente.descripcion = registro.get("condicion")
                existente.fecha_ingesta = fecha_ingesta
                existente.fecha_registro = fecha_registro
                continue

            nuevo_clima = RegistroClima(
                clave_unica=clave_clima,
                ubicacion=ciudad,
                ciudad=ciudad,
                temperatura=registro.get("temperatura"),
                humedad=registro.get("humedad"),
                velocidad_viento=registro.get("viento_velocidad"),
                viento_direccion=registro.get("viento_direccion"),
                presion=registro.get("presion"),
                radiacion_uv=registro.get("radiacion_uv"),
                calidad_aire_pm25=registro.get("calidad_aire_pm25"),
                precipitacion=(
                    registro.get("precipitacion_mm")
                    if "precipitacion_mm" in registro
                    else registro.get("precipitacion")
                ),
                descripcion=registro.get("condicion"),
                fecha_ingesta=fecha_ingesta,
                fecha_registro=fecha_registro,
            )
            db.add(nuevo_clima)
            existentes_clima[clave_clima] = nuevo_clima
            insertados_clima += 1

        grupos_sismos_recibidos = grupos_sismos(datos)
        insertados_sismos = 0
        actualizados_sismos = 0
        duplicados_sismos = 0
        ids_sismos_lote: set[str] = set()
        existentes_sismos: dict[str, RegistroSismo] = {}

        for fecha_ingesta, registro in grupos_sismos_recibidos:
            id_externo = str(registro.get("id") or "").strip()
            lugar = str(registro.get("lugar") or "").strip()
            if not id_externo or not lugar:
                raise HTTPException(status_code=422, detail="Cada sismo requiere id y lugar")
            if registro.get("magnitud") is None or registro.get("profundidad_km") is None:
                raise HTTPException(status_code=422, detail="Cada sismo requiere magnitud y profundidad_km")

            if id_externo in ids_sismos_lote:
                duplicados_sismos += 1
                continue
            ids_sismos_lote.add(id_externo)

            hora = registro.get("hora")
            if isinstance(hora, datetime):
                fecha_evento = asegurar_zona_horaria(hora)
            elif hora:
                try:
                    fecha_evento = asegurar_zona_horaria(
                        datetime.fromisoformat(str(hora).replace("Z", "+00:00"))
                    )
                except ValueError as error:
                    raise HTTPException(
                        status_code=422,
                        detail="El campo hora del sismo tiene un formato inválido",
                    ) from error
            else:
                raise HTTPException(status_code=422, detail="Cada sismo requiere hora")

            valores = {
                "magnitud": registro["magnitud"],
                "profundidad": registro["profundidad_km"],
                "ubicacion": lugar,
                "referencia": registro.get("referencia"),
                "semaforo": registro.get("semaforo"),
                "longitud": registro.get("longitud"),
                "latitud": registro.get("latitud"),
                "url_usgs": registro.get("url_usgs"),
                "fecha_ingesta": asegurar_zona_horaria(fecha_ingesta),
                "fecha_evento": fecha_evento,
            }

            existente = existentes_sismos.get(id_externo)
            if existente is None:
                existente = db.scalar(
                    select(RegistroSismo).where(RegistroSismo.id_externo == id_externo)
                )
                if existente is not None:
                    existentes_sismos[id_externo] = existente

            if existente:
                for campo, valor in valores.items():
                    setattr(existente, campo, valor)
                actualizados_sismos += 1
            else:
                nuevo_sismo = RegistroSismo(id_externo=id_externo, **valores)
                db.add(nuevo_sismo)
                existentes_sismos[id_externo] = nuevo_sismo
                insertados_sismos += 1

        db.commit()
        return {
            "success": True,
            "confirmacion": "procesada",
            "ejecucion_id": str(ejecucion.id),
            "clave_ejecucion": clave,
            "resumen": {
                "clima_recibidos": len(grupos_clima_recibidos),
                "clima_insertados": insertados_clima,
                "clima_actualizados": actualizados_clima,
                "clima_duplicados": duplicados_clima,
                "sismos_recibidos": len(grupos_sismos_recibidos),
                "sismos_insertados": insertados_sismos,
                "sismos_actualizados": actualizados_sismos,
                "sismos_duplicados": duplicados_sismos,
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("ERROR REAL AL GUARDAR EN POSTGRESQL")
        raise HTTPException(
            status_code=503,
            detail="No fue posible almacenar los datos en PostgreSQL",
        )
