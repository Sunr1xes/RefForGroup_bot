from contextlib import asynccontextmanager
import logging
from sqlalchemy import ForeignKey, Column, Integer, String, TIMESTAMP, Float, BigInteger, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    first_name_tg = Column(String, nullable=False)
    last_name_tg = Column(String, nullable=True)
    last_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    patronymic = Column(String, nullable=True)
    phone_number = Column(String, nullable=False)
    referrer_id = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'))
    referral_earnings = Column(Float, default=0.0)
    account_balance = Column(Float, default=0.0)

    referrals = relationship('Referral', foreign_keys='Referral.user_id', back_populates='user', cascade='all, delete')

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

    def __repr__(self):
        return f"<Referral(id={self.id}, user_id={self.user_id}, referral_id={self.referral_id}, date_joined={self.date_joined})>"

engine = create_async_engine(DATABASE_URL) # type: ignore

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except SQLAlchemyError as e:
            logging.error(f"Error initializing database: {e}")

@asynccontextmanager
async def get_async_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
