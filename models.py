from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import secrets

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, editor, viewer
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def is_admin(self):
        return self.role == 'admin'

    def can_edit(self):
        return self.role in ('admin', 'editor')

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='reset_tokens')

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    active = db.Column(db.Boolean, default=True)
    transactions = db.relationship('Transaction', backref='category', lazy=True)
    projections = db.relationship('Projection', backref='category', lazy=True)

class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(60), nullable=False)
    client = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    value = db.Column(db.Float, nullable=False, default=0)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='ativo')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='contract', lazy=True)
    projections = db.relationship('Projection', backref='contract', lazy=True)

class CostCenter(db.Model):
    __tablename__ = 'cost_centers'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30))
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)
    status = db.Column(db.String(10), default='ativo')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='cost_center', lazy=True)
    bill_reminders = db.relationship('BillReminder', backref='cost_center', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(20))
    role = db.Column(db.String(100))           # cargo / função
    salary = db.Column(db.Float, default=0)    # salário base (referência)
    admission_date = db.Column(db.Date)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)
    phone = db.Column(db.String(30))
    notes = db.Column(db.Text)
    status = db.Column(db.String(15), default='ativo')  # ativo / demitido / afastado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contract = db.relationship('Contract', backref='employees', lazy=True)
    transactions = db.relationship('Transaction', backref='employee', lazy=True)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)            # razão social / nome
    trade_name = db.Column(db.String(200))                       # nome fantasia
    cnpj_cpf = db.Column(db.String(20))                          # CNPJ ou CPF
    category = db.Column(db.String(100))                         # tipo (asfalto, combustível, locação...)
    contact_name = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    bank_info = db.Column(db.String(255))                        # banco / agência / conta / PIX
    notes = db.Column(db.Text)
    status = db.Column(db.String(15), default='ativo')           # ativo / inativo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='supplier', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)
    cost_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(15), default='realizado')
    notes = db.Column(db.Text)
    attachment_data     = db.Column(db.LargeBinary)
    attachment_original = db.Column(db.String(255))
    attachment_mimetype = db.Column(db.String(100))
    reconciled          = db.Column(db.Boolean, default=False)
    reconciled_at       = db.Column(db.DateTime)
    bank_reference      = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BillReminder(db.Model):
    __tablename__ = 'bill_reminders'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    cost_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'), nullable=True)
    recurrence = db.Column(db.String(15), default='nenhuma')   # nenhuma / mensal / semanal
    status = db.Column(db.String(15), default='pendente')      # pendente / pago / atrasado / cancelado
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    attachment_data     = db.Column(db.LargeBinary)
    attachment_original = db.Column(db.String(255))
    attachment_mimetype = db.Column(db.String(100))
    category = db.relationship('Category', backref='bill_reminders', lazy=True)
    user = db.relationship('User', backref='bill_reminders', lazy=True)

class BankStatementEntry(db.Model):
    __tablename__ = 'bank_statement_entries'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255))
    value = db.Column(db.Float, nullable=False)  # sempre positivo
    type = db.Column(db.String(10), nullable=False)  # entrada / saida
    fit_id = db.Column(db.String(120))  # ID único do banco (OFX FITID)
    matched_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    matched_at = db.Column(db.DateTime)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    matched_transaction = db.relationship('Transaction', foreign_keys=[matched_transaction_id],
                                          backref=db.backref('bank_entry', uselist=False))

class Projection(db.Model):
    __tablename__ = 'projections'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)
    value = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
