from asyncio.log import logger
from sqlalchemy import ForeignKey, create_engine, Column, Integer, String, TIMESTAMP, Float, BigInteger, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

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

engine = create_engine(DATABASE_URL) # type: ignore
try:
    Base.metadata.create_all(engine)
except SQLAlchemyError as e:
    logger.error(f"Error creating tables: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
