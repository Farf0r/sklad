import logging

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.material import Material
from app.models.unit import Unit
from app.schemas.unit import UnitIn

logger = logging.getLogger(__name__)


def list_units(db: Session) -> list[Unit]:
    return list(db.scalars(select(Unit).order_by(Unit.name)))


def get_unit(db: Session, unit_id: int) -> Unit:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise NotFoundError(f"Единица измерения {unit_id} не найдена")
    return unit


def check_unique(db: Session, data: UnitIn, exclude_id: int | None = None):
    query = select(Unit).where(or_(Unit.name == data.name, Unit.short_name == data.short_name))
    if exclude_id is not None:
        query = query.where(Unit.id != exclude_id)
    if db.scalar(query.limit(1)):
        raise ConflictError("Единица измерения с таким названием или сокращением уже есть")


def create_unit(db: Session, data: UnitIn) -> Unit:
    check_unique(db, data)
    unit = Unit(**data.model_dump())
    db.add(unit)
    db.commit()
    logger.info("добавлена единица измерения %s (id=%s)", unit.short_name, unit.id)
    return unit


def update_unit(db: Session, unit_id: int, data: UnitIn) -> Unit:
    unit = get_unit(db, unit_id)
    check_unique(db, data, exclude_id=unit_id)
    unit.name = data.name
    unit.short_name = data.short_name
    db.commit()
    logger.info("изменена единица измерения id=%s", unit_id)
    return unit


def delete_unit(db: Session, unit_id: int):
    unit = get_unit(db, unit_id)
    used = db.scalar(select(func.count()).where(Material.unit_id == unit_id))
    if used:
        raise ConflictError(f"Нельзя удалить: единица измерения используется в материалах ({used})")
    db.delete(unit)
    db.commit()
    logger.info("удалена единица измерения id=%s", unit_id)
