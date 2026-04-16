from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Category, Transaction, Contract, Projection
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
from sqlalchemy import func, extract
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dfc-sistema-chave-secreta-2024')

# Banco de dados: PostgreSQL em produção, SQLite local
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # SQLite: usa /tmp em produção (Render) ou pasta local
    db_path = os.path.join('/tmp', 'dfc.db') if os.environ.get('RENDER') else os.path.join(app.instance_path, 'dfc.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar o sistema.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_database():
    """Inicializa o banco com tabelas e dados padrão na primeira execução."""
    db.create_all()

    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'contatonuees@gmail.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'nunes2025#')

    admin = User.query.filter_by(role='admin').first()
    if admin:
        # Atualiza credenciais do admin existente
        admin.email = ADMIN_EMAIL
        admin.password_hash = generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256')
    else:
        db.session.add(User(
            name='Administrador',
            email=ADMIN_EMAIL,
            password_hash=generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256'),
            role='admin'
        ))
    categorias_entrada = ['Recebimento de Medição','Antecipação de Contrato',
        'Adiantamento','Reembolso de Despesas','Outras Receitas']
    categorias_saida = ['Folha de Pagamento','INSS / FGTS','ISS','IRPJ / CSLL',
        'PIS / COFINS','CBUQ / Massa Asfáltica','Emulsão Asfáltica','Combustível',
        'Manutenção de Equipamentos','Aluguel de Equipamentos','Subempreiteiros',
        'Material de Construção','Sinalização / EPI','Despesas Administrativas',
        'Aluguel / Sede','Contador / Assessoria','Outras Despesas']
    for name in categorias_entrada:
        if not Category.query.filter_by(name=name, type='entrada').first():
            db.session.add(Category(name=name, type='entrada', active=True))
    for name in categorias_saida:
        if not Category.query.filter_by(name=name, type='saida').first():
            db.session.add(Category(name=name, type='saida', active=True))
    db.session.commit()

with app.app_context():
    try:
        init_database()
    except Exception as e:
        print(f'[AVISO] Erro ao inicializar banco: {e}')

# ─── HEALTH CHECK ────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    import traceback
    try:
        db.session.execute(db.text('SELECT 1'))
        user_count = User.query.count()
        return jsonify({
            'status': 'ok',
            'db': str(app.config['SQLALCHEMY_DATABASE_URI']),
            'users': user_count,
            'render_env': os.environ.get('RENDER','not set')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e), 'trace': traceback.format_exc()}), 500

# ─── AUTH ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)
    fim_mes = (inicio_mes + relativedelta(months=1)) - timedelta(days=1)

    # Totais do mês atual
    entradas_mes = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'entrada',
        Transaction.date >= inicio_mes,
        Transaction.date <= fim_mes,
        Transaction.status == 'realizado'
    ).scalar() or 0

    saidas_mes = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'saida',
        Transaction.date >= inicio_mes,
        Transaction.date <= fim_mes,
        Transaction.status == 'realizado'
    ).scalar() or 0

    saldo_mes = entradas_mes - saidas_mes

    # Saldo acumulado total
    total_entradas = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'entrada',
        Transaction.status == 'realizado'
    ).scalar() or 0
    total_saidas = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'saida',
        Transaction.status == 'realizado'
    ).scalar() or 0
    saldo_total = total_entradas - total_saidas

    # Últimos 6 meses para gráfico
    meses_labels = []
    meses_entradas = []
    meses_saidas = []
    for i in range(5, -1, -1):
        mes_ref = hoje - relativedelta(months=i)
        inicio = mes_ref.replace(day=1)
        fim = (inicio + relativedelta(months=1)) - timedelta(days=1)
        e = db.session.query(func.sum(Transaction.value)).filter(
            Transaction.type == 'entrada',
            Transaction.date >= inicio,
            Transaction.date <= fim,
            Transaction.status == 'realizado'
        ).scalar() or 0
        s = db.session.query(func.sum(Transaction.value)).filter(
            Transaction.type == 'saida',
            Transaction.date >= inicio,
            Transaction.date <= fim,
            Transaction.status == 'realizado'
        ).scalar() or 0
        meses_labels.append(mes_ref.strftime('%b/%Y'))
        meses_entradas.append(float(e))
        meses_saidas.append(float(s))

    # Lançamentos recentes
    lancamentos_recentes = Transaction.query.order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(8).all()

    # Contratos ativos
    contratos_ativos = Contract.query.filter_by(status='ativo').count()

    # Previsão próximos 30 dias (projeções)
    hoje_dt = hoje
    fim_30 = hoje_dt + timedelta(days=30)
    prev_entradas = db.session.query(func.sum(Projection.value)).filter(
        Projection.type == 'entrada',
        Projection.date >= hoje_dt,
        Projection.date <= fim_30
    ).scalar() or 0
    prev_saidas = db.session.query(func.sum(Projection.value)).filter(
        Projection.type == 'saida',
        Projection.date >= hoje_dt,
        Projection.date <= fim_30
    ).scalar() or 0

    return render_template('dashboard.html',
        entradas_mes=entradas_mes, saidas_mes=saidas_mes,
        saldo_mes=saldo_mes, saldo_total=saldo_total,
        meses_labels=json.dumps(meses_labels),
        meses_entradas=json.dumps(meses_entradas),
        meses_saidas=json.dumps(meses_saidas),
        lancamentos_recentes=lancamentos_recentes,
        contratos_ativos=contratos_ativos,
        prev_entradas=prev_entradas, prev_saidas=prev_saidas,
        hoje=hoje
    )

