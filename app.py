import os
import uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort
from supabase import create_client, Client

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL et SUPABASE_KEY doivent être configurées.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ALLOWED_IMAGES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp"
}


def admin_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("connexion"))
        return route(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    auteur = session.get("auteur")
    mes_signalements = []

    if auteur:
        try:
            result = (
                supabase
                .table("problemes")
                .select("*")
                .eq("auteur", auteur)
                .order("date_creation", desc=True)
                .execute()
            )

            mes_signalements = result.data or []

        except Exception as e:
            print("Erreur récupération signalements :", e)

    return render_template(
        "index.html",
        mes_signalements=mes_signalements,
        auteur=auteur
    )


@app.route("/signaler", methods=["POST"])
def signaler():
    auteur = request.form.get("auteur", "").strip()
    salle = request.form.get("salle", "").strip()
    categorie = request.form.get("categorie", "").strip()
    description = request.form.get("description", "").strip()
    urgence = request.form.get("urgence", "normale").strip()

    if not auteur or not salle or not categorie or not description:
        return "Informations manquantes.", 400

    session["auteur"] = auteur

    photo_url = None

    photo = request.files.get("photo")

    if photo and photo.filename:
        mime = photo.mimetype

        if mime not in ALLOWED_IMAGES:
            return "Format d'image non autorisé. Utilisez JPG, PNG ou WEBP.", 400

        extension = ALLOWED_IMAGES[mime]
        nom_fichier = f"{uuid.uuid4().hex}{extension}"

        photo_bytes = photo.read()

        if len(photo_bytes) > 8 * 1024 * 1024:
            return "La photo est trop volumineuse. Maximum : 8 Mo.", 400

        try:
            supabase.storage.from_("signalements").upload(
                nom_fichier,
                photo_bytes,
                {
                    "content-type": mime,
                    "upsert": "false"
                }
            )

            photo_url = supabase.storage.from_("signalements").get_public_url(
                nom_fichier
            )

        except Exception as e:
            print("Erreur upload photo :", e)
            return "Impossible d'envoyer la photo.", 500

    data = {
        "auteur": auteur,
        "salle": salle,
        "categorie": categorie,
        "description": description,
        "urgence": urgence,
        "statut": "nouveau",
        "photo_url": photo_url
    }

    try:
        result = supabase.table("problemes").insert(data).execute()
    except Exception as e:
        print("Erreur création signalement :", e)
        return "Impossible de créer le signalement.", 500

    if not result.data:
        return "Impossible de créer le signalement.", 500

    probleme = result.data[0]

    return redirect(url_for("index"))


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    erreur = None

    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("dashboard"))

        erreur = "Mot de passe incorrect."

    return render_template("connexion.html", erreur=erreur)


@app.route("/deconnexion")
def deconnexion():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/dashboard")
@admin_required
def dashboard():
    result = (
        supabase
        .table("problemes")
        .select("*")
        .order("date_creation", desc=True)
        .execute()
    )

    problemes = result.data or []

    urgents = sum(
        1 for p in problemes
        if p.get("urgence") == "urgente"
        and p.get("statut") != "resolu"
    )

    en_cours = sum(
        1 for p in problemes
        if p.get("statut") == "en_cours"
    )

    resolus = sum(
        1 for p in problemes
        if p.get("statut") == "resolu"
    )

    return render_template(
        "dashboard.html",
        problemes=problemes,
        urgents=urgents,
        en_cours=en_cours,
        resolus=resolus
    )


@app.route("/probleme/<int:probleme_id>")
@admin_required
def probleme(probleme_id):
    result = (
        supabase
        .table("problemes")
        .select("*")
        .eq("id", probleme_id)
        .single()
        .execute()
    )

    if not result.data:
        abort(404)

    return render_template(
        "probleme.html",
        probleme=result.data
    )


@app.route("/probleme/<int:probleme_id>/statut", methods=["POST"])
@admin_required
def modifier_statut(probleme_id):
    statut = request.form.get("statut", "nouveau")
    responsable = request.form.get("responsable", "").strip()

    statuts_autorises = {
        "nouveau",
        "en_cours",
        "resolu"
    }

    if statut not in statuts_autorises:
        return "Statut invalide.", 400

    supabase.table("problemes").update({
        "statut": statut,
        "responsable": responsable,
        "date_modification": "now()"
    }).eq("id", probleme_id).execute()

    return redirect(url_for("probleme", probleme_id=probleme_id))


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)