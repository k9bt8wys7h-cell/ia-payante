
import os
import sqlite3
import secrets
from functools import wraps
from flask import Flask, request, redirect, session, url_for, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
DB = "ia_payante.db"

def database():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with database() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            credits INTEGER DEFAULT 0
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prompt TEXT,
            result TEXT
        )""")

init_db()

PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IA Payante</title>
<style>
body{margin:0;background:#101426;color:white;font-family:Arial;text-align:center}
main{max-width:600px;margin:50px auto;padding:20px}
h1{color:#8b7cff;font-size:38px}
.card{background:#1d2540;padding:25px;border-radius:18px;margin:20px 0}
input,textarea{box-sizing:border-box;width:100%;padding:15px;margin:10px 0;border:0;border-radius:10px;font-size:16px}
button{background:#7665ff;color:white;border:0;padding:15px 25px;border-radius:10px;font-size:17px;cursor:pointer}
a{color:#a99fff}
.small{color:#aeb5ca}
</style>
</head>
<body><main>
<h1>IA Payante</h1>
<p class="small">Ton assistant intelligent</p>
{% if message %}<p>{{message}}</p>{% endif %}
{% if user %}
<div class="card">
<h2>Bienvenue !</h2>
<p>Crédits disponibles : <b>{{user.credits}}</b></p>
<form method="post" action="/generate">
<textarea name="prompt" placeholder="Que veux-tu demander à l'IA ?" required></textarea>
<button>Générer (1 crédit)</button>
</form>
{% if result %}<h3>Résultat</h3><p>{{result}}</p>{% endif %}
<p><a href="/history">Voir mon historique</a></p>
<p><a href="/logout">Déconnexion</a></p>
</div>
{% else %}
<div class="card">
<h2>Connexion</h2>
<form method="post" action="/login">
<input name="email" type="email" placeholder="Adresse e-mail" required>
<input name="password" type="password" placeholder="Mot de passe" required>
<button>Se connecter</button>
</form>
</div>
<div class="card">
<h2>Créer un compte</h2>
<form method="post" action="/register">
<input name="email" type="email" placeholder="Adresse e-mail" required>
<input name="password" type="password" placeholder="Mot de passe (8 caractères minimum)" required>
<button>S'inscrire</button>
</form>
</div>
{% endif %}
</main></body></html>
"""

def page(message="", result=""):
    user = None
    if session.get("user_id"):
        with database() as con:
            user = con.execute(
                "SELECT * FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
    return render_template_string(PAGE, user=user, message=message, result=result)

@app.route("/")
def home():
    return page()

@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if len(password) < 8:
        return page("Mot de passe trop court (8 caractères minimum).")
    try:
        with database() as con:
            con.execute(
                "INSERT INTO users(email,password,credits) VALUES(?,?,0)",
                (email, generate_password_hash(password))
            )
        return page("Compte créé ! Connecte-toi.")
    except sqlite3.IntegrityError:
        return page("Cette adresse e-mail est déjà utilisée.")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    with database() as con:
        user = con.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone()
    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        return redirect("/")
    return page("Identifiants incorrects.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/generate", methods=["POST"])
def generate():
    if not session.get("user_id"):
        return redirect("/")
    prompt = request.form.get("prompt", "").strip()
    if not prompt or len(prompt) > 1000:
        return page("Demande vide ou trop longue.")
    with database() as con:
        user = con.execute(
            "SELECT * FROM users WHERE id=?", (session["user_id"],)
        ).fetchone()
        if not user or user["credits"] < 1:
            return page("Tu n'as pas assez de crédits.")
        con.execute(
            "UPDATE users SET credits=credits-1 WHERE id=? AND credits>0",
            (session["user_id"],)
        )
        result = (
            "Voici une première réponse de démonstration à ta demande : "
            + prompt
            + ". Cette version utilise un moteur simplifié, pas encore une vraie IA."
        )
        con.execute(
            "INSERT INTO history(user_id,prompt,result) VALUES(?,?,?)",
            (session["user_id"], prompt, result)
        )
    return page(result=result)

@app.route("/history")
def history():
    if not session.get("user_id"):
        return redirect("/")
    with database() as con:
        rows = con.execute(
            "SELECT prompt,result FROM history WHERE user_id=? ORDER BY id DESC",
            (session["user_id"],)
        ).fetchall()
    content = "<h1>Mon historique</h1>"
    for row in rows:
        content += "<div class='card'><b>Demande :</b> " + \
            row["prompt"] + "<p>" + row["result"] + "</p></div>"
    content += "<a href='/'>Retour</a>"
    return render_template_string(
        "<html><body style='background:#101426;color:white;font-family:Arial;padding:20px'>" +
        content + "</body></html>"
    )

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
