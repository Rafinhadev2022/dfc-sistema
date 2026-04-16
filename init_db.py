"""
Executa UMA VEZ para criar o banco e popular com dados padrão.
Uso: python3 init_db.py
"""
from app import app, db
from models import User, Category, Contract, Transaction
from werkzeug.security import generate_password_hash
from datetime import date

with app.app_context():
    db.create_all()

    # ── Usuário admin padrão ────────────────────────────────────────────────
    if not User.query.filter_by(email='admin@dfc.com').first():
        admin = User(
            name='Administrador',
            email='admin@dfc.com',
            password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print('✓ Usuário admin criado: admin@dfc.com / admin123')
    else:
        print('  Usuário admin já existe.')

    # ── Categorias padrão (setor de pavimentação asfáltica) ─────────────────
    categorias_entrada = [
        'Recebimento de Medição',
        'Antecipação de Contrato',
        'Adiantamento',
        'Reembolso de Despesas',
        'Outras Receitas',
    ]
    categorias_saida = [
        'Folha de Pagamento',
        'INSS / FGTS',
        'ISS',
        'IRPJ / CSLL',
        'PIS / COFINS',
        'CBUQ / Massa Asfáltica',
        'Emulsão Asfáltica',
        'Combustível',
        'Manutenção de Equipamentos',
        'Aluguel de Equipamentos',
        'Subempreiteiros',
        'Material de Construção',
        'Sinalização / EPI',
        'Despesas Administrativas',
        'Aluguel / Sede',
        'Contador / Assessoria',
        'Outras Despesas',
    ]

    created = 0
    for name in categorias_entrada:
        if not Category.query.filter_by(name=name, type='entrada').first():
            db.session.add(Category(name=name, type='entrada', active=True))
            created += 1
    for name in categorias_saida:
        if not Category.query.filter_by(name=name, type='saida').first():
            db.session.add(Category(name=name, type='saida', active=True))
            created += 1
    db.session.commit()
    print(f'✓ {created} categorias criadas.')

    print('\n✅ Banco inicializado com sucesso!')
    print('   Acesse: http://localhost:5000')
    print('   Login:  admin@dfc.com')
    print('   Senha:  admin123')
