from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import EjecucionRobot

router = APIRouter(prefix="/api", tags=["Ejecuciones Robot"])


def serializar_ejecucion(ejecucion: EjecucionRobot) -> dict:
    duracion_segundos = None
    if ejecucion.fecha_fin:
        duracion_segundos = max(
            0,
            int((ejecucion.fecha_fin - ejecucion.fecha_inicio).total_seconds()),
        )

    return {
        "id": ejecucion.id,
        "clave_ejecucion": ejecucion.clave_ejecucion,
        "origen": ejecucion.origen,
        "computador": ejecucion.computador,
        "fecha_inicio": ejecucion.fecha_inicio,
        "fecha_fin": ejecucion.fecha_fin,
        "fecha_creacion": ejecucion.fecha_creacion,
        "estado": ejecucion.estado,
        "mensaje": ejecucion.mensaje,
        "estaciones_procesadas": ejecucion.estaciones_procesadas,
        "alertas_detectadas": ejecucion.alertas_detectadas,
        "semaforo_global": ejecucion.semaforo_global,
        "semaforos": ejecucion.semaforos,
        "totem_exp_epoch": ejecucion.totem_exp_epoch,
        "duracion_segundos": duracion_segundos,
    }


def consultar_ejecuciones(
    db: Session,
    fecha_desde: Optional[datetime],
    fecha_hasta: Optional[datetime],
    estado: Optional[str],
    busqueda: Optional[str],
    limite: int,
) -> list[EjecucionRobot]:
    consulta = select(EjecucionRobot)

    if fecha_desde:
        consulta = consulta.where(EjecucionRobot.fecha_inicio >= fecha_desde)
    if fecha_hasta:
        consulta = consulta.where(EjecucionRobot.fecha_inicio <= fecha_hasta)
    if estado:
        consulta = consulta.where(EjecucionRobot.estado.ilike(f"%{estado}%"))
    if busqueda:
        patron = f"%{busqueda}%"
        consulta = consulta.where(
            EjecucionRobot.clave_ejecucion.ilike(patron)
            | EjecucionRobot.mensaje.ilike(patron)
            | EjecucionRobot.computador.ilike(patron)
        )

    consulta = consulta.order_by(EjecucionRobot.fecha_inicio.desc()).limit(limite)
    return list(db.scalars(consulta).all())


@router.get("/ejecuciones")
def listar_ejecuciones(
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    estado: Optional[str] = None,
    busqueda: Optional[str] = None,
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = consultar_ejecuciones(
        db, fecha_desde, fecha_hasta, estado, busqueda, limite
    )
    return {"total": len(registros), "datos": [serializar_ejecucion(r) for r in registros]}


@router.get("/logs")
def listar_logs(
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    estado: Optional[str] = None,
    busqueda: Optional[str] = None,
    limite: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    registros = consultar_ejecuciones(
        db, fecha_desde, fecha_hasta, estado, busqueda, limite
    )
    return {"total": len(registros), "datos": [serializar_ejecucion(r) for r in registros]}
