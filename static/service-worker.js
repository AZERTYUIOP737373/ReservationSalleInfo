const CACHE_NAME = "college-sos-notifications-v3";

self.addEventListener("install", event => {
    console.log("[Collège SOS] Service Worker installé");

    event.waitUntil(
        self.skipWaiting()
    );
});

self.addEventListener("activate", event => {
    console.log("[Collège SOS] Service Worker activé");

    event.waitUntil(
        clients.claim()
    );
});

self.addEventListener("push", event => {
    console.log("[Collège SOS] 🔔 PUSH REÇU");

    let data = {
        title: "Collège SOS",
        body: "Nouveau signalement",
        url: "/dashboard",
        tag: "college-sos"
    };

    if (event.data) {
        try {
            const json = event.data.json();

            data.title = json.title || data.title;
            data.body = json.body || data.body;
            data.url = json.url || data.url;
            data.tag = json.tag || data.tag;

            console.log(
                "[Collège SOS] Données Push :",
                json
            );

        } catch (error) {
            console.error(
                "[Collège SOS] Erreur lecture Push :",
                error
            );

            try {
                data.body = event.data.text();
            } catch (textError) {
                console.error(
                    "[Collège SOS] Impossible de lire le message :",
                    textError
                );
            }
        }
    }

    let targetUrl;

    try {
        targetUrl = new URL(
            data.url || "/dashboard",
            self.location.origin
        ).href;
    } catch (error) {
        console.error(
            "[Collège SOS] URL invalide :",
            error
        );

        targetUrl = new URL(
            "/dashboard",
            self.location.origin
        ).href;
    }

    const options = {
        body: data.body,
        tag: data.tag,
        renotify: true,
        requireInteraction: true,

        icon: "/static/282-2828535_bb-logo-symbol.png",
        badge: "/static/282-2828535_bb-logo-symbol.png",

        data: {
            url: targetUrl
        }
    };

    event.waitUntil(
        self.registration.showNotification(
            data.title,
            options
        )
    );
});

self.addEventListener("notificationclick", event => {
    console.log(
        "[Collège SOS] Notification cliquée"
    );

    event.notification.close();

    const targetUrl =
        event.notification?.data?.url ||
        new URL(
            "/dashboard",
            self.location.origin
        ).href;

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(clientList => {

            for (const client of clientList) {
                if (
                    client.url.startsWith(
                        self.location.origin
                    )
                ) {
                    if ("focus" in client) {
                        return client.focus().then(
                            focusedClient => {

                                if (
                                    focusedClient &&
                                    "navigate" in focusedClient
                                ) {
                                    return focusedClient.navigate(
                                        targetUrl
                                    );
                                }

                                return focusedClient;
                            }
                        );
                    }
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(
                    targetUrl
                );
            }

            return undefined;
        })
    );
});

self.addEventListener("notificationclose", event => {
    console.log(
        "[Collège SOS] Notification fermée"
    );
});
