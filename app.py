import os
from datetime import date, datetime, timedelta
from functools import wraps

import psycopg2
import psycopg2.extras

from flask import Flask, render_template_string, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "cle-secrete-locale-a-changer"
)


DATABASE_URL = os.environ.get("DATABASE_URL")

CODE_INSCRIPTION = "INFO-2026-93X7"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


HORAIRES = [
    "08:00 - 09:00",
    "09:00 - 10:00",
    "10:00 - 11:00",
    "11:00 - 12:00",
    "13:00 - 14:00",
    "14:00 - 15:00",
    "15:00 - 16:00",
    "16:00 - 17:00"
]


JOURS = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi"
]


HTML_LOGIN = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Collège Edmond Rostand - Salle informatique</title>

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    font-family: Arial, sans-serif;
    background: #eef2f7;
    color: #172033;
}

.box {
    width: 430px;
    max-width: calc(100% - 30px);
    background: white;
    padding: 35px;
    border-radius: 20px;
    box-shadow: 0 10px 35px rgba(0,0,0,.12);
}

.logo {
    width: 70px;
    height: 70px;
    margin: 0 auto 20px;
    border-radius: 18px;
    background: #2563eb;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
}

h1 {
    text-align: center;
    margin: 0;
}

.subtitle {
    text-align: center;
    color: #64748b;
    margin: 8px 0 25px;
}

label {
    display: block;
    font-weight: bold;
    margin-bottom: 7px;
}

input {
    width: 100%;
    padding: 13px;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    font-size: 15px;
    margin-bottom: 17px;
}

button {
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 10px;
    background: #2563eb;
    color: white;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

button:hover {
    background: #1d4ed8;
}

.secondary,
.back {
    display: block;
    text-align: center;
    margin-top: 15px;
    padding: 13px;
    border-radius: 10px;
    background: #e2e8f0;
    color: #172033;
    text-decoration: none;
    font-weight: bold;
}

.error {
    background: #fee2e2;
    color: #b91c1c;
    padding: 12px;
    border-radius: 9px;
    margin-bottom: 18px;
    font-weight: bold;
}

.success {
    background: #dcfce7;
    color: #15803d;
    padding: 12px;
    border-radius: 9px;
    margin-bottom: 18px;
    font-weight: bold;
}
</style>
</head>

<body>

<div class="box">

    <div class="logo">💻</div>

    <h1>Collège Edmond Rostand</h1>

    <div class="subtitle">Salle informatique • Connexion</div>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

    {% if success %}
        <div class="success">{{ success }}</div>
    {% endif %}

    <form method="POST" action="/login">

        <label>Nom d'utilisateur</label>

        <input
            type="text"
            name="username"
            placeholder="Votre nom d'utilisateur"
            required
            autocomplete="username"
        >

        <label>Mot de passe</label>

        <input
            type="password"
            name="password"
            placeholder="Votre mot de passe"
            required
            autocomplete="current-password"
        >

        <button type="submit">
            🔐 Se connecter
        </button>

    </form>

    <a class="secondary" href="/inscription">
        ➕ Créer un compte
    </a>

</div>

</body>
</html>
"""


HTML_REGISTER = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Collège Edmond Rostand - Créer un compte</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    font-family: Arial, sans-serif;
    background: #eef2f7;
    color: #172033;
}

.box {
    width: 450px;
    max-width: calc(100% - 30px);
    background: white;
    padding: 35px;
    border-radius: 20px;
    box-shadow: 0 10px 35px rgba(0,0,0,.12);
}

.logo {
    width: 70px;
    height: 70px;
    margin: 0 auto 20px;
    border-radius: 18px;
    background: #16a34a;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
}

h1 {
    text-align: center;
    margin: 0;
}

.subtitle {
    text-align: center;
    color: #64748b;
    margin: 8px 0 25px;
}

.info {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    padding: 13px;
    border-radius: 9px;
    margin-bottom: 20px;
    font-size: 14px;
}

label {
    display: block;
    font-weight: bold;
    margin-bottom: 7px;
}

input {
    width: 100%;
    padding: 13px;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    font-size: 15px;
    margin-bottom: 17px;
}

button {
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 10px;
    background: #16a34a;
    color: white;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

button:hover {
    background: #15803d;
}

.back {
    display: block;
    text-align: center;
    margin-top: 15px;
    padding: 13px;
    border-radius: 10px;
    background: #e2e8f0;
    color: #172033;
    text-decoration: none;
    font-weight: bold;
}

.error {
    background: #fee2e2;
    color: #b91c1c;
    padding: 12px;
    border-radius: 9px;
    margin-bottom: 18px;
    font-weight: bold;
}
</style>
</head>

<body>

<div class="box">

    <div class="logo">➕</div>

    <h1>Collège Edmond Rostand</h1>

    <div class="subtitle">
        Salle informatique • Créer un compte
    </div>

    <div class="info">
        🔐 Un code d'inscription fourni par l'établissement
        est nécessaire pour créer un compte.
    </div>

    {% if error %}
        <div class="error">
            {{ error }}
        </div>
    {% endif %}

    <form method="POST" action="/inscription">

        <label>Nom d'utilisateur</label>

        <input
            type="text"
            name="username"
            placeholder="username"
            required
            maxlength="30"
            autocomplete="username"
        >

        <label>Mot de passe</label>

        <input
            type="password"
            name="password"
            placeholder="Choisissez un mot de passe"
            required
            minlength="6"
            autocomplete="new-password"
        >

        <label>Confirmer le mot de passe</label>

        <input
            type="password"
            name="password_confirm"
            placeholder="Retapez le mot de passe"
            required
            minlength="6"
            autocomplete="new-password"
        >

        <label>Code d'inscription</label>

        <input
            type="password"
            name="code"
            placeholder="Code fourni par l'établissement"
            required
            autocomplete="off"
        >

        <button type="submit">
            ✅ Créer mon compte
        </button>

    </form>

    <a class="back" href="/login">
        ← Retour à la connexion
    </a>

</div>

</body>
</html>
"""


HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Collège Edmond Rostand - Salle informatique</title>

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #eef2f7;
    color: #172033;
}

