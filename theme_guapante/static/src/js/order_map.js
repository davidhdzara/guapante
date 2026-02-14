/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteOrderMap = publicWidget.Widget.extend({
    selector: '#guapante_order_map',

    start() {
        this._super(...arguments);
        this._initMap();
    },

    async _initMap() {
        const el = this.el;
        const warehouseLat = parseFloat(el.dataset.warehouseLat) || 4.6486;
        const warehouseLng = parseFloat(el.dataset.warehouseLng) || -74.1003;
        const clientLat = parseFloat(el.dataset.clientLat) || 0;
        const clientLng = parseFloat(el.dataset.clientLng) || 0;
        const warehouseName = el.dataset.warehouseName || 'Bodega Central';
        const clientName = el.dataset.clientName || 'Tu Ubicación';
        const deliveryStatus = el.dataset.deliveryStatus || 'received';

        // Load Leaflet CSS
        if (!document.querySelector('link[href*="leaflet"]')) {
            const css = document.createElement('link');
            css.rel = 'stylesheet';
            css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(css);
        }

        // Load Leaflet JS
        if (!window.L) {
            await new Promise((resolve) => {
                const script = document.createElement('script');
                script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
                script.onload = resolve;
                document.head.appendChild(script);
            });
        }

        // Wait a tick for CSS to apply
        await new Promise(r => setTimeout(r, 100));

        const L = window.L;

        // Calculate map bounds
        const hasClient = clientLat !== 0 && clientLng !== 0;
        const centerLat = hasClient ? (warehouseLat + clientLat) / 2 : warehouseLat;
        const centerLng = hasClient ? (warehouseLng + clientLng) / 2 : warehouseLng;

        const map = L.map(el, {
            scrollWheelZoom: false,
            zoomControl: true,
        }).setView([centerLat, centerLng], 13);

        // OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        // Custom icons
        const warehouseIcon = L.divIcon({
            html: '<div style="background:#1a1a2e;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.3);"><i class="fa fa-industry" style="color:white;font-size:16px;"></i></div>',
            iconSize: [36, 36],
            iconAnchor: [18, 18],
            className: '',
        });

        const clientIcon = L.divIcon({
            html: '<div style="background:#dc3545;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.3);"><i class="fa fa-map-marker" style="color:white;font-size:18px;"></i></div>',
            iconSize: [36, 36],
            iconAnchor: [18, 18],
            className: '',
        });

        const truckIcon = L.divIcon({
            html: '<div style="background:#28a745;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(40,167,69,0.5);border:3px solid white;"><i class="fa fa-truck" style="color:white;font-size:16px;"></i></div>',
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            className: '',
        });

        // Add warehouse marker
        L.marker([warehouseLat, warehouseLng], { icon: warehouseIcon })
            .addTo(map)
            .bindPopup(`<strong>${warehouseName}</strong><br><small>Punto de despacho</small>`);

        // Add client marker if coordinates exist
        if (hasClient) {
            L.marker([clientLat, clientLng], { icon: clientIcon })
                .addTo(map)
                .bindPopup(`<strong>${clientName}</strong><br><small>Dirección de entrega</small>`);

            // If shipping, add a truck marker at midpoint
            if (deliveryStatus === 'shipping') {
                const truckLat = (warehouseLat + clientLat) / 2;
                const truckLng = (warehouseLng + clientLng) / 2;
                L.marker([truckLat, truckLng], { icon: truckIcon })
                    .addTo(map)
                    .bindPopup('<strong>En camino</strong><br><small>Tu pedido está en ruta</small>')
                    .openPopup();
            }

            // Fetch route from OSRM (free, no API key)
            try {
                const url = `https://router.project-osrm.org/route/v1/driving/${warehouseLng},${warehouseLat};${clientLng},${clientLat}?overview=full&geometries=geojson`;
                const resp = await fetch(url);
                const data = await resp.json();
                if (data.routes && data.routes.length > 0) {
                    const coords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
                    L.polyline(coords, {
                        color: '#28a745',
                        weight: 4,
                        opacity: 0.8,
                        dashArray: deliveryStatus === 'shipping' ? null : '8, 8',
                    }).addTo(map);
                }
            } catch (e) {
                // If OSRM fails, draw a straight line
                L.polyline([[warehouseLat, warehouseLng], [clientLat, clientLng]], {
                    color: '#28a745',
                    weight: 3,
                    opacity: 0.6,
                    dashArray: '10, 10',
                }).addTo(map);
            }

            // Fit map to show both markers
            const bounds = L.latLngBounds(
                [warehouseLat, warehouseLng],
                [clientLat, clientLng]
            );
            map.fitBounds(bounds, { padding: [50, 50] });
        }

        // Fix the map size after render
        setTimeout(() => map.invalidateSize(), 200);
    },
});

export default publicWidget.registry.GuapanteOrderMap;
