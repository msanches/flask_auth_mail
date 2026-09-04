# Como rodar este exemplo

### 1- Copiar o módulo para o seu projeto
Copie a pasta `flask_auth_mail/` para a raiz do projeto Flask:
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

### 2- Instale as dependências necessárias
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

### 3- Faça as configurações de Ambiente (`.env`)

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

Para mais informações, leia o README.md da pasta flask_auth_mail/