header {
    background: #172033;
    color: white;
    padding: 20px 25px;
}

.header-content {
    max-width: 1250px;
    margin: auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
}

header h1 {
    margin: 0;
    font-size: 27px;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 15px;
}

.user {
    color: #dbeafe;
    font-size: 14px;
}

.logout,
.admin-link {
    color: white;
    padding: 9px 13px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: bold;
}

.logout {
    background: #334155;
}

.admin-link {
    background: #2563eb;
}

.container {
    max-width: 1250px;
    margin: 30px auto;
    padding: 0 20px;
}

.card {
    background: white;
    border-radius: 16px;
    padding: 25px;
    margin-bottom: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,.08);
}

h2 {
    margin-top: 0;
}

.navigation {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 20px;
}

.navigation button {
    width: auto;
}

.navigation .current {
    font-size: 20px;
    font-weight: bold;
    text-align: center;
}

button {
    border: none;
    border-radius: 9px;
    background: #2563eb;
    color: white;
    font-size: 14px;
    font-weight: bold;
    padding: 11px 17px;
    cursor: pointer;
}

.week-wrapper {
    overflow-x: auto;
}

.week-grid {
    display: grid;
    grid-template-columns: 130px repeat(5, minmax(150px, 1fr));
    min-width: 880px;
    border: 1px solid #dbe2ea;
    border-radius: 12px;
    overflow: hidden;
}

.corner,
.day-header {
    background: #172033;
    color: white;
}

.day-header {
    padding: 15px 8px;
    text-align: center;
    font-weight: bold;
}

.day-header small {
    display: block;
    opacity: .7;
    margin-top: 5px;
    font-weight: normal;
}

.time-cell {
    background: #f8fafc;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 90px;
    font-weight: bold;
    border-top: 1px solid #dbe2ea;
}

.slot {
    min-height: 90px;
    padding: 8px;
    border-left: 1px solid #dbe2ea;
    border-top: 1px solid #dbe2ea;
}

.slot.free {
    background: #f0fdf4;
}

.slot.reserved {
    background: #fef2f2;
}

