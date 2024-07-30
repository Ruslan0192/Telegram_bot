
from sqlalchemy import select, update, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Calculation


async def orm_get_users(session: AsyncSession):
    query = select(User)
    result = await session.execute(query)
    return result.scalars().all()

# поиск пользователя
async def orm_get_user(session: AsyncSession, user_id: int):
    query = select(User).where(User.user_id_tel == user_id)
    result = await session.execute(query)
    return result.scalar()

async def orm_add_user(session: AsyncSession,user_id: int, name: str):
    obj = User(
        user_id_tel=user_id,
        name=name
    )
    session.add(obj)
    await session.commit()

async def orm_add_calculation(session: AsyncSession, data: dict):
    stmt = insert(Calculation).values(**data)
    result = await session.execute(stmt)
    calc_id = result.inserted_primary_key[0]
    await session.commit()
    return calc_id

async def orm_get_calculations(session: AsyncSession, user_id: int):
    query = select(Calculation).where(Calculation.id_user == user_id)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_get_calculation(session: AsyncSession, id_calc: int):
    query = select(Calculation).where(Calculation.id == id_calc)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_delete_calculation(session: AsyncSession, id_calc: int):
    query = delete(Calculation).where(Calculation.id == id_calc)
    await session.execute(query)
    await session.commit()


async def orm_add_payment(session: AsyncSession, calculation_id: int, payment: float, payment_id: str):
    query = update(Calculation).where(Calculation.id == calculation_id).values(
        payments=payment,
        payment_id=payment_id)

    await session.execute(query)
    await session.commit()
