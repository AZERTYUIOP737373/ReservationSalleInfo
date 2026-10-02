
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

    let targetUrl = event.notification.data?.url || "/dashboard";

    /*
     * Toujours construire l'adresse à partir du site
     * qui a enregistré le service worker.
     */
    const url = new URL(targetUrl, self.location.origin);

    event.waitUntil(
        clients.openWindow(url.href)
    );
});