.slot-content {
    height: 100%;
    min-height: 72px;
    border-radius: 9px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.slot.free .slot-content {
    border: 1px solid #86efac;
}

.slot.reserved .slot-content {
    border: 1px solid #fca5a5;
}

.status {
    font-size: 13px;
    font-weight: bold;
}

.free .status {
    color: #15803d;
}

.reserved .status {
    color: #b91c1c;
}

.teacher {
    font-weight: bold;
    font-size: 14px;
    margin-top: 5px;
}

.reason {
    font-size: 12px;
    margin-top: 3px;
    color: #475569;
}

.mine {
    font-size: 11px;
    color: #2563eb;
    font-weight: bold;
    margin-top: 4px;
}

.reserve-btn,
.delete-btn {
    width: 100%;
    padding: 7px;
    margin-top: 7px;
    font-size: 12px;
}

.reserve-btn {
    background: #16a34a;
}

.delete-btn {
    background: #dc2626;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
}

.field {
    display: flex;
    flex-direction: column;
}

label {
    font-weight: bold;
    margin-bottom: 7px;
}

input,
select {
    padding: 12px;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    font-size: 15px;
}

.readonly {
    background: #f1f5f9;
    color: #475569;
}

.form-button {
    width: 100%;
    margin-top: 20px;
    padding: 14px;
    font-size: 16px;
}

.message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 15px;
    font-weight: bold;
}

.error {
    background: #fee2e2;
    color: #b91c1c;
}

.legend {
    display: flex;
    gap: 25px;
    margin-top: 20px;
    font-weight: bold;
}

.legend span {
    display: flex;
    align-items: center;
    gap: 7px;
}

.dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
}

.green {
    background: #22c55e;
}

.red {
    background: #ef4444;
}

.blue {
    background: #2563eb;
}

@media (max-width: 700px) {
    .header-content {
        flex-direction: column;
        text-align: center;
    }

    .header-right {
        flex-wrap: wrap;
        justify-content: center;
    }

    .navigation {
        flex-direction: column;
    }

    .navigation button {
        width: 100%;
    }

    .form-grid {
        grid-template-columns: 1fr;
    }
}
</style>
</head>

<body>

<header>
<div class="header-content">

    <div>
        <h1>💻 Collège Edmond Rostand</h1>
        <div style="font-size:15px; opacity:.8; margin-top:4px;">Salle informatique</div>
    </div>

    <div class="header-right">

        <div class="user">
            👤 {{ username }}
        </div>

        {% if role == "admin" %}
            <a class="admin-link" href="/admin">
                👑 Administration
            </a>
        {% endif %}

        <a class="logout" href="/logout">
            Déconnexion
        </a>

    </div>

</div>
</header>

<div class="container">

<div class="card">

    <h2>📅 Planning de la semaine</h2>

    <div class="navigation">

        <form method="GET" action="/">
            <input type="hidden" name="week" value="{{ previous_week }}">
            <button type="submit">
                ◀ Semaine précédente
            </button>
        </form>

        <div class="current">
            {{ week_label }}
        </div>

        <form method="GET" action="/">
            <input type="hidden" name="week" value="{{ next_week }}">
            <button type="submit">
                Semaine suivante ▶
            </button>
        </form>

    </div>

    <div class="week-wrapper">

        <div class="week-grid">

            <div class="corner"></div>

            {% for day in days %}
                <div class="day-header">
                    {{ day.name }}
                    <small>{{ day.display }}</small>
                </div>
            {% endfor %}

            {% for horaire in horaires %}

                <div class="time-cell">
                    {{ horaire }}
                </div>

                {% for day in days %}

                    {% set key = day.date + "|" + horaire %}
                    {% set reservation = reservations.get(key) %}

                    {% if reservation %}

                        <div class="slot reserved">

                            <div class="slot-content">

                                <div>

                                    <div class="status">
                                        🔴 RÉSERVÉ
                                    </div>

                                    <div class="teacher">
                                        👤 {{ reservation.professeur }}
                                    </div>

                                    <div class="reason">
                                        {{ reservation.motif }}
                                    </div>

                                    {% if reservation.professeur == username %}
                                        <div class="mine">
                                            ★ Votre réservation
                                        </div>
                                    {% endif %}

                                </div>

                                {% if role == "admin" or reservation.professeur == username %}

                                    <form method="POST" action="/annuler"
                                          onsubmit="return confirm('Voulez-vous vraiment annuler cette réservation ?');">

                                        <input type="hidden" name="id" value="{{ reservation.id }}">
                                        <input type="hidden" name="week" value="{{ selected_week }}">

                                        <button class="delete-btn" type="submit">
                                            🗑 Annuler
                                        </button>

                                    </form>

                                {% endif %}

                            </div>

                        </div>

                    {% else %}

                        <div class="slot free">

                            <div class="slot-content">

                                <div class="status">
                                    🟢 LIBRE
                                </div>

                                <button
                                    class="reserve-btn"
                                    type="button"
                                    onclick="ouvrirReservation('{{ day.date }}', '{{ horaire }}')"
                                >
                                    + Réserver
                                </button>

                            </div>

                        </div>

                    {% endif %}

                {% endfor %}

            {% endfor %}

        </div>

    </div>

    <div class="legend">

        <span>
            <span class="dot green"></span>
            Libre
        </span>

        <span>
            <span class="dot red"></span>
            Réservé
        </span>

        <span>
            <span class="dot blue"></span>
            Ma réservation
        </span>

    </div>

