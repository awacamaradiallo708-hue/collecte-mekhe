let map = L.map('map').setView([15.11, -16.63], 13);

// Fond de carte
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap'
}).addTo(map);

// ==================== VARIABLES ====================
let watchId = null;
let path = [];
let polyline = L.polyline([], {color: 'blue'}).addTo(map);

// ==================== GPS TRACKING ====================
function startTracking() {
  if (!navigator.geolocation) {
    alert("GPS non supporté");
    return;
  }

  watchId = navigator.geolocation.watchPosition(position => {
    let lat = position.coords.latitude;
    let lon = position.coords.longitude;

    let point = [lat, lon];
    path.push(point);

    polyline.addLatLng(point);

    map.setView(point);

    // Sauvegarde locale
    saveLocal(point);

  }, err => {
    console.error(err);
  }, {
    enableHighAccuracy: true,
    maximumAge: 1000
  });
}

function stopTracking() {
  if (watchId) {
    navigator.geolocation.clearWatch(watchId);
  }
}

// ==================== STOCKAGE LOCAL ====================
function saveLocal(point) {
  let data = JSON.parse(localStorage.getItem("trajet") || "[]");
  data.push({
    lat: point[0],
    lon: point[1],
    time: new Date().toISOString()
  });
  localStorage.setItem("trajet", JSON.stringify(data));
}

// ==================== SYNCHRONISATION ====================
async function syncData() {
  let data = JSON.parse(localStorage.getItem("trajet") || "[]");

  if (data.length === 0) {
    alert("Aucune donnée");
    return;
  }

  try {
    await fetch("https://ton-api.com/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    });

    alert("Synchronisé !");
    localStorage.removeItem("trajet");

  } catch (e) {
    alert("Erreur connexion");
  }
}

// ==================== CHARGEMENT GEOJSON ====================
document.getElementById("geojsonInput").addEventListener("change", function(e) {

  const files = e.target.files;
  let colors = ["red", "green", "orange", "purple", "black"];

  for (let i = 0; i < files.length; i++) {
    let reader = new FileReader();

    reader.onload = function(event) {
      let geojson = JSON.parse(event.target.result);

      L.geoJSON(geojson, {
        style: {
          color: colors[i % colors.length],
          weight: 4,
          dashArray: "5, 10"
        }
      }).addTo(map);
    };

    reader.readAsText(files[i]);
  }
});
