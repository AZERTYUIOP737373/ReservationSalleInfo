console.log("[Collège SOS] Service Worker chargé");

self.addEventListener("install", function (event) {
    console.log("[Collège SOS] Service Worker installé");

    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    console.log("[Collège SOS] Service Worker activé");

    event.waitUntil(
        clients.claim()
    );
});

self.addEventListener("push", function (event) {
    console.log("[Collège SOS] PUSH REÇU");

    let data = {
        title: "Collège SOS",
        body: "Nouveau signalement",
        url: "/dashboard",
        tag: "college-sos"
    };

    if (event.data) {
        try {
            const json = event.data.json();

            console.log(
                "[Collège SOS] Données reçues :",
                json
            );

            data = {
                title: json.title || "Collège SOS",
                body: json.body || "Nouveau signalement",
                url: json.url || "/dashboard",
                tag: json.tag || "college-sos"
            };

        } catch (error) {
            console.error(
                "[Collège SOS] Impossible de lire le JSON :",
                error
            );

            try {
                data.body = event.data.text();
            } catch (textError) {
                console.error(
                    "[Collège SOS] Impossible de lire le texte :",
                    textError
                );
            }
        }
    }

    const notificationOptions = {
        body: data.body,
        tag: data.tag,
        renotify: true,
        requireInteraction: true,
        icon: "/static/icon-192.png",
        badge: "/static/icon-192.png",
        data: {
            url: data.url
        }
    };

    console.log(
        "[Collège SOS] Affichage notification :",
        data.title,
        data.body
    );

    event.waitUntil(
        self.registration.showNotification(
            data.title,
            notificationOptions
        ).then(function () {
            console.log(
                "[Collège SOS] Notification affichée"
            );
        }).catch(function (error) {
            console.error(
                "[Collège SOS] ERREUR showNotification :",
                error
            );

            throw error;
        })
    );
});

self.addEventListener("notificationclick", function (event) {
    console.log("[Collège SOS] Notification cliquée");

    event.notification.close();

    const notificationData =
        event.notification.data || {};

    const targetUrl =
        notificationData.url || "/dashboard";

    let finalUrl;

    try {
        const url = new URL(
            targetUrl,
            "https://reservation-salle-info.onrender.com"
        );

        finalUrl =
            "https://reservation-salle-info.onrender.com" +
            url.pathname +
            url.search +
            url.hash;

    } catch (error) {
        console.error(
            "[Collège SOS] URL invalide :",
            error
        );

        finalUrl =
            "https://reservation-salle-info.onrender.com/dashboard";
    }

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (clientList) {

            for (const client of clientList) {
                if ("focus" in client) {
                    client.navigate(finalUrl);
                    return client.focus();
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(finalUrl);
            }
        })
    );
});