from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClimaEntrada(BaseModel):
    model_config = ConfigDict(extra="allow")

    ciudad: str = Field(min_length=1, max_length=255)
    temperatura: float | None = None
    humedad: float | None = None
    viento_velocidad: float | None = None
    viento_direccion: str | None = None
    presion: float | None = None
    radiacion_uv: float | None = None
    calidad_aire_pm25: float | None = None
    precipitacion_mm: float | None = None
    condicion: str | None = None


class SismoEntrada(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=100)
    lugar: str = Field(min_length=1, max_length=255)
    magnitud: float
    semaforo: str | None = None
    hora: datetime
    longitud: float | None = None
    latitud: float | None = None
    profundidad_km: float
    url_usgs: str | None = None


class ClimaExterno(BaseModel):
    model_config = ConfigDict(extra="allow")

    fecha_ingesta: datetime | None = None
    clima: list[ClimaEntrada] = Field(default_factory=list)


class SismoExterno(BaseModel):
    model_config = ConfigDict(extra="allow")

    fecha_ingesta: datetime | None = None
    sismo: SismoEntrada


class DatosExterno(BaseModel):
    model_config = ConfigDict(extra="allow")

    clima: list[ClimaExterno | dict[str, Any]] = Field(default_factory=list)
    sismos: list[SismoExterno | dict[str, Any]] = Field(default_factory=list)


class RecepcionRobot(BaseModel):
    model_config = ConfigDict(extra="allow")

    origen: str | None = None
    ejecucion: str | None = None
    timestamp: datetime | None = None
    status: str | None = None
    estaciones_procesadas: int | None = Field(default=None, ge=0)
    alertas_detectadas: int | None = Field(default=None, ge=0)
    semaforo_global: str | None = None
    semaforos: dict[str, Any] | list[Any] | None = None
    totem_exp_epoch: int | None = Field(default=None, ge=0)
    estaciones: list[dict[str, Any]] | None = None
    archivos: dict[str, Any] | list[Any] | str | None = None
    drive_link: str | None = None
    ejecucion_id: str | None = None
    clave_ejecucion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_ejecucion: datetime | None = None
    estado: str = "completada"
    mensaje: str | None = None
    computador: str | None = None
    archivos_generados: dict[str, Any] | list[Any] | str | None = None
    enlaces_drive: dict[str, str] | None = None
    data: DatosExterno | None = None
    clima: list[ClimaExterno | dict[str, Any]] | None = None
    sismos: list[SismoExterno | dict[str, Any]] | None = None
