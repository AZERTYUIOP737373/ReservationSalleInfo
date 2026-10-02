import os
import uuid
import json
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


VAPID_PRIVATE_KEY = "6dlCw-898B4sND2xNNSRMkyusOb3pOvApo07UTEmgww"

VAPID_PUBLIC_KEY = "BAFbXzUBcO30aqu7ly0oIV0fhv3jDQRsIPUtuoGKiw67PjYUpyPD4QCC-k1SpIIuxgix4SvJyWeJRNyf7mrnQKI"

VAPID_EMAIL = "mailto:baptiste.brygal@gmail.com"


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL et SUPABASE_KEY doivent être configurées."
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
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
        "role": session.get("role")
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


def supprimer_abonnement_push(endpoint):
    if not endpoint:
        return

    try:
        (
            supabase
            .table("push_subscriptions")
            .delete()
            .eq("endpoint", endpoint)
            .execute()
        )

        print("[PUSH] Abonnement supprimé :", endpoint[:80])

    except Exception as e:
        print(
            "[PUSH] Impossible de supprimer l'abonnement :",
            repr(e)
        )


def envoyer_notification_admins(probleme):
    print("[PUSH] ========================================")
    print("[PUSH] Début envoi notification")
    print("[PUSH] Signalement :", probleme.get("id"))

    try:
        admins_result = (
            supabase
            .table("users")
            .select("username")
            .eq("role", "admin")
            .execute()
        )

        admins = admins_result.data or []

        if not admins:
            print("[PUSH] Aucun administrateur trouvé.")
            return

        noms_admins = [
            admin.get("username")
            for admin in admins
            if admin.get("username")
        ]

        print("[PUSH] Administrateurs :", noms_admins)

        if not noms_admins:
            print("[PUSH] Aucun nom administrateur valide.")
            return

        subscriptions_result = (
            supabase
            .table("push_subscriptions")
            .select("*")
            .in_("username", noms_admins)
            .execute()
        )

        subscriptions = subscriptions_result.data or []

        print(
            "[PUSH] Nombre d'abonnements trouvés :",
            len(subscriptions)
        )

        if not subscriptions:
            print(
                "[PUSH] Aucun appareil administrateur "
                "abonné aux notifications."
            )
            return

        urgence = probleme.get("urgence", "normale")
        salle = probleme.get("salle", "Salle inconnue")
        categorie = probleme.get("categorie", "Problème")
        description = probleme.get("description", "")
        probleme_id = probleme.get("id")

        if len(description) > 140:
            description = description[:137] + "..."

        if urgence == "urgente":
            titre = "🚨 Signalement URGENT"
        else:
            titre = "🚨 Nouveau signalement"

        corps = (
            f"{salle} • {categorie}\n"
            f"{description}"
        )

        # URL ABSOLUE afin que le navigateur ne puisse jamais
        # interpréter l'adresse comme une ancienne URL locale.
        url_signalement = (
            f"https://reservation-salle-info.onrender.com"
            f"/probleme/{probleme_id}"
        )

        payload = {
            "title": titre,
            "body": corps,
            "url": url_signalement,
            "tag": f"signalement-{probleme_id}"
        }

        print("[PUSH] Payload :", json.dumps(
            payload,
            ensure_ascii=False
        ))

        succes = 0
        echecs = 0

        for subscription in subscriptions:

            username = subscription.get("username")
            endpoint = subscription.get("endpoint")
            p256dh = subscription.get("p256dh")
            auth = subscription.get("auth")

            print(
                "[PUSH] ----------------------------------------"
            )
            print("[PUSH] Utilisateur :", username)
            print(
                "[PUSH] Endpoint :",
                endpoint[:100] if endpoint else "ABSENT"
            )

            if not endpoint or not p256dh or not auth:
                print(
                    "[PUSH] Abonnement incomplet -> suppression."
                )

                supprimer_abonnement_push(endpoint)
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
                    "[PUSH] ✓ Notification acceptée par le service Push"
                )

                if response is not None:
                    try:
                        print(
                            "[PUSH] Réponse Push :",
                            getattr(response, "status_code", response)
                        )
                    except Exception:
                        pass

            except WebPushException as e:
                echecs += 1

                response = getattr(e, "response", None)

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
                    "[PUSH] ✗ WebPushException"
                )
                print(
                    "[PUSH] Utilisateur :",
                    username
                )
                print(
                    "[PUSH] Status HTTP :",
                    status_code
                )
                print(
                    "[PUSH] Erreur :",
                    repr(e)
                )

                if response is not None:
                    try:
                        print(
                            "[PUSH] Réponse serveur :",
                            response.text[:1000]
                        )
                    except Exception:
                        pass

                # Un abonnement avec 404/410 est généralement
                # définitivement expiré.
                if status_code in (404, 410):
                    print(
                        "[PUSH] Abonnement expiré/introuvable."
                    )

                    supprimer_abonnement_push(endpoint)

            except Exception as e:
                echecs += 1

                print(
                    "[PUSH] ✗ Erreur inattendue :",
                    repr(e)
                )

        print("[PUSH] ========================================")
        print(
            f"[PUSH] Résultat : {succes} accepté(s), "
            f"{echecs} échec(s)"
        )
        print("[PUSH] ========================================")

    except Exception as e:
        print(
            "[PUSH] Impossible d'envoyer les notifications :",
            repr(e)
        )


