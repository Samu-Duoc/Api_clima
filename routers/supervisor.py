import hmac
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import (
    EjecucionRobot,
    EventoSupervisor,
    EstadoSupervisor,
    TrabajoRobot,
)


router = APIRouter(prefix="/api/robot", tags=["Supervisor Rocketbot"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def verificar_agente(
    x_agent_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> str:
    configured = os.getenv("AGENT_API_KEY")
    if not configured:
        raise HTTPException(status_code=503, detail="AGENT_API_KEY no está configurada")
    supplied = x_agent_api_key
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, configured):
        raise HTTPException(status_code=401, detail="Credencial del agente inválida")
    return configured


class SolicitudTrabajo(BaseModel):
    clave_solicitud: str = Field(min_length=8, max_length=128)
    tipo: str = "CARGAR_NUEVO_TOKEN"
    robot: str = "Clima"
    origen: str = "dashboard"
    intentos_maximos: int = Field(
        default=int(os.getenv("JOB_MAX_ATTEMPTS", "3")),
        ge=1,
        le=10,
    )
    minutos_expiracion: int = Field(
        default=int(os.getenv("JOB_LEASE_MINUTES", "15")),
        ge=1,
        le=1440,
    )
    etapa_fallida: Optional[str] = Field(default=None, max_length=100)
    etapas_completadas: list[str] = Field(default_factory=list)


class ReporteAgente(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    estado: str = Field(min_length=1, max_length=50)
    detalle: Optional[str] = Field(default=None, max_length=4000)


class ReporteEtapa(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    etapa: str = Field(min_length=1, max_length=100)
    estado: str = Field(min_length=1, max_length=50)
    detalle: Optional[str] = Field(default=None, max_length=4000)


def serializar_trabajo_supervisor(trabajo: TrabajoRobot) -> dict:
    try:
        etapas_completadas = (
            json.loads(trabajo.etapas_completadas)
            if trabajo.etapas_completadas
            else []
        )
    except json.JSONDecodeError:
        etapas_completadas = []

    if not isinstance(etapas_completadas, list):
        etapas_completadas = []

    return {
        "id": trabajo.id,
        "clave_solicitud": trabajo.clave_solicitud,
        "tipo": trabajo.tipo,
        "robot": trabajo.robot,
        "estado": trabajo.estado,
        "agente_id": trabajo.agente_id,
        "mensaje": trabajo.mensaje,
        "fecha_creacion": trabajo.fecha_creacion,
        "fecha_reclamado": trabajo.fecha_reclamado,
        "fecha_inicio": trabajo.fecha_inicio,
        "fecha_expiracion": trabajo.fecha_expiracion,
        "fecha_finalizacion": trabajo.fecha_finalizacion,
        "etapa_actual": trabajo.etapa_actual,
        "etapa_fallida": trabajo.etapa_fallida,
        "etapas_completadas": etapas_completadas,
        "intentos": trabajo.intentos,
        "intentos_maximos": trabajo.intentos_maximos,
    }


def obtener_estado(db: Session, agente_id: str) -> EstadoSupervisor:
    estado = db.scalar(
        select(EstadoSupervisor).where(EstadoSupervisor.agente_id == agente_id)
    )
    if estado is None:
        estado = EstadoSupervisor(
            agente_id=agente_id,
            estado="DESCONECTADO",
        )
        db.add(estado)
        db.flush()
    return estado


def registrar_evento(
    db: Session,
    agente_id: str,
    evento: str,
    detalle: Optional[str] = None,
    trabajo_id: Optional[int] = None,
) -> None:
    db.add(EventoSupervisor(
        agente_id=agente_id,
        trabajo_id=trabajo_id,
        evento=evento,
        detalle=detalle,
    ))


@router.get("/supervisor/estado")
def estado_supervisor_dashboard(db: Session = Depends(get_db)):
    estado = db.scalar(
        select(EstadoSupervisor).order_by(
            EstadoSupervisor.fecha_actualizacion.desc()
        ).limit(1)
    )

    trabajo = None
    if estado and estado.trabajo_actual_id:
        trabajo_registrado = db.get(TrabajoRobot, estado.trabajo_actual_id)
        if trabajo_registrado:
            trabajo = serializar_trabajo_supervisor(trabajo_registrado)

    if trabajo is None:
        trabajo_registrado = db.scalar(
            select(TrabajoRobot)
            .where(TrabajoRobot.robot == "Clima")
            .order_by(TrabajoRobot.fecha_creacion.desc())
            .limit(1)
        )
        if trabajo_registrado:
            trabajo = serializar_trabajo_supervisor(trabajo_registrado)

    eventos_alerta = db.scalars(
        select(EventoSupervisor)
        .where(EventoSupervisor.evento.in_((
            "REQUIERE_INTERVENCION",
            "ETAPA_FALLIDA",
            "EJECUCION_ERROR",
            "TRABAJO_ERROR_MAXIMO",
            "ESTADO_NO_CONFIRMADO",
        )))
        .order_by(EventoSupervisor.fecha_evento.desc())
        .limit(20)
    ).all()

    alertas = [
        {
            "id": evento.id,
            "trabajo_id": evento.trabajo_id,
            "fecha": evento.fecha_evento,
            "tipo": evento.evento,
            "descripcion": evento.detalle,
        }
        for evento in eventos_alerta
    ]

    ultima_ejecucion = db.scalar(
        select(EjecucionRobot)
        .order_by(EjecucionRobot.fecha_inicio.desc())
        .limit(1)
    )
    totem_exp_epoch = (
        ultima_ejecucion.totem_exp_epoch
        if ultima_ejecucion and ultima_ejecucion.totem_exp_epoch
        else None
    )

    return {
        "agente": (
            {
                "id": estado.agente_id,
                "estado": estado.estado,
                "detalle": estado.detalle,
                "ultimo_heartbeat": estado.ultimo_heartbeat,
                "fecha_actualizacion": estado.fecha_actualizacion,
                "trabajo_actual_id": estado.trabajo_actual_id,
            }
            if estado else None
        ),
        "trabajo": trabajo,
        "alertas": alertas,
        "totem_exp_epoch": totem_exp_epoch,
    }


@router.get("/supervisor/eventos")
def eventos_supervisor_dashboard(
    limite: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    eventos = db.scalars(
        select(EventoSupervisor)
        .order_by(EventoSupervisor.fecha_evento.desc())
        .limit(limite)
    ).all()
    return {
        "total": len(eventos),
        "datos": [
            {
                "id": evento.id,
                "trabajo_id": evento.trabajo_id,
                "agente_id": evento.agente_id,
                "fecha": evento.fecha_evento,
                "evento": evento.evento,
                "descripcion": evento.detalle,
            }
            for evento in eventos
        ],
    }


@router.get("/agente/estado")
def estado_robot(
    agente_id: str,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    estado = obtener_estado(db, agente_id)
    db.commit()
    trabajo = None
    if estado.trabajo_actual_id:
        trabajo = db.get(TrabajoRobot, estado.trabajo_actual_id)
    return {
        "agent_id": estado.agente_id,
        "estado": estado.estado,
        "detalle": estado.detalle,
        "ultimo_heartbeat": estado.ultimo_heartbeat,
        "trabajo_actual_id": estado.trabajo_actual_id,
        "trabajo": (
            {
                "id": trabajo.id,
                "estado": trabajo.estado,
                "robot": trabajo.robot,
                "fecha_expiracion": trabajo.fecha_expiracion,
            }
            if trabajo else None
        ),
    }


@router.post("/trabajos/solicitar")
def solicitar_trabajo(
    solicitud: SolicitudTrabajo,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    existente = db.scalar(
        select(TrabajoRobot).where(
            TrabajoRobot.clave_solicitud == solicitud.clave_solicitud
        )
    )
    if existente:
        return {
            "duplicado": True,
            "trabajo": {
                "id": existente.id,
                "estado": existente.estado,
                "clave_solicitud": existente.clave_solicitud,
            },
        }

    ahora = utc_now()
    trabajo = TrabajoRobot(
        clave_solicitud=solicitud.clave_solicitud,
        tipo=solicitud.tipo,
        robot=solicitud.robot,
        origen=solicitud.origen,
        estado="PENDIENTE",
        intentos=0,
        intentos_maximos=solicitud.intentos_maximos,
        fecha_creacion=ahora,
        fecha_expiracion=ahora + timedelta(minutes=solicitud.minutos_expiracion),
        etapa_fallida=solicitud.etapa_fallida,
        etapas_completadas=json.dumps(
            solicitud.etapas_completadas,
            ensure_ascii=False,
        ),
    )
    db.add(trabajo)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existente = db.scalar(
            select(TrabajoRobot).where(
                TrabajoRobot.clave_solicitud == solicitud.clave_solicitud
            )
        )
        if existente is None:
            raise
        return {
            "duplicado": True,
            "trabajo": {
                "id": existente.id,
                "estado": existente.estado,
                "clave_solicitud": existente.clave_solicitud,
            },
        }
    registrar_evento(db, "dashboard", "SOLICITUD_TRABAJO", solicitud.tipo, trabajo.id)
    db.commit()
    db.refresh(trabajo)
    return {
        "duplicado": False,
        "trabajo": {
            "id": trabajo.id,
            "estado": trabajo.estado,
            "clave_solicitud": trabajo.clave_solicitud,
            "robot": trabajo.robot,
            "fecha_expiracion": trabajo.fecha_expiracion,
        },
    }


@router.post("/agente/siguiente")
def reclamar_siguiente(
    reporte: ReporteAgente,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    ahora = utc_now()
    estado = obtener_estado(db, reporte.agent_id)
    estado.estado = "ACTIVO"
    estado.detalle = reporte.detalle
    estado.ultimo_heartbeat = ahora

    vencidos = list(db.scalars(
        select(TrabajoRobot).where(
            TrabajoRobot.estado.in_(("PENDIENTE", "RECLAMADO", "EN_EJECUCION")),
            TrabajoRobot.fecha_expiracion.is_not(None),
            TrabajoRobot.fecha_expiracion < ahora,
        )
    ).all())
    for vencido in vencidos:
        if vencido.intentos < vencido.intentos_maximos:
            vencido.estado = "PENDIENTE"
            vencido.agente_id = None
            vencido.fecha_reclamado = None
            vencido.fecha_expiracion = ahora + timedelta(
                minutes=int(os.getenv("JOB_LEASE_MINUTES", "15"))
            )
            vencido.mensaje = "Trabajo vencido; liberado para reintento"
            evento = "TRABAJO_REINTENTADO"
        else:
            vencido.estado = "ERROR"
            vencido.mensaje = "Trabajo vencido después de consumir todos los reintentos"
            vencido.fecha_finalizacion = ahora
            evento = "TRABAJO_ERROR_MAXIMO"
        registrar_evento(
            db,
            reporte.agent_id,
            evento,
            vencido.mensaje,
            vencido.id,
        )

    trabajo = db.scalar(
        select(TrabajoRobot)
        .where(
            TrabajoRobot.estado == "PENDIENTE",
            TrabajoRobot.robot == "Clima",
            TrabajoRobot.fecha_expiracion >= ahora,
        )
        .order_by(TrabajoRobot.fecha_creacion)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if trabajo is None:
        db.commit()
        return {"trabajo": None}

    trabajo.estado = "RECLAMADO"
    trabajo.agente_id = reporte.agent_id
    trabajo.fecha_reclamado = ahora
    trabajo.intentos += 1
    estado.trabajo_actual_id = trabajo.id
    registrar_evento(
        db,
        reporte.agent_id,
        "TRABAJO_RECLAMADO",
        f"Intento {trabajo.intentos}/{trabajo.intentos_maximos}",
        trabajo.id,
    )
    db.commit()
    db.refresh(trabajo)
    return {
        "trabajo": {
            "id": trabajo.id,
            "clave_solicitud": trabajo.clave_solicitud,
            "tipo": trabajo.tipo,
            "robot": trabajo.robot,
            "estado": trabajo.estado,
            "etapa_actual": trabajo.etapa_actual,
            "etapa_fallida": trabajo.etapa_fallida,
            "etapas_completadas": trabajo.etapas_completadas,
        }
    }


@router.post("/agente/heartbeat")
def heartbeat(
    reporte: ReporteAgente,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    ahora = utc_now()
    estado = obtener_estado(db, reporte.agent_id)
    estado.estado = reporte.estado
    estado.detalle = reporte.detalle
    estado.ultimo_heartbeat = ahora
    registrar_evento(
        db,
        reporte.agent_id,
        "HEARTBEAT",
        reporte.detalle,
        estado.trabajo_actual_id,
    )
    db.commit()
    return {"success": True, "ultimo_heartbeat": ahora}


@router.get("/trabajos/{trabajo_id}")
def consultar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    trabajo = db.get(TrabajoRobot, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return {
        "id": trabajo.id,
        "clave_solicitud": trabajo.clave_solicitud,
        "tipo": trabajo.tipo,
        "robot": trabajo.robot,
        "estado": trabajo.estado,
        "agente_id": trabajo.agente_id,
        "intentos": trabajo.intentos,
        "intentos_maximos": trabajo.intentos_maximos,
        "mensaje": trabajo.mensaje,
        "fecha_creacion": trabajo.fecha_creacion,
        "fecha_reclamado": trabajo.fecha_reclamado,
        "fecha_expiracion": trabajo.fecha_expiracion,
        "fecha_inicio": trabajo.fecha_inicio,
        "fecha_finalizacion": trabajo.fecha_finalizacion,
        "etapa_actual": trabajo.etapa_actual,
        "etapa_fallida": trabajo.etapa_fallida,
        "etapas_completadas": trabajo.etapas_completadas,
    }


@router.post("/trabajos/{trabajo_id}/iniciar")
def iniciar_trabajo(
    trabajo_id: int,
    reporte: ReporteAgente,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    trabajo = db.get(TrabajoRobot, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo.agente_id not in (None, reporte.agent_id):
        raise HTTPException(status_code=409, detail="Trabajo reclamado por otro agente")
    if trabajo.estado not in ("PENDIENTE", "RECLAMADO"):
        raise HTTPException(status_code=409, detail=f"Estado actual: {trabajo.estado}")
    trabajo.estado = "EN_EJECUCION"
    trabajo.agente_id = reporte.agent_id
    trabajo.fecha_inicio = utc_now()
    estado = obtener_estado(db, reporte.agent_id)
    estado.estado = "EJECUTANDO"
    estado.detalle = reporte.detalle
    estado.trabajo_actual_id = trabajo.id
    registrar_evento(db, reporte.agent_id, "EJECUCION_INICIADA", reporte.detalle, trabajo.id)
    db.commit()
    return {"success": True, "estado": trabajo.estado}


@router.post("/trabajos/{trabajo_id}/finalizar")
def finalizar_trabajo(
    trabajo_id: int,
    reporte: ReporteAgente,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    trabajo = db.get(TrabajoRobot, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo.agente_id not in (None, reporte.agent_id):
        raise HTTPException(status_code=409, detail="Trabajo reclamado por otro agente")
    permitido = {"COMPLETADO", "EJECUCION_COMPLETADA", "EJECUCION_ERROR",
                 "ESTADO_NO_CONFIRMADO", "ROBOT_PREPARADO"}
    if reporte.estado not in permitido:
        raise HTTPException(status_code=422, detail="Estado de finalización no permitido")

    es_completado = reporte.estado in ("COMPLETADO", "EJECUCION_COMPLETADA")
    trabajo.estado = "COMPLETADO" if es_completado else reporte.estado
    trabajo.mensaje = reporte.detalle
    trabajo.fecha_finalizacion = utc_now()
    estado = obtener_estado(db, reporte.agent_id)
    estado.estado = reporte.estado
    estado.detalle = reporte.detalle
    estado.trabajo_actual_id = None
    registrar_evento(db, reporte.agent_id, reporte.estado, reporte.detalle, trabajo.id)
    db.commit()
    return {"success": True, "estado": trabajo.estado}


@router.post("/trabajos/{trabajo_id}/error")
def registrar_error(
    trabajo_id: int,
    reporte: ReporteAgente,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    trabajo = db.get(TrabajoRobot, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo.agente_id not in (None, reporte.agent_id):
        raise HTTPException(status_code=409, detail="Trabajo reclamado por otro agente")

    if trabajo.intentos < trabajo.intentos_maximos:
        trabajo.estado = "PENDIENTE"
        trabajo.agente_id = None
        trabajo.fecha_reclamado = None
        trabajo.fecha_expiracion = utc_now() + timedelta(
            minutes=int(os.getenv("JOB_LEASE_MINUTES", "15"))
        )
    else:
        trabajo.estado = "ERROR"
        trabajo.fecha_finalizacion = utc_now()
    trabajo.mensaje = reporte.detalle
    estado = obtener_estado(db, reporte.agent_id)
    estado.estado = "EJECUCION_ERROR"
    estado.detalle = reporte.detalle
    estado.trabajo_actual_id = None
    registrar_evento(db, reporte.agent_id, "EJECUCION_ERROR", reporte.detalle, trabajo.id)
    db.commit()
    return {"success": True, "estado": trabajo.estado}


@router.post("/trabajos/{trabajo_id}/etapa")
def registrar_etapa(
    trabajo_id: int,
    reporte: ReporteEtapa,
    db: Session = Depends(get_db),
    _auth: str = Depends(verificar_agente),
):
    trabajo = db.get(TrabajoRobot, trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo.agente_id not in (None, reporte.agent_id):
        raise HTTPException(status_code=409, detail="Trabajo reclamado por otro agente")

    if reporte.estado in ("COMPLETADA", "COMPLETADO", "OK"):
        completadas: list[str] = []
        if trabajo.etapas_completadas:
            try:
                completadas = json.loads(trabajo.etapas_completadas)
            except json.JSONDecodeError:
                completadas = []
        if reporte.etapa not in completadas:
            completadas.append(reporte.etapa)
        trabajo.etapas_completadas = json.dumps(completadas, ensure_ascii=False)
        trabajo.etapa_actual = reporte.etapa
        trabajo.etapa_fallida = None
        evento = "ETAPA_COMPLETADA"
    elif reporte.estado in ("ERROR", "FALLIDA", "EJECUCION_ERROR"):
        trabajo.etapa_actual = reporte.etapa
        trabajo.etapa_fallida = reporte.etapa
        evento = "ETAPA_FALLIDA"
    else:
        raise HTTPException(status_code=422, detail="Estado de etapa no permitido")

    registrar_evento(
        db,
        reporte.agent_id,
        evento,
        reporte.detalle,
        trabajo.id,
    )
    db.commit()
    return {
        "success": True,
        "etapa_actual": trabajo.etapa_actual,
        "etapa_fallida": trabajo.etapa_fallida,
        "etapas_completadas": trabajo.etapas_completadas,
    }
