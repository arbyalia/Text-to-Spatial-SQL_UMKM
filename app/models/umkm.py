from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Double, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JenisUmkm(Base):
    __tablename__ = "jenis_umkm"
    __table_args__ = {"schema": "umkm"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class Umkm(Base):
    __tablename__ = "umkm"
    __table_args__ = {"schema": "umkm"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    alamat: Mapped[str | None] = mapped_column(String(250), nullable=True)
    pinggir_jalan: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    dekat_fasilitas: Mapped[str | None] = mapped_column(String(250), nullable=True)
    rating: Mapped[float | None] = mapped_column(Double, nullable=True)
    jml_ulasan: Mapped[int] = mapped_column(Integer, nullable=False)
    district_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    jenis_umkm_id: Mapped[int] = mapped_column(Integer, nullable=False)