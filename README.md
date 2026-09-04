# Guia de Integração: Como Utilizar o `flask_auth_mail` em Qualquer Aplicação Flask

Este tutorial ensina como reutilizar o módulo **`flask_auth_mail`** em qualquer projeto Flask existente ou novo para implementar:
- **Login sem senha por código OTP de 6 dígitos** (Passwordless / Magic Code via e-mail);
- **Suporte ao "Lembrar de mim"** (`remember=True`) integrado nativamente ao **Flask-Login**;
- **Proteção contra ataques de força bruta**: Limite de 3 tentativas com **bloqueio automático de 1 hora**;
- **Recuperação de senha por link seguro** com tokens temporários assinados (`itsdangerous`);
- **Disparo de e-mails transacionais modernos** desacoplados (nativo com **Resend API**).

---

## 1. Estrutura e Pré-requisitos

### A. Copiar o módulo para o seu projeto
Copie a pasta `flask_auth_mail/` para a raiz do seu novo projeto Flask:
```text
seu_projeto/
├── flask_auth_mail/        <-- Copie esta pasta inteira para sua aplicação
│   ├── templates/emails/
│   │   ├── login_code.html
│   │   └── reset_password.html
│   ├── __init__.py
│   ├── config.py
│   ├── email_service.py
│   ├── models.py
│   ├── otp.py
│   └── tokens.py
├── .env                    <-- Suas chaves de ambiente
├── requirements.txt
├── templates               <-- Templates da aplicação(HTML)
└── app.py                  <-- Aplicação Flask
```

### B. Dependências necessárias
Adicione ao seu `requirements.txt`:
```text
Flask>=3.0.0
Flask-SQLAlchemy>=3.1.1
Flask-Login>=0.6.3
itsdangerous>=2.2.0
requests>=2.32.5
python-dotenv>=1.0.1
```
E instale no seu ambiente virtual:
```bash
pip install -r requirements.txt
```

---

## 2. Configurações de Ambiente (`.env`)

Crie um arquivo `.env` na raiz da sua aplicação com as seguintes chaves:

```env
# Chave mestra do Flask (criptografia de sessão e tokens)
SECRET_KEY=sua-chave-secreta-forte-aqui

# Conexão do Banco de Dados (SQLite, PostgreSQL, MySQL, etc.)
SQLALCHEMY_DATABASE_URI=sqlite:///sua_base.db

# Credenciais do Resend
RESEND_API_KEY=re_sua_chave_do_resend
EMAIL_FROM=contato@seudominio.com

# Parâmetros de Segurança do OTP (Opcionais - valores padrão abaixo)
OTP_MAX_ATTEMPTS=3           # Bloqueia após 3 erros consecutivos
OTP_LOCKOUT_DURATION=3600    # Duração do bloqueio: 3600 segundos (1 hora)
OTP_EXPIRATION=300           # Validade do código: 300 segundos (5 minutos)
OTP_RESEND_INTERVAL=60       # Intervalo mínimo entre envios: 60 segundos
```

