const CACHE_NAME = "college-sos-v2";

self.addEventListener("install", event => {
    console.log("[Collège SOS] Service Worker installé");
    self.skipWaiting();
});

self.addEventListener("activate", event => {
    console.log("[Collège SOS] Service Worker activé");

    event.waitUntil(
        clients.claim()
    );
});

self.addEventListener("push", event => {
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

            data.title = json.title || data.title;
            data.body = json.body || data.body;
            data.url = json.url || data.url;
            data.tag = json.tag || data.tag;

            console.log("[Collège SOS] Données Push :", json);
        } catch (error) {
            console.error(
                "[Collège SOS] Erreur lecture Push :",
                error
            );

            try {
                data.body = event.data.text();
            } catch (textError) {
                console.error(
                    "[Collège SOS] Impossible de lire le message",
                    textError
                );
            }
        }
    }

    const options = {
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

    event.waitUntil(
        self.registration.showNotification(
            data.title,
            options
        )
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    const url = event.notification.data?.url || "/dashboard";

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(clientList => {

            for (const client of clientList) {
                if ("focus" in client) {
                    return client.focus().then(() => {
                        if ("navigate" in client) {
                            return client.navigate(url);
                        }
                    });
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