</div>

<div class="card" id="reservation">

    <h2>📝 Nouvelle réservation</h2>

    {% if error %}
        <div class="message error">
            {{ error }}
        </div>
    {% endif %}

    <form method="POST" action="/reserver">

        <input type="hidden" name="week" value="{{ selected_week }}">

        <div class="form-grid">

            <div class="field">

                <label>Date</label>

                <input
                    id="date"
                    type="date"
                    name="date"
                    value="{{ selected_week }}"
                    required
                >

            </div>

            <div class="field">

                <label>Créneau</label>

                <select id="horaire" name="horaire" required>

                    {% for horaire in horaires %}
                        <option value="{{ horaire }}">
                            {{ horaire }}
                        </option>
                    {% endfor %}

                </select>

            </div>

            <div class="field">

                <label>Nom d'utilisateur</label>

                <input
                    class="readonly"
                    type="text"
                    value="{{ username }}"
                    readonly
                >

            </div>

            <div class="field">

                <label>Motif</label>

                <input
                    type="text"
                    name="motif"
                    placeholder="Ex : cours d'informatique"
                    maxlength="200"
                    required
                >

            </div>

        </div>

        <button class="form-button" type="submit">
            🟢 Réserver la salle
        </button>

    </form>

</div>

</div>

<script>
function ouvrirReservation(date, horaire) {
    document.getElementById("date").value = date;
    document.getElementById("horaire").value = horaire;

    document.getElementById("reservation").scrollIntoView({
        behavior: "smooth"
    });
}
</script>

</body>
</html>
"""


HTML_ADMIN = """
<!DOCTYPE html>
<html lang="fr">

<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Collège Edmond Rostand - Administration</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #eef2f7;
    color: #172033;
}

header {
    background: #172033;
    color: white;
    padding: 20px 25px;
}

.header-content {
    max-width: 1100px;
    margin: auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}

header h1 {
    margin: 0;
}

.back {
    color: white;
    background: #334155;
    padding: 10px 14px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: bold;
}

.container {
    max-width: 1100px;
    margin: 30px auto;
    padding: 0 20px;
}

.card {
    background: white;
    border-radius: 16px;
    padding: 25px;
    margin-bottom: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,.08);
}

h2 {
    margin-top: 0;
}

.info {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
}

.code {
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 2px;
    margin-top: 8px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    padding: 12px;
    border-bottom: 1px solid #e2e8f0;
    text-align: left;
}

th {
    background: #f8fafc;
}

.delete {
    background: #dc2626;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 7px;
    cursor: pointer;
    font-weight: bold;
}

.table-wrapper {
    overflow-x: auto;
}

@media (max-width: 700px) {
    .header-content {
        flex-direction: column;
    }

    table {
        min-width: 650px;
    }
}

</style>

</head>

<body>

<header>