# ─── LANÇAMENTOS ─────────────────────────────────────────────────────────────

@app.route('/lancamentos')
@login_required
def lancamentos():
    page = request.args.get('page', 1, type=int)
    tipo = request.args.get('tipo', '')
    status = request.args.get('status', '')
    data_ini = request.args.get('data_ini', '')
    data_fim = request.args.get('data_fim', '')
    categoria_id = request.args.get('categoria_id', '', type=str)

    q = Transaction.query
    if tipo:
        q = q.filter(Transaction.type == tipo)
    if status:
        q = q.filter(Transaction.status == status)
    if data_ini:
        q = q.filter(Transaction.date >= datetime.strptime(data_ini, '%Y-%m-%d').date())
    if data_fim:
        q = q.filter(Transaction.date <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if categoria_id:
        q = q.filter(Transaction.category_id == int(categoria_id))

    lancamentos_paginados = q.order_by(Transaction.date.desc(), Transaction.created_at.desc()).paginate(page=page, per_page=15)
    categorias = Category.query.filter_by(active=True).order_by(Category.name).all()

    return render_template('lancamentos/index.html',
        lancamentos=lancamentos_paginados,
        categorias=categorias,
        filtros={'tipo': tipo, 'status': status, 'data_ini': data_ini, 'data_fim': data_fim, 'categoria_id': categoria_id}
    )

@app.route('/lancamentos/novo', methods=['GET', 'POST'])
@login_required
def lancamento_novo():
    categorias = Category.query.filter_by(active=True).order_by(Category.type, Category.name).all()
    contratos = Contract.query.filter_by(status='ativo').order_by(Contract.number).all()
    if request.method == 'POST':
        try:
            valor_str = request.form.get('value', '0').replace('.', '').replace(',', '.')
            t = Transaction(
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                description=request.form['description'].strip(),
                category_id=int(request.form['category_id']),
                contract_id=int(request.form['contract_id']) if request.form.get('contract_id') else None,
                value=float(valor_str),
                type=request.form['type'],
                status=request.form['status'],
                notes=request.form.get('notes', '').strip(),
                user_id=current_user.id
            )
            db.session.add(t)
            db.session.commit()
            flash('Lançamento registrado com sucesso!', 'success')
            return redirect(url_for('lancamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {str(e)}', 'danger')
    return render_template('lancamentos/form.html', lancamento=None, categorias=categorias, contratos=contratos)

@app.route('/lancamentos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def lancamento_editar(id):
    t = Transaction.query.get_or_404(id)
    categorias = Category.query.filter_by(active=True).order_by(Category.type, Category.name).all()
    contratos = Contract.query.filter_by(status='ativo').order_by(Contract.number).all()
    if request.method == 'POST':
        try:
            valor_str = request.form.get('value', '0').replace('.', '').replace(',', '.')
            t.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            t.description = request.form['description'].strip()
            t.category_id = int(request.form['category_id'])
            t.contract_id = int(request.form['contract_id']) if request.form.get('contract_id') else None
            t.value = float(valor_str)
            t.type = request.form['type']
            t.status = request.form['status']
            t.notes = request.form.get('notes', '').strip()
            db.session.commit()
            flash('Lançamento atualizado com sucesso!', 'success')
            return redirect(url_for('lancamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
    return render_template('lancamentos/form.html', lancamento=t, categorias=categorias, contratos=contratos)

@app.route('/lancamentos/<int:id>/excluir', methods=['POST'])
@login_required
def lancamento_excluir(id):
    t = Transaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Lançamento excluído.', 'success')
    return redirect(url_for('lancamentos'))

# ─── CONTRATOS ───────────────────────────────────────────────────────────────

@app.route('/contratos')
@login_required
def contratos():
    status = request.args.get('status', '')
    q = Contract.query
    if status:
        q = q.filter(Contract.status == status)
    contratos = q.order_by(Contract.created_at.desc()).all()
    return render_template('contratos/index.html', contratos=contratos, filtro_status=status)

@app.route('/contratos/novo', methods=['GET', 'POST'])
@login_required
def contrato_novo():
    if request.method == 'POST':
        try:
            valor_str = request.form.get('value', '0').replace('.', '').replace(',', '.')
            c = Contract(
                number=request.form['number'].strip(),
                client=request.form['client'].strip(),
                description=request.form['description'].strip(),
                value=float(valor_str),
                start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
                end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form.get('end_date') else None,
                status=request.form.get('status', 'ativo')
            )
            db.session.add(c)
            db.session.commit()
            flash('Contrato cadastrado com sucesso!', 'success')
            return redirect(url_for('contratos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {str(e)}', 'danger')
    return render_template('contratos/form.html', contrato=None)

@app.route('/contratos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def contrato_editar(id):
    c = Contract.query.get_or_404(id)
    if request.method == 'POST':
        try:
            valor_str = request.form.get('value', '0').replace('.', '').replace(',', '.')
            c.number = request.form['number'].strip()
            c.client = request.form['client'].strip()
            c.description = request.form['description'].strip()
            c.value = float(valor_str)
            c.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
            c.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form.get('end_date') else None
            c.status = request.form.get('status', 'ativo')
            db.session.commit()
            flash('Contrato atualizado com sucesso!', 'success')
            return redirect(url_for('contratos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
    return render_template('contratos/form.html', contrato=c)

@app.route('/contratos/<int:id>/excluir', methods=['POST'])
@login_required
def contrato_excluir(id):
    c = Contract.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('Contrato excluído.', 'success')
    return redirect(url_for('contratos'))

# ─── PROJEÇÕES ────────────────────────────────────────────────────────────────

@app.route('/projecoes')
@login_required
def projecoes():
    hoje = date.today()
    data_ini = request.args.get('data_ini', hoje.strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', (hoje + timedelta(days=90)).strftime('%Y-%m-%d'))
    tipo = request.args.get('tipo', '')

    q = Projection.query
    if data_ini:
        q = q.filter(Projection.date >= datetime.strptime(data_ini, '%Y-%m-%d').date())
    if data_fim:
        q = q.filter(Projection.date <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if tipo:
        q = q.filter(Projection.type == tipo)

    projecoes = q.order_by(Projection.date.asc()).all()

    # Acumular saldo projetado
    saldo_atual = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'entrada', Transaction.status == 'realizado'
    ).scalar() or 0
    saldo_atual -= db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'saida', Transaction.status == 'realizado'
    ).scalar() or 0

    # Dados do gráfico de projeção (agrupado por semana)
    proj_labels = []
    proj_saldos = []
    saldo_acum = float(saldo_atual)
    if projecoes:
        from itertools import groupby
        for p in projecoes:
            if p.type == 'entrada':
                saldo_acum += float(p.value)
            else:
                saldo_acum -= float(p.value)
            proj_labels.append(p.date.strftime('%d/%m'))
            proj_saldos.append(round(saldo_acum, 2))

    categorias = Category.query.filter_by(active=True).order_by(Category.name).all()
    contratos = Contract.query.filter_by(status='ativo').all()

    return render_template('projecoes/index.html',
        projecoes=projecoes, saldo_atual=saldo_atual,
        proj_labels=json.dumps(proj_labels), proj_saldos=json.dumps(proj_saldos),
        categorias=categorias, contratos=contratos,
        filtros={'data_ini': data_ini, 'data_fim': data_fim, 'tipo': tipo}
    )

@app.route('/projecoes/novo', methods=['POST'])
@login_required
def projecao_nova():
    try:
        valor_str = request.form.get('value', '0').replace('.', '').replace(',', '.')
        p = Projection(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            description=request.form['description'].strip(),
            category_id=int(request.form['category_id']),
            contract_id=int(request.form['contract_id']) if request.form.get('contract_id') else None,
            value=float(valor_str),
            type=request.form['type'],
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(p)
        db.session.commit()
        flash('Projeção adicionada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar: {str(e)}', 'danger')
    return redirect(url_for('projecoes'))

@app.route('/projecoes/<int:id>/excluir', methods=['POST'])
@login_required
def projecao_excluir(id):
    p = Projection.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash('Projeção excluída.', 'success')
    return redirect(url_for('projecoes'))

@app.route('/projecoes/<int:id>/realizar', methods=['POST'])
@login_required
def projecao_realizar(id):
    p = Projection.query.get_or_404(id)
    t = Transaction(
        date=p.date,
        description=p.description,
        category_id=p.category_id,
        contract_id=p.contract_id,
        value=p.value,
        type=p.type,
        status='realizado',
        notes=f'Realizado a partir da projeção. {p.notes}',
        user_id=current_user.id
    )
    db.session.add(t)
    db.session.delete(p)
    db.session.commit()
    flash('Projeção lançada como realizada!', 'success')
    return redirect(url_for('projecoes'))

# ─── RELATÓRIOS ───────────────────────────────────────────────────────────────

@app.route('/relatorios')
@login_required
def relatorios():
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)

    inicio = date(ano, mes, 1)
    fim = (inicio + relativedelta(months=1)) - timedelta(days=1)

    # Totais
    entradas = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'entrada',
        Transaction.date >= inicio,
        Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).scalar() or 0

    saidas = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'saida',
        Transaction.date >= inicio,
        Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).scalar() or 0

    saldo = entradas - saidas

    # Por categoria - entradas
    cat_entradas = db.session.query(
        Category.name, func.sum(Transaction.value).label('total')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.type == 'entrada',
        Transaction.date >= inicio,
        Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).group_by(Category.id).order_by(func.sum(Transaction.value).desc()).all()

    cat_saidas = db.session.query(
        Category.name, func.sum(Transaction.value).label('total')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.type == 'saida',
        Transaction.date >= inicio,
        Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).group_by(Category.id).order_by(func.sum(Transaction.value).desc()).all()

    # Todos os lançamentos do período
    lancamentos = Transaction.query.filter(
        Transaction.date >= inicio,
        Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).order_by(Transaction.date.asc(), Transaction.type.asc()).all()

    # Dados para gráfico diário
    dias_labels = []
    dias_entradas_vals = []
    dias_saidas_vals = []
    d = inicio
    while d <= fim:
        e = db.session.query(func.sum(Transaction.value)).filter(
            Transaction.type == 'entrada',
            Transaction.date == d,
            Transaction.status == 'realizado'
        ).scalar() or 0
        s = db.session.query(func.sum(Transaction.value)).filter(
            Transaction.type == 'saida',
            Transaction.date == d,
            Transaction.status == 'realizado'
        ).scalar() or 0
        dias_labels.append(d.strftime('%d'))
        dias_entradas_vals.append(float(e))
        dias_saidas_vals.append(float(s))
        d += timedelta(days=1)

    meses_disponiveis = []
    for y in range(hoje.year - 2, hoje.year + 1):
        for m in range(1, 13):
            meses_disponiveis.append({'ano': y, 'mes': m,
                'label': date(y, m, 1).strftime('%B/%Y').capitalize()})

    return render_template('relatorios/index.html',
        entradas=entradas, saidas=saidas, saldo=saldo,
        cat_entradas=cat_entradas, cat_saidas=cat_saidas,
        lancamentos=lancamentos, inicio=inicio, fim=fim,
        mes=mes, ano=ano,
        dias_labels=json.dumps(dias_labels),
        dias_entradas_vals=json.dumps(dias_entradas_vals),
        dias_saidas_vals=json.dumps(dias_saidas_vals),
        meses_disponiveis=meses_disponiveis
    )

@app.route('/relatorios/pdf')
@login_required
def relatorio_pdf():
    mes = request.args.get('mes', date.today().month, type=int)
    ano = request.args.get('ano', date.today().year, type=int)
    inicio = date(ano, mes, 1)
    fim = (inicio + relativedelta(months=1)) - timedelta(days=1)

    entradas_total = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'entrada',
        Transaction.date >= inicio, Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).scalar() or 0

    saidas_total = db.session.query(func.sum(Transaction.value)).filter(
        Transaction.type == 'saida',
        Transaction.date >= inicio, Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).scalar() or 0

    lancamentos = Transaction.query.filter(
        Transaction.date >= inicio, Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).order_by(Transaction.date.asc(), Transaction.type.asc()).all()

    cat_entradas = db.session.query(
        Category.name, func.sum(Transaction.value).label('total')
    ).join(Transaction).filter(
        Transaction.type == 'entrada',
        Transaction.date >= inicio, Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).group_by(Category.id).order_by(func.sum(Transaction.value).desc()).all()

    cat_saidas = db.session.query(
        Category.name, func.sum(Transaction.value).label('total')
    ).join(Transaction).filter(
        Transaction.type == 'saida',
        Transaction.date >= inicio, Transaction.date <= fim,
        Transaction.status == 'realizado'
    ).group_by(Category.id).order_by(func.sum(Transaction.value).desc()).all()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cabeçalho
    pdf.set_fill_color(30, 64, 175)
    pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_xy(10, 8)
    pdf.cell(190, 10, 'DEMONSTRACAO DE FLUXO DE CAIXA', align='C')
    pdf.set_font('Helvetica', '', 11)
    pdf.set_xy(10, 20)
    pdf.cell(190, 8, f'Periodo: {inicio.strftime("%d/%m/%Y")} a {fim.strftime("%d/%m/%Y")}', align='C')
    pdf.set_xy(10, 27)
    pdf.cell(190, 6, f'Emitido em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}', align='C')

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(42)

    # Resumo
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_fill_color(243, 244, 246)
    pdf.cell(190, 8, 'RESUMO DO PERIODO', fill=True, ln=True)
    pdf.ln(2)

    def fmt_valor(v):
        return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    pdf.set_font('Helvetica', '', 11)
    pdf.set_fill_color(220, 252, 231)
    pdf.cell(95, 8, 'Total de Entradas', fill=True, border=1)
    pdf.set_fill_color(220, 252, 231)
    pdf.cell(95, 8, fmt_valor(entradas_total), fill=True, border=1, align='R', ln=True)

    pdf.set_fill_color(254, 226, 226)
    pdf.cell(95, 8, 'Total de Saidas', fill=True, border=1)
    pdf.cell(95, 8, fmt_valor(saidas_total), fill=True, border=1, align='R', ln=True)

    saldo = entradas_total - saidas_total
    fill_cor = (220, 252, 231) if saldo >= 0 else (254, 226, 226)
    pdf.set_fill_color(*fill_cor)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(95, 9, 'SALDO DO PERIODO', fill=True, border=1)
    pdf.cell(95, 9, fmt_valor(saldo), fill=True, border=1, align='R', ln=True)
    pdf.ln(4)

    # Por categoria - Entradas
    if cat_entradas:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(243, 244, 246)
        pdf.cell(190, 8, 'ENTRADAS POR CATEGORIA', fill=True, ln=True)
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(209, 250, 229)
        pdf.cell(130, 7, 'Categoria', fill=True, border=1)
        pdf.cell(60, 7, 'Valor', fill=True, border=1, align='R', ln=True)
        pdf.set_font('Helvetica', '', 10)
        for cat, total in cat_entradas:
            pdf.cell(130, 7, str(cat), border=1)
            pdf.cell(60, 7, fmt_valor(total), border=1, align='R', ln=True)
        pdf.ln(4)

    # Por categoria - Saídas
    if cat_saidas:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(243, 244, 246)
        pdf.cell(190, 8, 'SAIDAS POR CATEGORIA', fill=True, ln=True)
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(254, 205, 211)
        pdf.cell(130, 7, 'Categoria', fill=True, border=1)
        pdf.cell(60, 7, 'Valor', fill=True, border=1, align='R', ln=True)
        pdf.set_font('Helvetica', '', 10)
        for cat, total in cat_saidas:
            pdf.cell(130, 7, str(cat), border=1)
            pdf.cell(60, 7, fmt_valor(total), border=1, align='R', ln=True)
        pdf.ln(4)

    # Lançamentos detalhados
    if lancamentos:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(243, 244, 246)
        pdf.cell(190, 8, 'LANCAMENTOS DETALHADOS', fill=True, ln=True)
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_fill_color(224, 231, 255)
        pdf.cell(22, 7, 'Data', fill=True, border=1)
        pdf.cell(75, 7, 'Descricao', fill=True, border=1)
        pdf.cell(40, 7, 'Categoria', fill=True, border=1)
        pdf.cell(18, 7, 'Tipo', fill=True, border=1, align='C')
        pdf.cell(35, 7, 'Valor', fill=True, border=1, align='R', ln=True)
        pdf.set_font('Helvetica', '', 9)
        for l in lancamentos:
            tipo_txt = 'Entrada' if l.type == 'entrada' else 'Saida'
            desc = l.description[:45] if len(l.description) > 45 else l.description
            cat_nome = l.category.name[:22] if l.category else '-'
            pdf.cell(22, 6, l.date.strftime('%d/%m/%Y'), border=1)
            pdf.cell(75, 6, desc, border=1)
            pdf.cell(40, 6, cat_nome, border=1)
            pdf.cell(18, 6, tipo_txt, border=1, align='C')
            pdf.cell(35, 6, fmt_valor(l.value), border=1, align='R', ln=True)

    pdf_bytes = pdf.output()
    response = make_response(bytes(pdf_bytes))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=DFC_{ano}_{mes:02d}.pdf'
    return response

# ─── CATEGORIAS ───────────────────────────────────────────────────────────────

@app.route('/categorias')
@login_required
def categorias():
    cats = Category.query.order_by(Category.type, Category.name).all()
    return render_template('categorias/index.html', categorias=cats)

@app.route('/categorias/nova', methods=['POST'])
@login_required
def categoria_nova():
    name = request.form.get('name', '').strip()
    tipo = request.form.get('type', 'saida')
    if name:
        c = Category(name=name, type=tipo, active=True)
        db.session.add(c)
        db.session.commit()
        flash('Categoria criada com sucesso!', 'success')
    return redirect(url_for('categorias'))

@app.route('/categorias/<int:id>/toggle', methods=['POST'])
@login_required
def categoria_toggle(id):
    c = Category.query.get_or_404(id)
    c.active = not c.active
    db.session.commit()
    return redirect(url_for('categorias'))

@app.route('/categorias/<int:id>/excluir', methods=['POST'])
@login_required
def categoria_excluir(id):
    c = Category.query.get_or_404(id)
    if c.transactions:
        flash('Não é possível excluir categoria com lançamentos vinculados.', 'warning')
    else:
        db.session.delete(c)
        db.session.commit()
        flash('Categoria excluída.', 'success')
    return redirect(url_for('categorias'))

# ─── API ─────────────────────────────────────────────────────────────────────

@app.route('/api/categorias/<tipo>')
@login_required
def api_categorias(tipo):
    cats = Category.query.filter_by(type=tipo, active=True).order_by(Category.name).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in cats])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