> **Dica do Resend**: 
> - Para desenvolvimento sem domínio próprio, utilize `EMAIL_FROM=onboarding@resend.dev` (entrega apenas no e-mail cadastrado na sua conta Resend).
> - Para produção, cadastre e valide o seu domínio em [resend.com/domains](https://resend.com/domains) para poder enviar a partir de `contato@seudominio.com` para qualquer usuário.

---

## 3. Passo a Passo de Inicialização

O `flask_auth_mail` funciona como qualquer extensão oficial do Flask (como SQLAlchemy ou Flask-Login).

### No seu `app.py`:
```python
import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from dotenv import load_dotenv

# Importe a extensão e as funções públicas
from flask_auth_mail import (
    AuthMail,
    enviar_codigo_login,
    validar_codigo_login,
    gerar_token,
    validar_token,
    enviar_email
)

load_dotenv(override=True)

app = Flask(__name__)
app.config.from_prefixed_env()  # Ou carregue do os.getenv()
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)  # Sessão persistente por 30 dias

# 1. Inicialize o SQLAlchemy e o Flask-Login
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# 2. Inicialize o AuthMail passando o app e a instância do db
auth_mail = AuthMail(app, db)
```

---

## 4. Conectando com o Modelo de Usuário

O módulo **não impõe nenhum modelo de usuário fechado**. Ele apenas precisa saber como buscar seu usuário pelo e-mail através do decorador `@auth_mail.find_user_by_email_loader`:

```python
# Seu modelo de Usuário existente
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nome = db.Column(db.String(100))

# Função de carregamento exigida pelo Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Callback que ensina o AuthMail a encontrar o usuário
@auth_mail.find_user_by_email_loader
def get_user_by_email(email):
    if not email:
        return None
    return User.query.filter_by(email=email.strip().lower()).first()
```

---

## 5. Implementando o Fluxo de Login por Código (OTP)

### Passo 1: Solicitar o Código de Login (`/login`)
O usuário informa o e-mail. O módulo gera um código de 6 dígitos, salva apenas o **hash criptográfico** no banco e envia o template HTML pelo Resend.

```python
from flask import render_template, request, redirect, url_for, flash
from flask_auth_mail import enviar_codigo_login, EmailSendError

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        try:
            # Dispara o e-mail com o código de 6 dígitos
            enviar_codigo_login(email)
            flash("Código de acesso enviado para seu e-mail!", "success")
            return redirect(url_for("verificar", email=email))

        except ValueError as ve:
            # Acionado se estiver bloqueado por tentativas erradas ou no intervalo de reenvio
            flash(str(ve), "warning")
        except EmailSendError as ese:
            flash("Falha ao entregar o e-mail. Tente novamente.", "danger")

    return render_template("login.html")
```

> **Segurança contra Enumeração**: Se o e-mail informado **não existir** no banco, a função `enviar_codigo_login` simula o sucesso sem disparar erros para não revelar a atacantes se a conta existe ou não.

---

### Passo 2: Validar o Código e Autenticar (`/verificar`)
O usuário digita o código e escolhe se deseja permanecer conectado:

```python
from flask_auth_mail import validar_codigo_login
from flask_login import current_user

@app.route("/verificar", methods=["GET", "POST"])
def verificar():
    email = request.args.get("email") or request.form.get("email")

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        lembrar = bool(request.form.get("lembrar"))  # True ou False

        # Valida o código, conta as tentativas e autentica com Flask-Login
        if validar_codigo_login(email, codigo, remember=lembrar):
            flash(f"Bem-vindo(a), {current_user.email}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Código incorreto, expirado ou conta temporariamente bloqueada.", "danger")

    return render_template("verificar.html", email=email)
```

---

### Passo 3: Rotas Protegidas e Logout

```python
from flask_login import login_required, logout_user, current_user

@app.route("/dashboard")
@login_required
def dashboard():
    return f"Olá, {current_user.email}! Você está autenticado."

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for("login"))
```

---

## 6. Fluxo Adicional: Recuperação de Senha por Link

Se a sua aplicação também tiver senha tradicional e você quiser implementar o "Esqueci minha senha":

### 1. Gerar e enviar o link:
```python
from flask_auth_mail import gerar_token, enviar_email
from flask import render_template

def enviar_recuperacao_senha(user):
    # Gera um token assinado temporário com validade de 15 minutos (900 segundos)
    token = gerar_token({"user_id": user.id}, salt="redefinir-senha")
    
    link_redefinicao = url_for("redefinir_senha", token=token, _external=True)
    
    html = render_template(
        "emails/reset_password.html",
        app_name="Minha Aplicação",
        reset_url=link_redefinicao,
        expires_in_minutes=15
    )
    
    enviar_email(user.email, "Redefinição de Senha", html)
```

### 2. Validar o token e redefinir:
```python
from flask_auth_mail import validar_token

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    # Valida a assinatura e o tempo de expiração
    payload = validar_token(token, salt="redefinir-senha", max_age=900)
    if not payload:
        flash("Link de redefinição inválido ou expirado.", "danger")
        return redirect(url_for("login"))

    user_id = payload.get("user_id")
    user = User.query.get(user_id)

    if request.method == "POST":
        nova_senha = request.form.get("senha")
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso! Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("redefinir_senha.html")
```

---

## 7. Como Customizar os Templates de E-mail

Os e-mails transacionais enviados pelo módulo estão em:
```text
flask_auth_mail/templates/emails/
├── login_code.html       # Template do código de 6 dígitos
└── reset_password.html   # Template do link de recuperação
```
Eles utilizam HTML inline e CSS responsivo moderno, compatível com Gmail, Outlook e Apple Mail. Você pode abrir esses arquivos e alterar cores, logo ou textos conforme a identidade visual do seu produto.

---

## 8. Criando as Tabelas no Banco de Dados

Sempre que inicializar o banco pela primeira vez no seu projeto, execute o `create_all()` dentro do contexto da aplicação. O `AuthMail` registrará automaticamente a tabela `flask_auth_mail_otp` no seu banco:

```python
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Cria suas tabelas e a tabela de OTP com suporte a lockout
    app.run(debug=True)
```

---

## 9. Resumo da API Pública

| Função / Classe | Onde Usar | Descrição |
| :--- | :--- | :--- |
| `AuthMail(app, db)` | Inicialização | Registra a extensão no Flask e vincula as tabelas ao SQLAlchemy. |
| `@auth_mail.find_user_by_email_loader` | Configuração | Ensina a extensão como consultar seu usuário pelo e-mail. |
| `enviar_codigo_login(email)` | Rota de Login | Gera o código OTP, salva o hash e dispara o e-mail via Resend. |
| `validar_codigo_login(email, code, remember=False)` | Rota de Verificação | Valida o código, controla tentativas/bloqueio e efetua o login no Flask-Login. |
| `gerar_token(payload, salt=...)` | Recuperação de Senha | Cria um token assinado e temporizado (`itsdangerous`). |
| `validar_token(token, salt=..., max_age=...)` | Recuperação de Senha | Decodifica e valida expiração do token. |
| `enviar_email(destinatario, assunto, html)` | E-mails gerais | Dispara qualquer e-mail transacional via Resend. |
