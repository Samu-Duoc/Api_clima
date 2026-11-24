
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    pg_values = {
        name: os.getenv(name)
        for name in ("PGUSER", "PGPASSWORD", "PGHOST", "PGPORT", "PGDATABASE")
    }
    missing = [name for name, value in pg_values.items() if not value]
    if missing:
        raise ValueError(
            "Faltan variables de PostgreSQL en el archivo .env: "
            + ", ".join(missing)
        )

    DATABASE_URL = URL.create(
        "postgresql+psycopg",
        username=pg_values["PGUSER"],
        password=pg_values["PGPASSWORD"],
        host=pg_values["PGHOST"],
        port=int(pg_values["PGPORT"]),
        database=pg_values["PGDATABASE"],
        query={
            "sslmode": os.getenv("PGSSLMODE", "require"),
            "channel_binding": "require",
        },
    )

# Conexión a PostgreSQL (Neon)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# Dependencia para utilizar sesiones en los endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Prueba de conexión
def test_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))
        return result.scalar()


def create_tables():
    Base.metadata.create_all(bind=engine)
    migraciones = (
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS clave_unica VARCHAR(64)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS ciudad VARCHAR(255)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS viento_direccion VARCHAR(30)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS presion NUMERIC(7, 2)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS radiacion_uv NUMERIC(7, 2)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS calidad_aire_pm25 NUMERIC(7, 2)",
        "ALTER TABLE registros_clima ADD COLUMN IF NOT EXISTS fecha_ingesta TIMESTAMPTZ",
        "ALTER TABLE registros_clima ALTER COLUMN temperatura DROP NOT NULL",
        "ALTER TABLE registros_clima ALTER COLUMN humedad DROP NOT NULL",
        "ALTER TABLE registros_clima ALTER COLUMN velocidad_viento DROP NOT NULL",
        "ALTER TABLE registros_clima ALTER COLUMN precipitacion DROP NOT NULL",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS id_externo VARCHAR(100)",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS semaforo VARCHAR(30)",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS longitud NUMERIC(9, 4)",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS latitud NUMERIC(9, 4)",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS url_usgs TEXT",
        "ALTER TABLE registros_sismos ADD COLUMN IF NOT EXISTS fecha_ingesta TIMESTAMPTZ",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS clave_ejecucion VARCHAR(64)",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS computador VARCHAR(255)",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS origen VARCHAR(50)",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS estaciones_procesadas INTEGER",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS alertas_detectadas INTEGER",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS semaforo_global VARCHAR(50)",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS semaforos TEXT",
        "ALTER TABLE ejecuciones_robot ADD COLUMN IF NOT EXISTS totem_exp_epoch BIGINT",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_registros_clima_clave_unica "
        "ON registros_clima (clave_unica) WHERE clave_unica IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_registros_sismos_id_externo "
        "ON registros_sismos (id_externo) WHERE id_externo IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_ejecuciones_robot_clave "
        "ON ejecuciones_robot (clave_ejecucion) WHERE clave_ejecucion IS NOT NULL",
        "ALTER TABLE trabajos_robot ADD COLUMN IF NOT EXISTS etapa_actual VARCHAR(100)",
        "ALTER TABLE trabajos_robot ADD COLUMN IF NOT EXISTS etapa_fallida VARCHAR(100)",
        "ALTER TABLE trabajos_robot ADD COLUMN IF NOT EXISTS etapas_completadas TEXT",
    )
    with engine.begin() as connection:
        for statement in migraciones:
            connection.execute(text(statement))
