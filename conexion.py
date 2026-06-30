"""Conexión a PostgreSQL leyendo la cadena del archivo .env."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parent / ".env")


def get_conn():
    """Devuelve una conexión psycopg a la base prosagro."""
    return psycopg.connect(os.environ["DATABASE_URL"])
