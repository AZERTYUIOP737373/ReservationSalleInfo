
self.addEventListener("push", function (event) {
    let data = {
        title: "Collège SOS",
        body: "Nouveau signalement",
        url: "/dashboard",
        tag: "college-sos"
    };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (error) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body || "Nouveau signalement",
        tag: data.tag || "college-sos",
        renotify: true,
        requireInteraction: true,
        data: {
            url: data.url || "/dashboard"
        }
    };

    event.waitUntil(
        self.registration.showNotification(
            data.title || "Collège SOS",
            options
        )
    );
});


self.addEventListener("notificationclick", function (event) {
    event.notification.close();

    const notificationData = event.notification.data || {};
    let targetUrl = notificationData.url || "/dashboard";

    try {
        const url = new URL(targetUrl, self.location.origin);

        /*
         * On force l'utilisation du domaine Render.
         * Cela évite les anciennes adresses locales
         * comme 127.0.0.1 ou localhost.
         */
        const renderUrl =
            "https://reservation-salle-info.onrender.com" +
            url.pathname +
            url.search +
            url.hash;

        event.waitUntil(
            clients.matchAll({
                type: "window",
                includeUncontrolled: true
            }).then(function (clientList) {

                /*
                 * Si le site Render est déjà ouvert,
                 * on essaie de le mettre au premier plan.
                 */
                for (const client of clientList) {
                    try {
                        const clientUrl = new URL(client.url);

                        if (
                            clientUrl.origin ===
                            "https://reservation-salle-info.onrender.com"
                        ) {
                            return client.focus().then(function () {
                                if ("navigate" in client) {
                                    return client.navigate(renderUrl);
                                }
                            });
                        }
                    } catch (error) {
                        // On continue vers openWindow
                    }
                }

                /*
                 * Sinon on ouvre directement une nouvelle
                 * fenêtre/onglet vers le site Render.
                 */
                return clients.openWindow(renderUrl);
            })
        );

    } catch (error) {
        event.waitUntil(
            clients.openWindow(
                "https://reservation-salle-info.onrender.com/dashboard"
            )
        );
    }
});
