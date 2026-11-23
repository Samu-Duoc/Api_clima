from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RegistroClima
from routers.schemas import RecepcionRobot

router = APIRouter(prefix="/api/clima", tags=["Clima"])


def verificar_api_key(x_api_key: Optional[str] = Header(default=None)):
    import os
    import hmac

    api_key = os.getenv("API_KEY")
    if api_key and not hmac.compare_digest(x_api_key or "", api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


@router.get("")
def listar_clima(
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = db.scalars(
        select(RegistroClima).order_by(RegistroClima.fecha_registro.desc()).limit(limite)
    ).all()
    return {"total": len(registros), "datos": [serializar_clima(r) for r in registros]}


@router.get("/ciudad/{ciudad}")
def listar_por_ciudad(
    ciudad: str,
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = db.scalars(
        select(RegistroClima)
        .where(RegistroClima.ciudad == ciudad)
        .order_by(RegistroClima.fecha_registro.desc())
        .limit(limite)
    ).all()
    return {"ciudad": ciudad, "total": len(registros), "datos": [serializar_clima(r) for r in registros]}


@router.get("/rango")
def listar_por_rango(
    fecha_desde: datetime,
    fecha_hasta: datetime,
    db: Session = Depends(get_db),
):
    if fecha_desde > fecha_hasta:
        raise HTTPException(status_code=422, detail="fecha_desde debe ser anterior a fecha_hasta")
    registros = db.scalars(
        select(RegistroClima)
        .where(RegistroClima.fecha_registro >= fecha_desde)
        .where(RegistroClima.fecha_registro <= fecha_hasta)
        .order_by(RegistroClima.fecha_registro.desc())
    ).all()
    return {"total": len(registros), "datos": [serializar_clima(r) for r in registros]}


@router.get("/reciente")
def clima_reciente(db: Session = Depends(get_db)):
    registro = db.scalar(
        select(RegistroClima).order_by(RegistroClima.fecha_registro.desc()).limit(1)
    )
    if not registro:
        return {"datos": None}
    return {"datos": serializar_clima(registro)}


def serializar_clima(registro: RegistroClima) -> dict:
    return {
        "id": registro.id,
        "ciudad": registro.ciudad or registro.ubicacion,
        "temperatura": registro.temperatura,
        "humedad": registro.humedad,
        "viento_velocidad": registro.velocidad_viento,
        "viento_direccion": registro.viento_direccion,
        "presion": registro.presion,
        "radiacion_uv": registro.radiacion_uv,
        "calidad_aire_pm25": registro.calidad_aire_pm25,
        "precipitacion_mm": registro.precipitacion,
        "condicion": registro.descripcion,
        "fecha_ingesta": registro.fecha_ingesta,
        "fecha_registro": registro.fecha_registro,
        "fecha_creacion": registro.fecha_creacion,
    }