<div class="header-content">

    <div>
        <h1>👑 Administration</h1>
        <div style="font-size:14px; opacity:.8; margin-top:4px;">
            Collège Edmond Rostand • Salle informatique
        </div>
    </div>

    <a class="back" href="/">
        ← Retour au planning
    </a>

</div>

</header>

<div class="container">

<div class="card">

    <h2>🔐 Code d'inscription</h2>

    <div class="info">

        Donnez ce code uniquement aux personnes autorisées
        à créer un compte.

        <div class="code">
            {{ registration_code }}
        </div>

    </div>

</div>

<div class="card">

    <h2>👥 Comptes</h2>

    <div class="table-wrapper">

        <table>

            <tr>
                <th>Nom d'utilisateur</th>
                <th>Type</th>
            </tr>

            {% for user in users %}

            <tr>

                <td>{{ user.username }}</td>

                <td>
                    {% if user.role == "admin" %}
                        👑 Administrateur
                    {% else %}
                        👨‍🏫 Utilisateur
                    {% endif %}
                </td>

            </tr>

            {% endfor %}

        </table>

    </div>

</div>

<div class="card">

    <h2>📅 Réservations</h2>

    <div class="table-wrapper">

        <table>

            <tr>
                <th>Date</th>
                <th>Horaire</th>
                <th>Utilisateur</th>
                <th>Motif</th>
                <th>Action</th>
            </tr>

            {% for reservation in reservations %}

            <tr>

                <td>{{ reservation.date }}</td>
                <td>{{ reservation.horaire }}</td>
                <td>{{ reservation.professeur }}</td>
                <td>{{ reservation.motif }}</td>

                <td>

                    <form method="POST" action="/annuler"
                          onsubmit="return confirm('Annuler cette réservation ?');">

                        <input type="hidden"
                               name="id"
                               value="{{ reservation.id }}">

                        <input type="hidden"
                               name="week"
                               value="{{ reservation.date }}">

                        <button class="delete" type="submit">
                            🗑 Annuler
                        </button>

                    </form>

                </td>

            </tr>

            {% endfor %}

        </table>

    </div>

</div>

</div>

</body>
</html>
"""


def get_db():

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL n'est pas configurée dans les variables d'environnement."
        )

    database_url = DATABASE_URL

    if "sslmode=" not in database_url:
        if "?" in database_url:
            database_url += "&sslmode=require"
        else:
            database_url += "?sslmode=require"

    return psycopg2.connect(database_url)


def init_db():

    conn = get_db()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username VARCHAR(30) UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'prof'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id BIGSERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    horaire VARCHAR(30) NOT NULL,
                    professeur VARCHAR(30) NOT NULL,
                    motif VARCHAR(200) NOT NULL,
                    UNIQUE(date, horaire)
                )
            """)

            cur.execute("""
                SELECT id
                FROM users
                WHERE username = %s
            """, (ADMIN_USERNAME,))

            admin = cur.fetchone()

            if not admin:

                cur.execute("""
                    INSERT INTO users
                    (username, password, role)
                    VALUES (%s, %s, %s)
                """, (
                    ADMIN_USERNAME,
                    generate_password_hash(ADMIN_PASSWORD),
                    "admin"
                ))

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "username" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "username" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            return redirect(url_for("index"))

        return function(*args, **kwargs)

    return wrapper


def get_monday(value):

    selected = datetime.strptime(
        value,
        "%Y-%m-%d"
    ).date()

    return selected - timedelta(
        days=selected.weekday()
    )


def build_week(monday):

    days = []

    for i, name in enumerate(JOURS):

        current = monday + timedelta(days=i)

        days.append({
            "name": name,
            "date": current.isoformat(),
            "display": current.strftime("%d/%m")
        })

    return days


@app.route("/login", methods=["GET", "POST"])
def login():

    if "username" in session:
        return redirect(url_for("index"))

    error = None
    success = request.args.get("success")

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        try:

            init_db()

            conn = get_db()

            try:

                with conn.cursor(
                    cursor_factory=psycopg2.extras.RealDictCursor
                ) as cur:

                    cur.execute("""
                        SELECT username, password, role
                        FROM users
                        WHERE username = %s
                    """, (username,))

                    user = cur.fetchone()

            finally:

                conn.close()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session.clear()

                session["username"] = user["username"]
                session["role"] = user["role"]

                return redirect(url_for("index"))

            error = "❌ Nom d'utilisateur ou mot de passe incorrect."

        except Exception as e:

            print("Erreur connexion :", repr(e))

            error = "❌ Impossible de contacter la base de données."

    return render_template_string(
        HTML_LOGIN,
        error=error,
        success=success
    )


