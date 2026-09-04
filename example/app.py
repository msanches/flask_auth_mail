import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_required,
    current_user,
    logout_user
)
from dotenv import load_dotenv

from flask_auth_mail import (
    AuthMail,
    enviar_codigo_login,
    validar_codigo_login,
    EmailSendError
)

load_dotenv(override=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-super-secreta")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["RESEND_API_KEY"] = os.getenv("RESEND_API_KEY")
app.config["EMAIL_FROM"] = os.getenv("EMAIL_FROM", "onboarding@resend.dev")

# Configuração de persistência para 'Lembrar de mim' (30 dias)
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
app.config["REMEMBER_COOKIE_HTTPONLY"] = True

# Segurança e Travamento de OTP
app.config["OTP_MAX_ATTEMPTS"] = int(os.getenv("OTP_MAX_ATTEMPTS", 3))
app.config["OTP_LOCKOUT_DURATION"] = int(os.getenv("OTP_LOCKOUT_DURATION", 3600))

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, autentique-se para acessar esta página."
login_manager.login_message_category = "warning"

auth_mail = AuthMail(app, db)

# 1. Modelo de Usuário
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 2. Callback para localização do usuário por e-mail
@auth_mail.find_user_by_email_loader
def get_user_by_email(email):
    if not email:
        return None
    return User.query.filter_by(email=email.strip().lower()).first()

# ----------------- Rotas Web (Interface Visual) -----------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Por favor, digite um e-mail válido.", "danger")
            return render_template("login.html", email=email)

        try:
            enviar_codigo_login(email)
            flash("Código de verificação enviado! Verifique sua caixa de entrada.", "success")
            return redirect(url_for("verificar", email=email))
        except ValueError as ve:
            flash(str(ve), "warning")
            return render_template("login.html", email=email)
        except EmailSendError as ese:
            flash(f"Erro ao disparar e-mail: {ese}", "danger")
            return render_template("login.html", email=email)
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {e}", "danger")
            return render_template("login.html", email=email)

    email_arg = request.args.get("email", "")
    return render_template("login.html", email=email_arg)

@app.route("/verificar", methods=["GET", "POST"])
def verificar():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        codigo = request.form.get("codigo", "").strip()
        lembrar = bool(request.form.get("lembrar"))

        if not email or not codigo:
            flash("Informe o e-mail e o código de 6 dígitos.", "danger")
            return render_template("verificar.html", email=email)

        try:
            sucesso = validar_codigo_login(email, codigo, remember=lembrar)
            if sucesso:
                flash(f"Bem-vindo, {current_user.email}! Login realizado com sucesso.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Código incorreto, expirado ou limite de 3 tentativas excedido.", "danger")
                return render_template("verificar.html", email=email)
        except Exception as e:
            flash(f"Falha na validação do código: {e}", "danger")
            return render_template("verificar.html", email=email)

    email_arg = request.args.get("email", "")
    if not email_arg:
        return redirect(url_for("login"))
    return render_template("verificar.html", email=email_arg)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta com sucesso.", "success")
    return redirect(url_for("login"))

@app.route("/cadastrar-teste", methods=["GET", "POST"])
def cadastrar_teste():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Informe um endereço de e-mail.", "danger")
            return render_template("cadastrar_teste.html")

        existente = User.query.filter_by(email=email).first()
        if existente:
            flash(f"O usuário '{email}' já está cadastrado no banco local.", "warning")
        else:
            novo_usuario = User(email=email)
            db.session.add(novo_usuario)
            db.session.commit()
            flash(f"Usuário '{email}' cadastrado com sucesso! Agora você já pode solicitar o código de login.", "success")

        return redirect(url_for("login", email=email))

    return render_template("cadastrar_teste.html")

# ----------------- Rotas de API (JSON) -----------------

@app.route("/auth/solicitar-codigo", methods=["POST"])
def api_pedir_codigo():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"erro": "Parâmetro 'email' é obrigatório."}), 400

    try:
        enviar_codigo_login(email)
        return jsonify({"mensagem": "Se o e-mail existir na base, o código foi gerado e enviado."})
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 429
    except EmailSendError as ese:
        return jsonify({"erro": str(ese)}), 502

@app.route("/auth/verificar-codigo", methods=["POST"])
def api_verificar_codigo():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    codigo = data.get("codigo", "").strip()
    lembrar = bool(data.get("lembrar", False))

    if not email or not codigo:
        return jsonify({"erro": "Parâmetros 'email' e 'codigo' são obrigatórios."}), 400

    if validar_codigo_login(email, codigo, remember=lembrar):
        return jsonify({
            "mensagem": f"Usuário {current_user.email} autenticado com sucesso!",
            "user_id": current_user.id
        })
    return jsonify({"erro": "Código inválido, expirado ou limite de tentativas atingido."}), 401

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)