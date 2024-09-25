# Marketing\app\models.py

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash
import sqlalchemy as sa

from app.database import db
from app.errors import UserAlreadyExist, UserDoesntExist, CustomerAlreadyExist

class Agency(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(60), unique=True)
    password: Mapped[str]
    lex_acces: Mapped[List["LexAcc"]] = relationship(
            back_populates="agency", cascade="all, delete-orphan", default_factory=list
            )
    manual: Mapped[List["Manual"]] = relationship(
            back_populates="agency", cascade="all, delete-orphan", default_factory=list
            )
    bank_connections: Mapped[List["BankConnection"]] = relationship(
            back_populates="agency", cascade="all, delete-orphan", default_factory=list
            )
    mail_users: Mapped[List["MailUser"]] = relationship(
            back_populates="agency", cascade="all, delete-orphan", default_factory=list
            )
    google_ads_accounts: Mapped[List["GoogleAdsAccount"]] = relationship(
            back_populates="agency", cascade="all, delete-orphan", default_factory=list
            )
    
    @staticmethod
    def create_agency(email, password):
        try:
            existingUser = Agency.get_agency_from_email(email)
            if existingUser:
                raise UserAlreadyExist("User with this email already exist", "danger")
        except UserDoesntExist:
            hdPassword = Agency.generate_password(password)
            newUser = Agency(email=email, password=hdPassword)
            db.session.add(newUser)

    @staticmethod
    def get_agency_from_email(email):
        existingUser = db.session.execute(
                db.select(Agency).filter_by(email=email)
                ).scalar_one_or_none()
        if not existingUser:
            raise UserDoesntExist("User with this email doesn't exist", "danger")
        return existingUser

    def check_password(self, password):
        return check_password_hash(self.password, password)

    @staticmethod
    def generate_password(password):
        return generate_password_hash(password)

class LexAcc(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    orgID: Mapped[str] = mapped_column(unique=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agency.id"))
    agency: Mapped["Agency"] = relationship(back_populates="lex_acces")
    customers: Mapped[Optional[List["Customer"]]] = relationship(
            back_populates="lexAcc", cascade="all, delete-orphan"
            )
    name: Mapped[str]
    source: Mapped[str] = mapped_column(nullable=False)
    eventID: Mapped[Optional[str]]
    added_on: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def add_customer(self, lexID, name):
        existingCustomer = db.session.execute(
                db.select(Customer).filter_by(lexID=lexID)
                ).scalar_one_or_none()
        if existingCustomer:
            raise CustomerAlreadyExist("Customer already exist.", "danger")
        newCustomer = Customer(lexID=lexID, lexAccId=self.id, lexAcc=self, name=name)
        db.session.add(newCustomer)
        return newCustomer

class Customer(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    lexID: Mapped[str] = mapped_column(unique=True)
    lexAccId: Mapped[int] = mapped_column(ForeignKey("lex_acc.id"))
    lexAcc: Mapped["LexAcc"] = relationship(back_populates="customers")
    name: Mapped[str]
    totalGrossAmount: Mapped[float] = mapped_column(
            nullable=False,
            default=0.0
            )
    totalNetAmount: Mapped[float] = mapped_column(
            nullable=False,
            default=0.0
            )
    addedOn: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def add_invoice_amounts(self, grossAmount, netAmount):
        self.totalGrossAmount += grossAmount
        self.totalNetAmount += netAmount

class Manual(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agency.id"))
    agency: Mapped["Agency"] = relationship(back_populates="manual")
    identifier: Mapped[str] = mapped_column(unique=True)
    source: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str]
    totalAmount: Mapped[float] = mapped_column(
            nullable=False,
            default=0.0
            )
    addedOn: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class BankConnection(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agency.id"), nullable=False)
    finapi_connection_id: Mapped[int] = mapped_column(nullable=False)
    bank_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    last_sync: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class BankAccount(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("bank_connection.id"), nullable=False)
    finapi_account_id: Mapped[int] = mapped_column(nullable=False)
    account_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    iban: Mapped[str] = mapped_column(sa.String(34))

class BankTransaction(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("bank_account.id"), nullable=False)
    finapi_transaction_id: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(255))
    booking_date: Mapped[datetime] = mapped_column(nullable=False)
    value_date: Mapped[datetime] = mapped_column(nullable=False)


class MailUser(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(120), unique=True)
    password: Mapped[str] = mapped_column(sa.String(255))
    domain: Mapped[str] = mapped_column(sa.String(50))
    folder: Mapped[str] = mapped_column(sa.String(50))
    agency_id: Mapped[int] = mapped_column(sa.ForeignKey('agency.id'))
    agency: Mapped["Agency"] = relationship(back_populates="mail_users")
    emails: Mapped[List["Email"]] = relationship(back_populates="mail_user", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<MailUser {self.email}>'


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id'), nullable=False)

    def __repr__(self):
        return f'<Attachment {self.filename}>'

class GoogleAdsAccount(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(sa.String(20), unique=True)
    refresh_token: Mapped[str] = mapped_column(sa.String(256))
    agency_id: Mapped[int] = mapped_column(sa.ForeignKey("agency.id"))
    agency: Mapped["Agency"] = relationship(back_populates="google_ads_accounts")
    campaigns: Mapped[List["GoogleAdsCampaign"]] = relationship(back_populates="account", cascade="all, delete-orphan")

class GoogleAdsCampaign(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(sa.String(20), unique=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    status: Mapped[str] = mapped_column(sa.String(20))
    budget: Mapped[float]
    account_id: Mapped[int] = mapped_column(sa.ForeignKey("google_ads_account.id"))
    account: Mapped["GoogleAdsAccount"] = relationship(back_populates="campaigns")



class Email(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(sa.String(255))
    sender: Mapped[str] = mapped_column(sa.String(100))
    recipient: Mapped[str] = mapped_column(sa.String(100))
    date: Mapped[datetime]
    content: Mapped[str] = mapped_column(sa.Text)
    mail_user_id: Mapped[int] = mapped_column(sa.ForeignKey("mail_user.id"))
    mail_user: Mapped["MailUser"] = relationship(back_populates="emails")

    def __repr__(self):
        return f'<Email {self.subject}>'

class DataAnalysis(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(sa.ForeignKey("agency.id"))
    agency: Mapped["Agency"] = relationship()
    analysis_type: Mapped[str] = mapped_column(sa.String(50))
    result: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)



