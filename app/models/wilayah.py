from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Double, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Province(Base):
    __tablename__ = "provinces"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    alt_name: Mapped[str] = mapped_column(String, default="")
    latitude: Mapped[float] = mapped_column(Double, default=0)
    longitude: Mapped[float] = mapped_column(Double, default=0)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class Regency(Base):
    __tablename__ = "regencies"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    province_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    alt_name: Mapped[str] = mapped_column(String, default="")
    latitude: Mapped[float] = mapped_column(Double, default=0)
    longitude: Mapped[float] = mapped_column(Double, default=0)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    regency_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    alt_name: Mapped[str] = mapped_column(String, default="")
    latitude: Mapped[float] = mapped_column(Double, default=0)
    longitude: Mapped[float] = mapped_column(Double, default=0)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class Village(Base):
    __tablename__ = "villages"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    alt_name: Mapped[str] = mapped_column(String, default="")
    latitude: Mapped[float] = mapped_column(Double, default=0)
    longitude: Mapped[float] = mapped_column(Double, default=0)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)