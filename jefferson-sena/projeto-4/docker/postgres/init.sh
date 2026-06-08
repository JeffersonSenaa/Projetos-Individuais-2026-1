#!/usr/bin/env bash
# Executado apenas na primeira criação do volume PostgreSQL.
set -e
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE DATABASE uda_habitacional;
EOSQL