@app.route("/inscription", methods=["GET", "POST"])
def inscription():

    if "username" in session:
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":

        print("========== INSCRIPTION ==========")
        print("POST /inscription reçu")

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        password_confirm = request.form.get(
            "password_confirm",
            ""
        )

        code = request.form.get(
            "code",
            ""
        ).strip()

        print("Nom utilisateur :", username)
        print("Code reçu :", "OUI" if code else "NON")

        if code != CODE_INSCRIPTION:

            error = "❌ Le code d'inscription est incorrect."

        elif len(username) < 3:

            error = "❌ Le nom d'utilisateur doit contenir au moins 3 caractères."

        elif len(username) > 30:

            error = "❌ Le nom d'utilisateur est trop long."

        elif password == "":

            error = "❌ Le mot de passe est obligatoire."

        elif len(password) < 6:

            error = "❌ Le mot de passe doit contenir au moins 6 caractères."

        elif password != password_confirm:

            error = "❌ Les deux mots de passe ne correspondent pas."

        else:

            conn = None

            try:

                print("Initialisation/vérification de la base...")

                init_db()

                print("Base OK.")

                conn = get_db()

                with conn.cursor() as cur:

                    cur.execute("""
                        SELECT id
                        FROM users
                        WHERE username = %s
                    """, (username,))

                    existing = cur.fetchone()

                    if existing:

                        error = "❌ Ce nom d'utilisateur existe déjà."

                    else:

                        print("Création du compte...")

                        cur.execute("""
                            INSERT INTO users
                            (username, password, role)
                            VALUES (%s, %s, %s)
                        """, (
                            username,
                            generate_password_hash(password),
                            "prof"
                        ))

                        conn.commit()

                        print("Compte créé avec succès.")

                        return redirect(
                            url_for(
                                "login",
                                success="Compte créé avec succès. Vous pouvez maintenant vous connecter."
                            )
                        )

            except Exception as e:

                if conn:
                    conn.rollback()

                print("ERREUR INSCRIPTION :", repr(e))

                error = (
                    "❌ Une erreur est survenue lors de la création du compte. "
                    "Consultez les logs Render."
                )

            finally:

                if conn:
                    conn.close()

    return render_template_string(
        HTML_REGISTER,
        error=error
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():

    requested_week = request.args.get(
        "week",
        date.today().isoformat()
    )

    try:

        monday = get_monday(requested_week)

    except ValueError:

        monday = get_monday(date.today().isoformat())

    selected_week = monday.isoformat()

    days = build_week(monday)

    sunday = monday + timedelta(days=6)

    conn = get_db()

    try:

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute("""
                SELECT id, date, horaire, professeur, motif
                FROM reservations
                WHERE date >= %s
                AND date <= %s
                ORDER BY date, horaire
            """, (
                monday,
                sunday
            ))

            rows = cur.fetchall()

    finally:

        conn.close()

    reservations = {}

    for reservation in rows:

        reservation_date = reservation["date"]

        if hasattr(reservation_date, "isoformat"):
            reservation_date = reservation_date.isoformat()

        key = reservation_date + "|" + reservation["horaire"]

        reservations[key] = {
            "id": reservation["id"],
            "date": reservation_date,
            "horaire": reservation["horaire"],
            "professeur": reservation["professeur"],
            "motif": reservation["motif"]
        }

    previous_week = (
        monday - timedelta(days=7)
    ).isoformat()

    next_week = (
        monday + timedelta(days=7)
    ).isoformat()

    week_label = (
        monday.strftime("%d/%m/%Y")
        + " → "
        + sunday.strftime("%d/%m/%Y")
    )

    return render_template_string(
        HTML,
        days=days,
        horaires=HORAIRES,
        reservations=reservations,
        selected_week=selected_week,
        previous_week=previous_week,
        next_week=next_week,
        week_label=week_label,
        username=session["username"],
        role=session["role"],
        error=None
    )


@app.route("/reserver", methods=["POST"])
@login_required
def reserver():

    selected_week = request.form.get(
        "week",
        date.today().isoformat()
    )

    selected_date = request.form.get(
        "date",
        ""
    )

    horaire = request.form.get(
        "horaire",
        ""
    )

    motif = request.form.get(
        "motif",
        ""
    ).strip()

    if not selected_date or horaire not in HORAIRES or not motif:

        return redirect(
            url_for(
                "index",
                week=selected_week
            )
        )

    try:

        selected_date_obj = datetime.strptime(
            selected_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return redirect(
            url_for(
                "index",
                week=selected_week
            )
        )

    if selected_date_obj.weekday() > 4:

        return redirect(
            url_for(
                "index",
                week=selected_week
            )
        )

    conn = get_db()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT id
                FROM reservations
                WHERE date = %s
                AND horaire = %s
            """, (
                selected_date_obj,
                horaire
            ))

            existing = cur.fetchone()

            if not existing:

                cur.execute("""
                    INSERT INTO reservations
                    (date, horaire, professeur, motif)
                    VALUES (%s, %s, %s, %s)
                """, (
                    selected_date_obj,
                    horaire,
                    session["username"],
                    motif
                ))

                conn.commit()

    except psycopg2.errors.UniqueViolation:

        conn.rollback()

    except Exception as e:

        conn.rollback()

        print(
            "Erreur réservation :",
            repr(e)
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "index",
            week=selected_week
        )
    )


@app.route("/annuler", methods=["POST"])
@login_required
def annuler():

    reservation_id = request.form.get(
        "id",
        ""
    )

    selected_week = request.form.get(
        "week",
        date.today().isoformat()
    )

    try:

        reservation_id = int(reservation_id)

    except ValueError:

        return redirect(
            url_for(
                "index",
                week=selected_week
            )
        )

    conn = get_db()

    try:

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute("""
                SELECT professeur
                FROM reservations
                WHERE id = %s
            """, (
                reservation_id,
            ))

            reservation = cur.fetchone()

            if reservation:

                is_admin = session.get("role") == "admin"

                is_owner = (
                    reservation["professeur"]
                    == session["username"]
                )

                if is_admin or is_owner:

                    cur.execute("""
                        DELETE FROM reservations
                        WHERE id = %s
                    """, (
                        reservation_id,
                    ))

                    conn.commit()

    except Exception as e:

        conn.rollback()

        print(
            "Erreur annulation :",
            repr(e)
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "index",
            week=selected_week
        )
    )


@app.route("/admin")
@admin_required
def admin():

    conn = get_db()

    try:

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute("""
                SELECT username, role
                FROM users
                ORDER BY username
            """)

            users = cur.fetchall()

            cur.execute("""
                SELECT id, date, horaire, professeur, motif
                FROM reservations
                ORDER BY date, horaire
            """)

            reservations = cur.fetchall()

    finally:

        conn.close()

    return render_template_string(
        HTML_ADMIN,
        users=users,
        reservations=reservations,
        registration_code=CODE_INSCRIPTION
    )


@app.route("/health")
def health():

    conn = None

    try:

        conn = get_db()

        with conn.cursor() as cur:

            cur.execute("SELECT 1")
            cur.fetchone()

        return "OK", 200

    except Exception as e:

        print(
            "Erreur health :",
            repr(e)
        )

        return "DATABASE ERROR", 500

    finally:

        if conn:
            conn.close()


try:

    init_db()

    print(
        "Base PostgreSQL initialisée avec succès."
    )

except Exception as e:

    print(
        "ERREUR INITIALISATION BASE DE DONNÉES :",
        repr(e)
    )


if __name__ == "__main__":

    print()
    print("======================================")
    print("   RESERVATION SALLE INFORMATIQUE")
    print("   COLLEGE EDMOND ROSTAND")
    print("======================================")
    print()

    print("http://127.0.0.1:5000")
    print()

    print("Compte administrateur :")
    print("Identifiant :", ADMIN_USERNAME)
    print("Mot de passe :", ADMIN_PASSWORD)
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )