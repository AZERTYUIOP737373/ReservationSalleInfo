import os
from dotenv import load_dotenv

load_dotenv()

import uuid
import json
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    jsonify,
    send_from_directory
)

from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

from pywebpush import webpush, WebPushException


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "dev-secret-change-me"
)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

PROF_SIGNUP_PASSWORD = os.environ.get(
    "PROF_SIGNUP_PASSWORD",
    "change-this-signup-password"
)

ADMIN_PROMOTION_PASSWORD = os.environ.get(
    "ADMIN_PROMOTION_PASSWORD",
    "change-this-admin-password"
)

VAPID_PRIVATE_KEY = os.environ.get(
    "VAPID_PRIVATE_KEY"
)

VAPID_PUBLIC_KEY = os.environ.get(
    "VAPID_PUBLIC_KEY"
)

VAPID_EMAIL = os.environ.get(
    "VAPID_EMAIL",
    "mailto:baptiste.brygal@gmail.com"
)


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL et SUPABASE_KEY doivent être configurées."
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


if not VAPID_PUBLIC_KEY:
    print(
        "[PUSH] ATTENTION : VAPID_PUBLIC_KEY absente."
    )

if not VAPID_PRIVATE_KEY:
    print(
        "[PUSH] ATTENTION : VAPID_PRIVATE_KEY absente."
    )

if not VAPID_EMAIL:
    print(
        "[PUSH] ATTENTION : VAPID_EMAIL absent."
    )


ALLOWED_IMAGES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp"
}


def get_current_user():
    if not session.get("user_id"):
        return None

    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
        "profile_photo_url": session.get("profile_photo_url")
    }


def professor_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        user = get_current_user()

        if not user:
            return redirect(url_for("connexion"))

        if user.get("role") not in ("prof", "professeur"):
            if user.get("role") == "admin":
                return redirect(url_for("dashboard"))

            session.clear()
            return redirect(url_for("connexion"))

        return route(*args, **kwargs)

    return wrapper


def admin_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        user = get_current_user()

        if not user:
            return redirect(url_for("connexion"))

        if user.get("role") != "admin":
            if user.get("role") in ("prof", "professeur"):
                return redirect(url_for("professeur"))

            session.clear()
            return redirect(url_for("connexion"))

        return route(*args, **kwargs)

    return wrapper


def verifier_mot_de_passe(stored_password, password):
    if not stored_password:
        return False

    try:
        if check_password_hash(stored_password, password):
            return True
    except Exception:
        pass

    if stored_password == password:
        return True

    return False


def recuperer_utilisateur(username):
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def convertir_date(date_string):
    if not date_string:
        return None

    try:
        valeur = str(date_string).strip()

        if valeur.endswith("Z"):
            valeur = valeur[:-1] + "+00:00"

        date_convertie = datetime.fromisoformat(valeur)

        if date_convertie.tzinfo is None:
            date_convertie = date_convertie.replace(
                tzinfo=timezone.utc
            )

        return date_convertie

    except Exception:
        return None


def calculer_duree_secondes(probleme):
    if probleme.get("statut") != "resolu":
        return None

    date_creation = convertir_date(
        probleme.get("date_creation")
    )

    date_modification = convertir_date(
        probleme.get("date_modification")
    )

    if not date_creation or not date_modification:
        return None

    try:
        difference = (
            date_modification - date_creation
        ).total_seconds()

        if difference < 0:
            return None

        return difference

    except Exception:
        return None


def calculer_duree_actuelle_secondes(probleme):
    if probleme.get("statut") == "resolu":
        return None

    date_creation = convertir_date(
        probleme.get("date_creation")
    )

    if not date_creation:
        return None

    try:
        maintenant = datetime.now(timezone.utc)

        difference = (
            maintenant - date_creation
        ).total_seconds()

        if difference < 0:
            return 0

        return difference

    except Exception:
        return None


def calculer_duree_affichage_secondes(probleme):
    if probleme.get("statut") == "resolu":
        return calculer_duree_secondes(probleme)

    return calculer_duree_actuelle_secondes(probleme)


def calculer_duree_moyenne(problemes):
    durees = []

    for probleme in problemes:
        duree = calculer_duree_secondes(probleme)

        if duree is not None:
            durees.append(duree)

    if not durees:
        return 0

    return sum(durees) / len(durees)


def formater_duree_secondes(secondes):
    try:
        secondes = int(secondes)
    except Exception:
        secondes = 0

    if secondes < 0:
        secondes = 0

    jours = secondes // 86400
    reste = secondes % 86400

    heures = reste // 3600
    reste = reste % 3600

    minutes = reste // 60
    secondes_finales = reste % 60

    return {
        "jours": jours,
        "heures": heures,
        "minutes": minutes,
        "secondes": secondes_finales
    }


def ajouter_durees_resolution(problemes):
    for probleme in problemes:
        duree_secondes = calculer_duree_affichage_secondes(
            probleme
        )

        if duree_secondes is not None:
            probleme["duree_resolution_secondes"] = int(
                duree_secondes
            )

            probleme["duree_resolution"] = (
                formater_duree_secondes(
                    duree_secondes
                )
            )
        else:
            probleme["duree_resolution_secondes"] = 0

            probleme["duree_resolution"] = {
                "jours": 0,
                "heures": 0,
                "minutes": 0,
                "secondes": 0
            }

    return problemes


def supprimer_abonnement_push(endpoint):
    if not endpoint:
        return

    try:
        (
            supabase
            .table("push_subscriptions")
            .delete()
            .eq(
                "endpoint",
                endpoint
            )
            .execute()
        )

        print(
            "[PUSH] Abonnement supprimé :",
            endpoint[:100]
        )

    except Exception as e:
        print(
            "[PUSH] Erreur suppression abonnement :",
            repr(e)
        )


def envoyer_push_aux_abonnements(
    subscriptions,
    payload
):
    succes = 0
    echecs = 0

    if not VAPID_PRIVATE_KEY:
        print(
            "[PUSH] Envoi impossible : "
            "VAPID_PRIVATE_KEY absente."
        )

        return {
            "success": 0,
            "failed": len(subscriptions)
        }

    if not VAPID_EMAIL:
        print(
            "[PUSH] Envoi impossible : "
            "VAPID_EMAIL absent."
        )

        return {
            "success": 0,
            "failed": len(subscriptions)
        }

    for subscription in subscriptions:
        username = subscription.get(
            "username"
        )

        endpoint = subscription.get(
            "endpoint"
        )

        p256dh = subscription.get(
            "p256dh"
        )

        auth = subscription.get(
            "auth"
        )

        print(
            "[PUSH] ----------------------------------------"
        )

        print(
            "[PUSH] Utilisateur :",
            username
        )

        print(
            "[PUSH] Endpoint :",
            endpoint[:120]
            if endpoint
            else "ABSENT"
        )

        if (
            not endpoint
            or not p256dh
            or not auth
        ):
            print(
                "[PUSH] Abonnement incomplet."
            )

            supprimer_abonnement_push(
                endpoint
            )

            echecs += 1
            continue

        subscription_info = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": p256dh,
                "auth": auth
            }
        }

        try:
            response = webpush(
                subscription_info=subscription_info,
                data=json.dumps(
                    payload,
                    ensure_ascii=False
                ),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": VAPID_EMAIL
                },
                ttl=86400
            )

            succes += 1

            print(
                "[PUSH] ✓ ENVOI ACCEPTE"
            )

            if response is not None:
                print(
                    "[PUSH] HTTP :",
                    getattr(
                        response,
                        "status_code",
                        "?"
                    )
                )

        except WebPushException as e:
            echecs += 1

            response = getattr(
                e,
                "response",
                None
            )

            status_code = None

            if response is not None:
                status_code = getattr(
                    response,
                    "status_code",
                    None
                )

            if status_code is None:
                status_code = getattr(
                    e,
                    "status_code",
                    None
                )

            print(
                "[PUSH] ✗ ECHEC"
            )

            print(
                "[PUSH] HTTP :",
                status_code
            )

            print(
                "[PUSH] Erreur :",
                repr(e)
            )

            if response is not None:
                try:
                    print(
                        "[PUSH] Réponse :",
                        response.text[:1000]
                    )
                except Exception:
                    pass

            if status_code in (
                404,
                410
            ):
                print(
                    "[PUSH] Abonnement expiré/"
                    "introuvable."
                )

                supprimer_abonnement_push(
                    endpoint
                )

        except Exception as e:
            echecs += 1

            print(
                "[PUSH] ✗ ERREUR INATTENDUE :",
                repr(e)
            )

    return {
        "success": succes,
        "failed": echecs
    }


def envoyer_notification_admins(probleme):
    print("")
    print(
        "[PUSH] ========================================"
    )
    print(
        "[PUSH] NOUVEAU SIGNALEMENT"
    )
    print(
        "[PUSH] ID :",
        probleme.get("id")
    )

    if not VAPID_PUBLIC_KEY:
        print(
            "[PUSH] ERREUR : VAPID_PUBLIC_KEY absente."
        )

        return

    if not VAPID_PRIVATE_KEY:
        print(
            "[PUSH] ERREUR : VAPID_PRIVATE_KEY absente."
        )

        return

    if not VAPID_EMAIL:
        print(
            "[PUSH] ERREUR : VAPID_EMAIL absent."
        )

        return

    try:
        admins_result = (
            supabase
            .table("users")
            .select("username")
            .eq("role", "admin")
            .execute()
        )

        admins = admins_result.data or []

        noms_admins = [
            admin.get("username")
            for admin in admins
            if admin.get("username")
        ]

        print(
            "[PUSH] Administrateurs :",
            noms_admins
        )

        if not noms_admins:
            print(
                "[PUSH] Aucun administrateur."
            )

            return

        subscriptions_result = (
            supabase
            .table("push_subscriptions")
            .select("*")
            .in_(
                "username",
                noms_admins
            )
            .execute()
        )

        subscriptions = (
            subscriptions_result.data or []
        )

        print(
            "[PUSH] Abonnements trouvés :",
            len(subscriptions)
        )

        if not subscriptions:
            print(
                "[PUSH] Aucun appareil abonné."
            )

            return

        urgence = (
            probleme.get("urgence")
            or "normale"
        )

        salle = (
            probleme.get("salle")
            or "Salle inconnue"
        )

        categorie = (
            probleme.get("categorie")
            or "Problème"
        )

        description = (
            probleme.get("description")
            or ""
        )

        probleme_id = probleme.get("id")

        if len(description) > 180:
            description = (
                description[:177]
                + "..."
            )

        if urgence == "urgente":
            titre = "🚨 Signalement URGENT"
        else:
            titre = "🚨 Nouveau signalement"

        corps = (
            f"{salle} • {categorie}\n"
            f"{description}"
        )

        url_signalement = (
            f"https://sos-college.onrender.com"
            f"/probleme/{probleme_id}"
        )

        payload = {
            "title": titre,
            "body": corps,
            "url": url_signalement,
            "tag": f"college-sos-{probleme_id}"
        }

        print(
            "[PUSH] URL :",
            url_signalement
        )

        resultat = envoyer_push_aux_abonnements(
            subscriptions,
            payload
        )

        print(
            "[PUSH] ========================================"
        )

        print(
            "[PUSH] RESULTAT :",
            resultat["success"],
            "accepté(s),",
            resultat["failed"],
            "échec(s)"
        )

        print(
            "[PUSH] ========================================"
        )
        print("")

    except Exception as e:
        print(
            "[PUSH] ERREUR GENERALE :",
            repr(e)
        )


@app.route("/")
def index():
    user = get_current_user()

    if user:
        if user.get("role") == "admin":
            return redirect(
                url_for("dashboard")
            )

        if user.get("role") in (
            "prof",
            "professeur"
        ):
            return redirect(
                url_for("professeur")
            )

    return render_template(
        "index.html",
        user=None,
        mes_signalements=[],
        auteur=None
    )


@app.route("/professeur")
@professor_required
def professeur():
    user = get_current_user()

    profil = recuperer_utilisateur(
        user["username"]
    )

    if profil:
        user["profile_photo_url"] = profil.get(
            "profile_photo_url"
        )

        session["profile_photo_url"] = profil.get(
            "profile_photo_url"
        )

    mes_signalements = []

    try:
        result = (
            supabase
            .table("problemes")
            .select("*")
            .eq(
                "auteur",
                user["username"]
            )
            .order(
                "date_creation",
                desc=True
            )
            .execute()
        )

        mes_signalements = result.data or []

    except Exception as e:
        print(
            "Erreur récupération signalements :",
            repr(e)
        )

    return render_template(
        "index.html",
        user=user,
        mes_signalements=mes_signalements,
        auteur=user["username"]
    )


@app.route(
    "/profil/photo",
    methods=["POST"]
)
@professor_required
def modifier_photo_profil():
    user = get_current_user()

    photo = request.files.get(
        "profile_photo"
    )

    if not photo or not photo.filename:
        return redirect(
            url_for("professeur")
        )

    mime = photo.mimetype

    if mime not in ALLOWED_IMAGES:
        return (
            "Format d'image non autorisé. "
            "Utilisez JPG, PNG ou WEBP.",
            400
        )

    photo_bytes = photo.read()

    if len(photo_bytes) > 8 * 1024 * 1024:
        return (
            "La photo est trop volumineuse. "
            "Maximum : 8 Mo.",
            400
        )

    extension = ALLOWED_IMAGES[mime]

    nom_fichier = (
        f"profils/{uuid.uuid4().hex}{extension}"
    )

    try:
        supabase.storage.from_(
            "signalements"
        ).upload(
            nom_fichier,
            photo_bytes,
            {
                "content-type": mime,
                "upsert": "false"
            }
        )

        photo_url = (
            supabase
            .storage
            .from_("signalements")
            .get_public_url(
                nom_fichier
            )
        )

        result = (
            supabase
            .table("users")
            .update({
                "profile_photo_url": photo_url
            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )

        if not result.data:
            return (
                "Impossible d'enregistrer la photo.",
                500
            )

        session["profile_photo_url"] = photo_url

        return redirect(
            url_for("professeur")
        )

    except Exception as e:
        print(
            "Erreur photo de profil :",
            repr(e)
        )

        return (
            "Impossible d'enregistrer "
            "la photo de profil.",
            500
        )


@app.route(
    "/signaler",
    methods=["POST"]
)
@professor_required
def signaler():
    user = get_current_user()

    if not user:
        return redirect(
            url_for("connexion")
        )

    auteur = user["username"]

    salle = request.form.get(
        "salle",
        ""
    ).strip()

    categorie = request.form.get(
        "categorie",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    urgence = request.form.get(
        "urgence",
        "normale"
    ).strip()

    if not salle or not categorie or not description:
        return (
            "Informations manquantes.",
            400
        )

    photo_url = None

    photo = request.files.get("photo")

    if photo and photo.filename:
        mime = photo.mimetype

        if mime not in ALLOWED_IMAGES:
            return (
                "Format d'image non autorisé. "
                "Utilisez JPG, PNG ou WEBP.",
                400
            )

        extension = ALLOWED_IMAGES[mime]

        nom_fichier = (
            f"{uuid.uuid4().hex}{extension}"
        )

        photo_bytes = photo.read()

        if len(photo_bytes) > 8 * 1024 * 1024:
            return (
                "La photo est trop volumineuse. "
                "Maximum : 8 Mo.",
                400
            )

        try:
            supabase.storage.from_(
                "signalements"
            ).upload(
                nom_fichier,
                photo_bytes,
                {
                    "content-type": mime,
                    "upsert": "false"
                }
            )

            photo_url = (
                supabase
                .storage
                .from_("signalements")
                .get_public_url(
                    nom_fichier
                )
            )

        except Exception as e:
            print(
                "Erreur upload photo :",
                repr(e)
            )

            return (
                "Impossible d'envoyer la photo.",
                500
            )

    data = {
        "auteur": auteur,
        "salle": salle,
        "categorie": categorie,
        "description": description,
        "urgence": urgence,
        "statut": "en_cours",
        "photo_url": photo_url
    }

    try:
        result = (
            supabase
            .table("problemes")
            .insert(data)
            .execute()
        )

    except Exception as e:
        print(
            "Erreur création signalement :",
            repr(e)
        )

        return (
            "Impossible de créer le signalement.",
            500
        )

    if not result.data:
        return (
            "Impossible de créer le signalement.",
            500
        )

    probleme = result.data[0]

    envoyer_notification_admins(
        probleme
    )

    return redirect(
        url_for("professeur")
    )


@app.route(
    "/inscription",
    methods=["GET", "POST"]
)
def inscription():
    erreur = None
    succes = None

    if request.method == "POST":
        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        password_confirmation = request.form.get(
            "password_confirmation",
            ""
        )

        signup_password = request.form.get(
            "signup_password",
            ""
        )

        if (
            not username
            or not password
            or not password_confirmation
            or not signup_password
        ):
            erreur = (
                "Tous les champs sont obligatoires."
            )

        elif signup_password != PROF_SIGNUP_PASSWORD:
            erreur = (
                "Le mot de passe administrateur "
                "de création est incorrect."
            )

        elif password != password_confirmation:
            erreur = (
                "Les deux mots de passe "
                "ne correspondent pas."
            )

        elif len(username) < 3:
            erreur = (
                "L'identifiant doit contenir "
                "au moins 3 caractères."
            )

        elif len(password) < 8:
            erreur = (
                "Le mot de passe doit contenir "
                "au moins 8 caractères."
            )

        else:
            try:
                existing = (
                    supabase
                    .table("users")
                    .select("id")
                    .eq(
                        "username",
                        username
                    )
                    .execute()
                )

                if existing.data:
                    erreur = (
                        "Cet identifiant est "
                        "déjà utilisé."
                    )

                else:
                    password_hash = (
                        generate_password_hash(
                            password
                        )
                    )

                    result = (
                        supabase
                        .table("users")
                        .insert({
                            "username": username,
                            "password": password_hash,
                            "role": "prof"
                        })
                        .execute()
                    )

                    if not result.data:
                        erreur = (
                            "Impossible de créer le compte."
                        )

                    else:
                        return redirect(
                            url_for("connexion")
                        )

            except Exception as e:
                print(
                    "Erreur création compte :",
                    repr(e)
                )

                erreur = (
                    "Impossible de créer le compte. "
                    "Vérifiez la configuration de Supabase."
                )

    return render_template(
        "inscription.html",
        erreur=erreur,
        succes=succes
    )


@app.route(
    "/connexion",
    methods=["GET", "POST"]
)
def connexion():
    erreur = None

    if request.method == "POST":
        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:
            erreur = (
                "Veuillez remplir tous les champs."
            )

        else:
            try:
                user = recuperer_utilisateur(
                    username
                )

                if not user:
                    erreur = (
                        "Identifiant ou mot de passe incorrect."
                    )

                else:
                    stored_password = user.get(
                        "password",
                        ""
                    )

                    password_ok = (
                        verifier_mot_de_passe(
                            stored_password,
                            password
                        )
                    )

                    if not password_ok:
                        erreur = (
                            "Identifiant ou mot de passe incorrect."
                        )

                    else:
                        if stored_password == password:
                            try:
                                (
                                    supabase
                                    .table("users")
                                    .update({
                                        "password": (
                                            generate_password_hash(
                                                password
                                            )
                                        )
                                    })
                                    .eq(
                                        "id",
                                        user["id"]
                                    )
                                    .execute()
                                )

                            except Exception as e:
                                print(
                                    "Erreur sécurisation "
                                    "ancien mot de passe :",
                                    repr(e)
                                )

                        session.clear()

                        session["user_id"] = user["id"]
                        session["username"] = user["username"]
                        session["role"] = user["role"]
                        session["profile_photo_url"] = (
                            user.get(
                                "profile_photo_url"
                            )
                        )

                        if user.get("role") == "admin":
                            return redirect(
                                url_for("dashboard")
                            )

                        if user.get("role") in (
                            "prof",
                            "professeur"
                        ):
                            return redirect(
                                url_for("professeur")
                            )

                        session.clear()

                        erreur = (
                            "Le rôle de ce compte "
                            "n'est pas reconnu."
                        )

            except Exception as e:
                print(
                    "Erreur connexion :",
                    repr(e)
                )

                erreur = (
                    "Erreur lors de la connexion."
                )

    return render_template(
        "connexion.html",
        erreur=erreur
    )


@app.route(
    "/devenir-admin",
    methods=["GET", "POST"]
)
def devenir_admin():
    erreur = None
    succes = None

    if request.method == "POST":
        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        admin_password = request.form.get(
            "admin_password",
            ""
        )

        if (
            not username
            or not password
            or not admin_password
        ):
            erreur = (
                "Tous les champs sont obligatoires."
            )

        elif admin_password != ADMIN_PROMOTION_PASSWORD:
            erreur = (
                "Le code administrateur est incorrect."
            )

        else:
            try:
                user = recuperer_utilisateur(
                    username
                )

                if not user:
                    erreur = (
                        "Aucun compte ne correspond "
                        "à cet identifiant."
                    )

                else:
                    stored_password = user.get(
                        "password",
                        ""
                    )

                    if not verifier_mot_de_passe(
                        stored_password,
                        password
                    ):
                        erreur = (
                            "Identifiant ou mot de passe incorrect."
                        )

                    elif user.get("role") == "admin":
                        erreur = (
                            "Ce compte est déjà administrateur."
                        )

                    else:
                        result = (
                            supabase
                            .table("users")
                            .update({
                                "role": "admin"
                            })
                            .eq(
                                "id",
                                user["id"]
                            )
                            .execute()
                        )

                        if not result.data:
                            erreur = (
                                "Impossible de modifier "
                                "le rôle du compte."
                            )

                        else:
                            session.clear()

                            session["user_id"] = user["id"]
                            session["username"] = user["username"]
                            session["role"] = "admin"
                            session["profile_photo_url"] = (
                                user.get(
                                    "profile_photo_url"
                                )
                            )

                            return redirect(
                                url_for("dashboard")
                            )

            except Exception as e:
                print(
                    "Erreur promotion administrateur :",
                    repr(e)
                )

                erreur = (
                    "Impossible de devenir administrateur. "
                    "Vérifiez la configuration de Supabase."
                )

    return render_template(
        "devenir_admin.html",
        erreur=erreur,
        succes=succes
    )


@app.route("/deconnexion")
def deconnexion():
    session.clear()

    return redirect(
        url_for("index")
    )


@app.route("/logout")
def logout():
    session.clear()

    return redirect(
        url_for("index")
    )


@app.route("/dashboard")
@admin_required
def dashboard():
    result = (
        supabase
        .table("problemes")
        .select("*")
        .order(
            "date_creation",
            desc=True
        )
        .execute()
    )

    problemes = result.data or []

    problemes = ajouter_durees_resolution(
        problemes
    )

    auteurs = list({
        p.get("auteur")
        for p in problemes
        if p.get("auteur")
    })

    profils = {}

    if auteurs:
        try:
            users_result = (
                supabase
                .table("users")
                .select(
                    "username,profile_photo_url"
                )
                .in_(
                    "username",
                    auteurs
                )
                .execute()
            )

            for profil in users_result.data or []:
                profils[
                    profil.get("username")
                ] = profil

        except Exception as e:
            print(
                "Erreur récupération photos de profil :",
                repr(e)
            )

    en_cours = sum(
        1
        for p in problemes
        if p.get("statut") == "en_cours"
    )

    urgents = sum(
        1
        for p in problemes
        if p.get("statut") == "en_cours"
        and p.get("urgence") == "urgente"
    )

    resolus = sum(
        1
        for p in problemes
        if p.get("statut") == "resolu"
    )

    a_reaffecter = sum(
        1
        for p in problemes
        if p.get("statut") == "nouveau"
    )

    moyenne_secondes = calculer_duree_moyenne(
        problemes
    )

    moyenne_duree = formater_duree_secondes(
        moyenne_secondes
    )

    return render_template(
        "dashboard.html",
        problemes=problemes,
        en_cours=en_cours,
        urgents=urgents,
        resolus=resolus,
        a_reaffecter=a_reaffecter,
        profils=profils,
        moyenne_duree=moyenne_duree
    )


@app.route("/probleme/<int:probleme_id>")
def probleme(probleme_id):
    user = get_current_user()

    if not user:
        return redirect(
            url_for("connexion")
        )

    result = (
        supabase
        .table("problemes")
        .select("*")
        .eq(
            "id",
            probleme_id
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        abort(404)

    probleme_data = result.data[0]

    if user.get("role") == "admin":
        pass

    elif user.get("role") in (
        "prof",
        "professeur"
    ):
        if (
            probleme_data.get("auteur")
            != user.get("username")
        ):
            abort(403)

    else:
        session.clear()

        return redirect(
            url_for("connexion")
        )

    duree_secondes = calculer_duree_affichage_secondes(
        probleme_data
    )

    if duree_secondes is not None:
        probleme_data[
            "duree_resolution_secondes"
        ] = int(
            duree_secondes
        )

        probleme_data[
            "duree_resolution"
        ] = formater_duree_secondes(
            duree_secondes
        )

    else:
        probleme_data[
            "duree_resolution_secondes"
        ] = 0

        probleme_data[
            "duree_resolution"
        ] = {
            "jours": 0,
            "heures": 0,
            "minutes": 0,
            "secondes": 0
        }

    auteur_user = None

    if probleme_data.get("auteur"):
        try:
            auteur_result = (
                supabase
                .table("users")
                .select(
                    "username,profile_photo_url"
                )
                .eq(
                    "username",
                    probleme_data["auteur"]
                )
                .limit(1)
                .execute()
            )

            if auteur_result.data:
                auteur_user = auteur_result.data[0]

        except Exception as e:
            print(
                "Erreur récupération profil auteur :",
                repr(e)
            )

    commentaires = []

    try:
        commentaires_result = (
            supabase
            .table("commentaires")
            .select("*")
            .eq(
                "probleme_id",
                probleme_id
            )
            .order(
                "date_creation",
                desc=False
            )
            .execute()
        )

        commentaires = (
            commentaires_result.data or []
        )

    except Exception as e:
        print(
            "Erreur récupération commentaires :",
            repr(e)
        )

    return render_template(
        "probleme.html",
        probleme=probleme_data,
        auteur_user=auteur_user,
        commentaires=commentaires,
        current_user=user
    )


@app.route(
    "/probleme/<int:probleme_id>/commentaire",
    methods=["POST"]
)
def ajouter_commentaire(probleme_id):
    user = get_current_user()

    if not user:
        return redirect(
            url_for("connexion")
        )

    if user.get("role") not in (
        "admin",
        "prof",
        "professeur"
    ):
        session.clear()

        return redirect(
            url_for("connexion")
        )

    contenu = request.form.get(
        "contenu",
        ""
    ).strip()

    if not contenu:
        return redirect(
            url_for(
                "probleme",
                probleme_id=probleme_id
            )
        )

    if len(contenu) > 2000:
        return (
            "Le commentaire est trop long. "
            "Maximum : 2000 caractères.",
            400
        )

    try:
        probleme_result = (
            supabase
            .table("problemes")
            .select(
                "id,auteur"
            )
            .eq(
                "id",
                probleme_id
            )
            .limit(1)
            .execute()
        )

        if not probleme_result.data:
            abort(404)

        probleme_cible = probleme_result.data[0]

        if user.get("role") in (
            "prof",
            "professeur"
        ):
            if (
                probleme_cible.get("auteur")
                != user.get("username")
            ):
                abort(403)

        commentaire_data = {
            "probleme_id": probleme_id,
            "auteur_id": user["id"],
            "auteur_nom": user["username"],
            "contenu": contenu
        }

        print(
            "[COMMENTAIRE] Tentative d'ajout :",
            commentaire_data
        )

        (
            supabase
            .table("commentaires")
            .insert(commentaire_data)
            .execute()
        )

        print(
            "[COMMENTAIRE] Commentaire ajouté avec succès."
        )

    except Exception as e:
        print(
            "[COMMENTAIRE] ERREUR AJOUT :",
            repr(e)
        )

        return (
            "Impossible d'ajouter le commentaire.",
            500
        )

    return redirect(
        url_for(
            "probleme",
            probleme_id=probleme_id
        )
    )


@app.route(
    "/probleme/<int:probleme_id>/statut",
    methods=["POST"]
)
@admin_required
def modifier_statut(probleme_id):
    statut = request.form.get(
        "statut",
        "nouveau"
    )

    responsable = request.form.get(
        "responsable",
        ""
    ).strip()

    statuts_autorises = {
        "nouveau",
        "en_cours",
        "resolu"
    }

    if statut not in statuts_autorises:
        return (
            "Statut invalide.",
            400
        )

    (
        supabase
        .table("problemes")
        .update({
            "statut": statut,
            "responsable": responsable,
            "date_modification": "now()"
        })
        .eq(
            "id",
            probleme_id
        )
        .execute()
    )

    return redirect(
        url_for(
            "probleme",
            probleme_id=probleme_id
        )
    )


@app.route("/notifications")
@admin_required
def notifications():
    return render_template(
        "notifications.html",
        vapid_public_key=VAPID_PUBLIC_KEY or ""
    )


@app.route(
    "/api/push/subscribe",
    methods=["POST"]
)
@admin_required
def push_subscribe():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Non connecté."
        }), 401

    if not VAPID_PUBLIC_KEY:
        return jsonify({
            "success": False,
            "error": (
                "La clé VAPID publique "
                "n'est pas configurée."
            )
        }), 500

    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify({
            "success": False,
            "error": "Données manquantes."
        }), 400

    endpoint = str(
        data.get("endpoint") or ""
    ).strip()

    keys = data.get("keys") or {}

    p256dh = str(
        keys.get("p256dh") or ""
    ).strip()

    auth = str(
        keys.get("auth") or ""
    ).strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({
            "success": False,
            "error": "Abonnement invalide."
        }), 400

    try:
        existing = (
            supabase
            .table("push_subscriptions")
            .select(
                "id,username,endpoint"
            )
            .eq(
                "endpoint",
                endpoint
            )
            .limit(1)
            .execute()
        )

        data_abonnement = {
            "username": user["username"],
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth
        }

        if existing.data:
            result = (
                supabase
                .table("push_subscriptions")
                .update(data_abonnement)
                .eq(
                    "endpoint",
                    endpoint
                )
                .execute()
            )

        else:
            result = (
                supabase
                .table("push_subscriptions")
                .insert(data_abonnement)
                .execute()
            )

        if not result.data:
            print(
                "[PUSH] Aucun abonnement retourné "
                "par Supabase."
            )

            return jsonify({
                "success": False,
                "error": (
                    "Impossible d'enregistrer "
                    "l'abonnement."
                )
            }), 500

        print(
            "[PUSH] ✓ Abonnement enregistré"
        )

        print(
            "[PUSH] Utilisateur :",
            user["username"]
        )

        print(
            "[PUSH] Endpoint :",
            endpoint[:120]
        )

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "[PUSH] ERREUR inscription :",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": (
                "Erreur serveur lors de "
                "l'enregistrement."
            )
        }), 500


@app.route(
    "/api/push/unsubscribe",
    methods=["POST"]
)
@admin_required
def push_unsubscribe():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    endpoint = str(
        data.get("endpoint") or ""
    ).strip()

    if not endpoint:
        return jsonify({
            "success": False,
            "error": "Endpoint manquant."
        }), 400

    try:
        (
            supabase
            .table("push_subscriptions")
            .delete()
            .eq(
                "endpoint",
                endpoint
            )
            .eq(
                "username",
                user["username"]
            )
            .execute()
        )

        print(
            "[PUSH] ✓ Abonnement désactivé pour",
            user["username"]
        )

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "[PUSH] Erreur désinscription :",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": "Erreur serveur."
        }), 500


@app.route(
    "/api/push/status",
    methods=["GET"]
)
@admin_required
def push_status():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Non connecté."
        }), 401

    try:
        result = (
            supabase
            .table("push_subscriptions")
            .select(
                "endpoint",
                count="exact"
            )
            .eq(
                "username",
                user["username"]
            )
            .execute()
        )

        count = result.count

        if count is None:
            count = len(
                result.data or []
            )

        return jsonify({
            "success": True,
            "vapid_configured": bool(
                VAPID_PUBLIC_KEY
                and VAPID_PRIVATE_KEY
                and VAPID_EMAIL
            ),
            "subscriptions": count
        })

    except Exception as e:
        print(
            "[PUSH] Erreur statut :",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": "Impossible de lire le statut."
        }), 500


@app.route(
    "/api/push/test",
    methods=["POST"]
)
@admin_required
def push_test():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Non connecté."
        }), 401

    if not VAPID_PUBLIC_KEY:
        return jsonify({
            "success": False,
            "error": "VAPID_PUBLIC_KEY absente."
        }), 500

    if not VAPID_PRIVATE_KEY:
        return jsonify({
            "success": False,
            "error": "VAPID_PRIVATE_KEY absente."
        }), 500

    try:
        result = (
            supabase
            .table("push_subscriptions")
            .select("*")
            .eq(
                "username",
                user["username"]
            )
            .execute()
        )

        subscriptions = result.data or []

        print("")
        print(
            "[PUSH TEST] ========================================"
        )
        print(
            "[PUSH TEST] Utilisateur :",
            user["username"]
        )
        print(
            "[PUSH TEST] Abonnements :",
            len(subscriptions)
        )

        if not subscriptions:
            print(
                "[PUSH TEST] Aucun abonnement."
            )

            return jsonify({
                "success": False,
                "sent": 0,
                "failed": 0,
                "error": (
                    "Aucun abonnement trouvé "
                    "pour cet administrateur."
                )
            }), 400

        payload = {
            "title": "🔔 Test Collège SOS",
            "body": (
                "Cette notification vient "
                "directement du serveur."
            ),
            "url": (
                "https://sos-college.onrender.com"
                "/notifications"
            ),
            "tag": "college-sos-test"
        }

        resultat = envoyer_push_aux_abonnements(
            subscriptions,
            payload
        )

        print(
            "[PUSH TEST] Résultat :",
            resultat
        )

        print(
            "[PUSH TEST] ========================================"
        )
        print("")

        if resultat["success"] == 0:
            return jsonify({
                "success": False,
                "sent": 0,
                "failed": resultat["failed"],
                "error": (
                    "Le serveur n'a réussi "
                    "aucun envoi."
                )
            }), 500

        return jsonify({
            "success": True,
            "sent": resultat["success"],
            "failed": resultat["failed"]
        })

    except Exception as e:
        print(
            "[PUSH TEST] ERREUR :",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": "Erreur serveur pendant le test."
        }), 500


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        app.static_folder,
        "service-worker.js",
        mimetype="application/javascript"
    )

    response.headers["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )

    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    response.headers["Service-Worker-Allowed"] = "/"

    return response


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
