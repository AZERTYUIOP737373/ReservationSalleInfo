
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

    let targetUrl = "/dashboard";

    if (
        event.notification.data &&
        event.notification.data.url
    ) {
        targetUrl = event.notification.data.url;
    }

    /*
     * Si l'ancienne notification contient une adresse locale
     * comme 127.0.0.1 ou localhost, on la remplace par
     * l'adresse actuelle du site.
     */
    try {
        const parsedUrl = new URL(
            targetUrl,
            self.location.origin
        );

        if (
            parsedUrl.hostname === "127.0.0.1" ||
            parsedUrl.hostname === "localhost" ||
            parsedUrl.hostname === "0.0.0.0"
        ) {
            targetUrl = "/dashboard";
        } else {
            targetUrl = parsedUrl.href;
        }
    } catch (error) {
        targetUrl = "/dashboard";
    }

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (clientList) {

            for (const client of clientList) {

                if ("navigate" in client) {
                    return client.navigate(targetUrl)
                        .then(function () {
                            return client.focus();
                        });
                }

                if ("focus" in client) {
                    return client.focus();
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
