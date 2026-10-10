-- Jalankan sebagai superuser setelah seluruh tabel terisi.
-- Pemakaian: psql -v ai_password="'rahasia'" -f db/02_readonly_role.sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_ai_executor') THEN
        CREATE ROLE readonly_ai_executor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

ALTER ROLE readonly_ai_executor PASSWORD :ai_password;
ALTER ROLE readonly_ai_executor SET default_transaction_read_only = on;
ALTER ROLE readonly_ai_executor SET statement_timeout = '5s';

REVOKE ALL ON ALL TABLES IN SCHEMA public, umkm FROM readonly_ai_executor;
GRANT USAGE ON SCHEMA public, umkm TO readonly_ai_executor;
GRANT SELECT ON
    umkm.umkm,
    umkm.jenis_umkm,
    public.provinces,
    public.regencies,
    public.districts,
    public.villages
TO readonly_ai_executor;
