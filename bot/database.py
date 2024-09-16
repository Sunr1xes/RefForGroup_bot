from contextlib import asynccontextmanager
import logging
from sqlalchemy import ForeignKey, Column, Integer, String, TIMESTAMP, Float, BigInteger, func, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from config import DATABASE_URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    first_name_tg = Column(String, nullable=False)
    last_name_tg = Column(String, nullable=True)
    last_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    patronymic = Column(String, nullable=True)
    phone_number = Column(String, nullable=False, unique=True)
    referrer_id = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'))
    referral_earnings = Column(Float, default=0.0)
    work_earnings = Column(Float, default=0.0)
    account_balance = Column(Float, default=0.0)

    referrals = relationship('Referral', foreign_keys='Referral.user_id', back_populates='user', cascade='all, delete')
    withdrawals = relationship('WithdrawalHistory', back_populates='user', cascade='all, delete')
    receipt_history = relationship('ReceiptHistory', back_populates='user', cascade='all, delete')  # Добавлено отношение


    __table_args__ = (
        Index('idx_user_id', 'user_id', unique=True),
    )

    def __repr__(self):
        return f"<User(id={self.id}, user_id={self.user_id}, first_name='{self.first_name}', last_name='{self.last_name}', phone_number={self.phone_number})>"

class Referral(Base):
    __tablename__ = 'referrals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    referral_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date_joined = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates='referrals')
    referral_user = relationship("User", foreign_keys=[referral_id])

    __table_args__ = (
        UniqueConstraint('user_id', 'referral_id', name='_user_referral_uc'),  # Уникальность рефералов
    )

    def __repr__(self):
        return f"<Referral(id={self.id}, user_id={self.user_id}, referral_id={self.referral_id}, date_joined={self.date_joined})>"

class WithdrawalHistory(Base):
    __tablename__ = 'withdrawal_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    withdrawal_date = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(String(20), default='pending')
    is_urgent = Column(Boolean, default=False)

    user = relationship("User", back_populates="withdrawals")

    def __repr__(self):
        return f"<WithdrawalHistory(id={self.id}, user_id={self.user_id}, amount={self.amount}, withdrawal_date={self.withdrawal_date}, status={self.status})>"

class Vacancy(Base):
    __tablename__ = 'vacancies'

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор вакансии
    chat_id = Column(BigInteger, nullable=False, index=True)  # Идентификатор чата, откуда взята вакансия
    message_id = Column(BigInteger, nullable=False)  # Идентификатор сообщения с вакансией в чате
    text = Column(Text, nullable=False)  # Текст вакансии
    posted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Дата публикации вакансии
    status = Column(String(20), default='active')  # Статус вакансии (active/inactive)

    __table_args__ = (
        Index('idx_chat_message', 'chat_id', 'message_id'),
    )
    def __repr__(self):
        return f"<Vacancy(id={self.id}, chat_id={self.chat_id}, message_id={self.message_id}, status={self.status})>"


class BlackList(Base):
    __tablename__ = 'blacklist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    date = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', name='_user_uc'),
        Index('idx_user_id_blacklist', 'user_id')
    )
    def __repr__(self):
        return f"<BlackList(id={self.id}, user_id={self.user_id}, chat_id={self.chat_id}, date={self.date})>"
    

class ReceiptHistory(Base):
    __tablename__ = 'receipt_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)  # Связь с таблицей пользователей
    amount = Column(Float, nullable=False)
    date = Column(TIMESTAMP(timezone=True), server_default=func.now())
    description = Column(Text, nullable=True)

    # Связь с таблицей пользователей
    user = relationship("User", back_populates="receipt_history")

    __table_args__ = (
        Index('idx_receipt_user_id', 'user_id'),  # Индекс на поле user_id
        Index('idx_receipt_date', 'date'),  # Индекс на поле timestamp
    )

    def __repr__(self):
        return f"<ReceiptHistory(id={self.id}, user_id={self.user_id}, amount={self.amount}, date={self.date})>"


engine = create_async_engine(DATABASE_URL) # type: ignore

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

async def init_db():
    async with engine.begin() as conn:
        try:
            # Удаление индексов вручную перед созданием (если нужно)
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)  # Пересоздание таблиц и индексов
            logging.info("Таблицы и индексы успешно созданы")
        except SQLAlchemyError as e:
            logging.error(f"Error initializing database: {e}")


@asynccontextmanager
async def get_async_session():
    async with async_session() as session: # type: ignore
        try:
            yield session
        finally:
            await session.close()