@app.route("/")
def index():
    user = get_current_user()

    if user:
        if user.get("role") == "admin":
            return redirect(url_for("dashboard"))

        if user.get("role") in ("prof", "professeur"):
            return redirect(url_for("professeur"))

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

    mes_signalements = []

    try:
        result = (
            supabase
            .table("problemes")
            .select("*")
            .eq("auteur", user["username"])
            .order("date_creation", desc=True)
            .execute()
        )

        mes_signalements = result.data or []

    except Exception as e:
        print("Erreur récupération signalements :", e)

    return render_template(
        "index.html",
        user=user,
        mes_signalements=mes_signalements,
        auteur=user["username"]
    )


@app.route("/signaler", methods=["POST"])
@professor_required
def signaler():
    user = get_current_user()

    if not user:
        return redirect(url_for("connexion"))

    auteur = user["username"]

    salle = request.form.get("salle", "").strip()
    categorie = request.form.get("categorie", "").strip()
    description = request.form.get("description", "").strip()
    urgence = request.form.get("urgence", "normale").strip()

    if not salle or not categorie or not description:
        return "Informations manquantes.", 400

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
        nom_fichier = f"{uuid.uuid4().hex}{extension}"

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
            print("Erreur upload photo :", e)
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
        "statut": "nouveau",
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
        print("Erreur création signalement :", e)
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

    envoyer_notification_admins(probleme)

    return redirect(url_for("professeur"))


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    erreur = None
    succes = None

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
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
            erreur = "Tous les champs sont obligatoires."

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
                    .eq("username", username)
                    .execute()
                )

                if existing.data:
                    erreur = (
                        "Cet identifiant est "
                        "déjà utilisé."
                    )

                else:
                    password_hash = generate_password_hash(
                        password
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
                        succes = (
                            "Compte professeur créé "
                            "avec succès."
                        )

            except Exception as e:
                print("Erreur création compte :", e)

                erreur = (
                    "Impossible de créer le compte. "
                    "Vérifiez la configuration de Supabase."
                )

    return render_template(
        "inscription.html",
        erreur=erreur,
        succes=succes
    )


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    erreur = None

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            erreur = (
                "Veuillez remplir tous les champs."
            )

        else:
            try:
                user = recuperer_utilisateur(username)

                if not user:
                    erreur = (
                        "Identifiant ou mot de passe incorrect."
                    )

                else:
                    stored_password = user.get(
                        "password",
                        ""
                    )

                    password_ok = verifier_mot_de_passe(
                        stored_password,
                        password
                    )

                    if not password_ok:
                        erreur = (
                            "Identifiant ou mot de passe incorrect."
                        )

                    else:
                        if stored_password == password:
                            try:
                                supabase.table(
                                    "users"
                                ).update({
                                    "password": generate_password_hash(
                                        password
                                    )
                                }).eq(
                                    "id",
                                    user["id"]
                                ).execute()

                            except Exception as e:
                                print(
                                    "Erreur sécurisation "
                                    "ancien mot de passe :",
                                    e
                                )

                        session.clear()

                        session["user_id"] = user["id"]
                        session["username"] = user["username"]
                        session["role"] = user["role"]

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
                print("Erreur connexion :", e)

                erreur = (
                    "Erreur lors de la connexion."
                )

    return render_template(
        "connexion.html",
        erreur=erreur
    )


@app.route("/devenir-admin", methods=["GET", "POST"])
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

        if not username or not password or not admin_password:
            erreur = "Tous les champs sont obligatoires."

        elif admin_password != ADMIN_PROMOTION_PASSWORD:
            erreur = "Le code administrateur est incorrect."

        else:
            try:
                user = recuperer_utilisateur(username)

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

                            return redirect(
                                url_for("dashboard")
                            )

            except Exception as e:
                print(
                    "Erreur promotion administrateur :",
                    e
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

    urgents = sum(
        1
        for p in problemes
        if p.get("urgence") == "urgente"
        and p.get("statut") != "resolu"
    )

    en_cours = sum(
        1
        for p in problemes
        if p.get("statut") == "en_cours"
    )

    resolus = sum(
        1
        for p in problemes
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
        return "Statut invalide.", 400

    supabase.table(
        "problemes"
    ).update({
        "statut": statut,
        "responsable": responsable,
        "date_modification": "now()"
    }).eq(
        "id",
        probleme_id
    ).execute()

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
        vapid_public_key=VAPID_PUBLIC_KEY
    )


@app.route("/api/push/subscribe", methods=["POST"])
@admin_required
def push_subscribe():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Non connecté."
        }), 401

    data = request.get_json(silent=True)

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
        # Un endpoint correspond à un appareil/navigateur.
        # On supprime d'abord toute ancienne association
        # avec un autre compte.
        (
            supabase
            .table("push_subscriptions")
            .delete()
            .eq("endpoint", endpoint)
            .neq("username", user["username"])
            .execute()
        )

        result = (
            supabase
            .table("push_subscriptions")
            .upsert(
                {
                    "username": user["username"],
                    "endpoint": endpoint,
                    "p256dh": p256dh,
                    "auth": auth
                },
                on_conflict="endpoint"
            )
            .execute()
        )

        if not result.data:
            print(
                "[PUSH] Echec enregistrement abonnement."
            )

            return jsonify({
                "success": False,
                "error": "Impossible d'enregistrer l'abonnement."
            }), 500

        print(
            "[PUSH] Nouvel abonnement enregistré pour",
            user["username"]
        )

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "Erreur enregistrement abonnement push :",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": "Erreur serveur."
        }), 500


@app.route("/api/push/unsubscribe", methods=["POST"])
@admin_required
def push_unsubscribe():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False
        }), 401

    data = request.get_json(silent=True) or {}

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
            .eq("endpoint", endpoint)
            .eq("username", user["username"])
            .execute()
        )

        print(
            "[PUSH] Abonnement supprimé pour",
            user["username"]
        )

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "Erreur suppression abonnement push :",
            repr(e)
        )

        return jsonify({
            "success": False
        }), 500


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        app.static_folder,
        "service-worker.js",
        mimetype="application/javascript"
    )

    # Empêche le navigateur de conserver trop longtemps
    # une ancienne version du service worker.
    response.headers["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

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
