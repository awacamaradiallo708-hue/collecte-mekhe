// ================= MODE =================
function setMode(mode) {
  document.getElementById("agentUI").style.display = (mode === "agent") ? "block" : "none";
  document.getElementById("dashboardUI").style.display = (mode === "dashboard") ? "block" : "none";

  if (mode === "dashboard") loadDashboard();
}

// ================= MAP =================
let map = L.map('map').setView([15.11, -16.63], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let polyline = L.polyline([], {color: 'blue'}).addTo(map);
let watchId = null;

// ================= GPS =================
function startTracking() {
  watchId = navigator.geolocation.watchPosition(pos => {

    let lat = pos.coords.latitude;
    let lon = pos.coords.longitude;

    polyline.addLatLng([lat, lon]);
    map.setView([lat, lon]);

    saveLocal({lat, lon, type: "tracking"});

  }, err => console.log(err), {enableHighAccuracy: true});
}

function stopTracking() {
  navigator.geolocation.clearWatch(watchId);
}

// ================= POINTS =================
function markPoint(type) {
  navigator.geolocation.getCurrentPosition(pos => {

    let lat = pos.coords.latitude;
    let lon = pos.coords.longitude;

    L.marker([lat, lon]).addTo(map).bindPopup(type);

    saveLocal({lat, lon, type});

  });
}

// ================= STOCKAGE =================
function saveLocal(point) {
  let data = JSON.parse(localStorage.getItem("data") || "[]");

  data.push({
    ...point,
    quartier: document.getElementById("quartier").value,
    agent: document.getElementById("agent_nom").value,
    time: new Date().toISOString()
  });

  localStorage.setItem("data", JSON.stringify(data));
}

// ================= ITINÉRAIRES =================
document.getElementById("quartier").addEventListener("change", function() {

  let q = this.value.toLowerCase().replace(" ", "_");

  fetch(`itineraires/${q}.geojson`)
    .then(res => res.json())
    .then(data => {

      L.geoJSON(data, {
        style: {
          color: "red",
          dashArray: "5,10",
          weight: 4
        }
      }).addTo(map);

    });
});

// ================= DASHBOARD =================
function loadDashboard() {

  let data = JSON.parse(localStorage.getItem("data") || "[]");

  let stats = {};

  data.forEach(d => {
    stats[d.quartier] = (stats[d.quartier] || 0) + 1;
  });

  let ctx = document.getElementById('chart');

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(stats),
      datasets: [{
        label: 'Points collectés',
        data: Object.values(stats)
      }]
    }
  });
}
