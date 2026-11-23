from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegistroClima(Base):
    __tablename__ = "registros_clima"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave_unica: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ubicacion: Mapped[str] = mapped_column(String(255), nullable=False)
    ciudad: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temperatura: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    humedad: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    velocidad_viento: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    viento_direccion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    presion: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    radiacion_uv: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    calidad_aire_pm25: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    precipitacion: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_ingesta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_registros_clima_ubicacion_fecha", "ubicacion", "fecha_registro"),
        Index("ux_registros_clima_clave_unica", "clave_unica", unique=True),
        Index("ix_registros_clima_ciudad_fecha", "ciudad", "fecha_ingesta"),
    )


class RegistroSismo(Base):
    __tablename__ = "registros_sismos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_externo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    magnitud: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    profundidad: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(255), nullable=False)
    referencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    semaforo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    longitud: Mapped[float | None] = mapped_column(Numeric(9, 4), nullable=True)
    latitud: Mapped[float | None] = mapped_column(Numeric(9, 4), nullable=True)
    url_usgs: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_ingesta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_evento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_registros_sismos_ubicacion_fecha", "ubicacion", "fecha_evento"),
        Index("ux_registros_sismos_id_externo", "id_externo", unique=True),
        Index("ix_registros_sismos_magnitud", "magnitud"),
    )


class UmbralClima(Base):
    __tablename__ = "umbrales_clima"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parametro: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    valor_minimo: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    valor_maximo: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    unidad: Mapped[str] = mapped_column(String(30), nullable=False)
    nivel: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )


class EjecucionRobot(Base):
    __tablename__ = "ejecuciones_robot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave_ejecucion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computador: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origen: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estaciones_procesadas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alertas_detectadas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semaforo_global: Mapped[str | None] = mapped_column(String(50), nullable=True)
    semaforos: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    fecha_fin: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estado: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    archivos_generados: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class TrabajoRobot(Base):
    __tablename__ = "trabajos_robot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave_solicitud: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False, default="CARGAR_NUEVO_TOKEN")
    robot: Mapped[str] = mapped_column(String(100), nullable=False, default="Clima")
    origen: Mapped[str] = mapped_column(String(50), nullable=False, default="dashboard")
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDIENTE", index=True)
    agente_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intentos_maximos: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    fecha_reclamado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_expiracion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_finalizacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    etapa_actual: Mapped[str | None] = mapped_column(String(100), nullable=True)
    etapa_fallida: Mapped[str | None] = mapped_column(String(100), nullable=True)
    etapas_completadas: Mapped[str | None] = mapped_column(Text, nullable=True)


class EstadoSupervisor(Base):
    __tablename__ = "estado_supervisor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agente_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    estado: Mapped[str] = mapped_column(String(50), nullable=False, default="DESCONECTADO")
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    ultimo_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trabajo_actual_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class EventoSupervisor(Base):
    __tablename__ = "eventos_supervisor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agente_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trabajo_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    evento: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
