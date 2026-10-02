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
        const url = new URL(
            targetUrl,
            "https://reservation-salle-info.onrender.com"
        );

        const renderUrl =
            "https://reservation-salle-info.onrender.com" +
            url.pathname +
            url.search +
            url.hash;

        event.waitUntil(
            clients.openWindow(renderUrl)
        );

    } catch (error) {
        event.waitUntil(
            clients.openWindow(
                "https://reservation-salle-info.onrender.com/dashboard"
            )
        );
    }
});

