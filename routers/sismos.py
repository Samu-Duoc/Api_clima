from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RegistroSismo

router = APIRouter(prefix="/api/sismos", tags=["Sismos"])


@router.get("")
def listar_sismos(
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = db.scalars(
        select(RegistroSismo).order_by(RegistroSismo.fecha_evento.desc()).limit(limite)
    ).all()
    return {"total": len(registros), "datos": [serializar_sismo(r) for r in registros]}


@router.get("/magnitud")
def listar_por_magnitud(
    minima: float = Query(default=0, ge=0),
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = db.scalars(
        select(RegistroSismo)
        .where(RegistroSismo.magnitud >= minima)
        .order_by(RegistroSismo.fecha_evento.desc())
        .limit(limite)
    ).all()
    return {"magnitud_minima": minima, "total": len(registros), "datos": [serializar_sismo(r) for r in registros]}


@router.get("/rango")
def listar_por_rango(
    fecha_desde: datetime,
    fecha_hasta: datetime,
    db: Session = Depends(get_db),
):
    if fecha_desde > fecha_hasta:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="fecha_desde debe ser anterior a fecha_hasta")
    registros = db.scalars(
        select(RegistroSismo)
        .where(RegistroSismo.fecha_evento >= fecha_desde)
        .where(RegistroSismo.fecha_evento <= fecha_hasta)
        .order_by(RegistroSismo.fecha_evento.desc())
    ).all()
    return {"total": len(registros), "datos": [serializar_sismo(r) for r in registros]}


@router.get("/recientes")
def sismos_recientes(
    limite: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    registros = db.scalars(
        select(RegistroSismo).order_by(RegistroSismo.fecha_evento.desc()).limit(limite)
    ).all()
    return {"total": len(registros), "datos": [serializar_sismo(r) for r in registros]}


def serializar_sismo(registro: RegistroSismo) -> dict:
    return {
        "id": registro.id,
        "id_externo": registro.id_externo,
        "lugar": registro.ubicacion,
        "magnitud": registro.magnitud,
        "semaforo": registro.semaforo,
        "hora": registro.fecha_evento,
        "longitud": registro.longitud,
        "latitud": registro.latitud,
        "profundidad_km": registro.profundidad,
        "url_usgs": registro.url_usgs,
        "fecha_ingesta": registro.fecha_ingesta,
        "fecha_creacion": registro.fecha_creacion,
    }