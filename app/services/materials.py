import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.material import Material
from app.schemas.material import MaterialIn
from app.services.units import get_unit

logger = logging.getLogger(__name__)


def list_materials(db: Session) -> list[Material]:
    return list(db.scalars(select(Material).order_by(Material.name)))


def get_material(db: Session, material_id: int) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise NotFoundError(f"Материал {material_id} не найден")
    return material


def check_unique(db: Session, name: str, exclude_id: int | None = None):
    query = select(Material).where(Material.name == name)
    if exclude_id is not None:
        query = query.where(Material.id != exclude_id)
    if db.scalar(query.limit(1)):
        raise ConflictError(f"Материал «{name}» уже есть")


def create_material(db: Session, data: MaterialIn) -> Material:
    get_unit(db, data.unit_id)
    check_unique(db, data.name)
    material = Material(name=data.name, unit_id=data.unit_id, description=data.description or None)
    db.add(material)
    db.commit()
    db.refresh(material)
    logger.info("добавлен материал %s (id=%s)", material.name, material.id)
    return material


def update_material(db: Session, material_id: int, data: MaterialIn) -> Material:
    # остаток здесь не меняется: он растёт только при проведении поступления
    material = get_material(db, material_id)
    get_unit(db, data.unit_id)
    check_unique(db, data.name, exclude_id=material_id)
    material.name = data.name
    material.unit_id = data.unit_id
    material.description = data.description or None
    db.commit()
    db.refresh(material)
    logger.info("изменён материал id=%s", material_id)
    return material


def delete_material(db: Session, material_id: int):
    material = get_material(db, material_id)
    if material.stock > 0:
        raise ConflictError("Нельзя удалить материал, пока он есть на складе")
    db.delete(material)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Нельзя удалить: материал используется в поступлениях") from None
    logger.info("удалён материал id=%s", material_id)
