-- Jalankan sebagai superuser sebelum load wilayah dan restore backup_umkm.sql.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS umkm;

CREATE TABLE IF NOT EXISTS umkm.jenis_umkm (
    id   SERIAL PRIMARY KEY,
    nama VARCHAR(100) NOT NULL UNIQUE
);

INSERT INTO umkm.jenis_umkm (id, nama) VALUES (1, 'Coffee Shop')
ON CONFLICT (id) DO NOTHING;

SELECT setval('umkm.jenis_umkm_id_seq', (SELECT MAX(id) FROM umkm.jenis_umkm));
