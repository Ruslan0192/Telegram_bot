from sqlalchemy import DateTime, Float, String, Text, func, ForeignKey, Column, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from word.temp_word import read_doc

class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id_tel: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)


class Calculation(Base):
    #читаю список параметров из файла
    list_param = read_doc()
    list_param = list_param[0]
    # print(list_param)

    __tablename__ = 'calculations'
    __table_args__ = {'extend_existing': True}
    # Создаем список из необходимых колонок
    columns = [Column(column, Float(), nullable=False) for column in list_param]

    # Распаковываем колонки в таблицу
    data = Table(
        'calculations',
        Base.metadata,
        Column('id', Integer(), primary_key=True),
        Column('id_user', Integer(), ForeignKey("users.user_id_tel"), nullable=False),
        Column('payments', Float(), ),
        Column('payment_id', String()),
        *columns
    )
