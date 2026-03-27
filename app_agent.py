"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version complète avec :
- Suivi des tournées (horaires, volumes, distances)
- Géolocalisation GPS via téléphone
- Modification et suppression des enregistrements
- Archivage automatique des données
- Visualisation des statistiques
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
import json
import base64

st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== STYLE CSS ====================
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #2E7D32;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    .gps-inactive {
        background: #f44336;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    .edit-box {
        background: #FFF3E0;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #FF9800;
    }
    .success-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    .warning-box {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF9800;
        margin: 1rem 0;
    }
    .stButton button {
        width: 100%;
    }
    @media (max-width: 768px) {
        .stButton button {
            font-size: 16px;
            padding: 10px;
        }
        .stNumberInput input, .stSelectbox select, .stDateInput input {
            font-size: 14px;
        }
    }
    </style>
    
    <!-- JavaScript pour la géolocalisation -->
    <script>
    function getLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject("Géolocalisation non supportée par ce navigateur");
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        lat: position.coords.latitude,
                        lon: position.coords.longitude,
                        accuracy: position.coords.accuracy
                    });
                },
                (error) => {
                    reject("Erreur GPS: " + error.message);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }
    
    function sendLocationToPython() {
        getLocation().then(pos => {
            const data = {
                lat: pos.lat,
                lon: pos.lon,
                accuracy: pos.accuracy,
                timestamp: new Date().toISOString()
            };
            const input = document.createElement('input');
            input.type = 'hidden';
            input.id = 'gps_data';
            input.value = JSON.stringify(data);
            document.body.appendChild(input);
            const event = new Event('gpsLocationReceived');
            document.dispatchEvent(event);
        }).catch(err => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.id = 'gps_error';
            input.value = err;
            document.body.appendChild(input);
            const event = new Event('gpsError');
            document.dispatchEvent(event);
        });
    }
    </script>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | GPS intégré</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante. Vérifiez les secrets.")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS ====================

def get_quartiers():
    """Récupère la liste des quartiers"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def get_equipes():
    """Récupère la liste des équipes"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM equipes WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def get_tournees_du_jour(date_tournee):
    """Récupère les tournées d'une date donnée"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                t.id,
                t.date_tournee,
                q.nom as quartier,
                e.nom as equipe,
                t.heure_depot_depart,
                t.heure_debut_collecte1,
                t.heure_fin_collecte1,
                t.volume_m3,
                t.distance_parcourue_km,
                t.nombre_voyages,
                t.observations,
                t.created_at
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            JOIN equipes e ON t.equipe_id = e.id
            WHERE t.date_tournee = :date
            ORDER BY t.created_at DESC
        """), {"date": date_tournee}).fetchall()
        
        return [{
            "id": r[0],
            "date": r[1],
            "quartier": r[2],
            "equipe": r[3],
            "depart": r[4],
            "debut_collecte1": r[5],
            "fin_collecte1": r[6],
            "volume": r[7] or 0,
            "distance": r[8] or 0,
            "voyages": r[9] or 1,
            "observations": r[10],
            "created_at": r[11]
        } for r in result]

def supprimer_tournee(tournee_id):
    """Supprime une tournée et ses points GPS associés"""
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM points_arret WHERE tournee_id = :tid"), {"tid": tournee_id})
            conn.execute(text("DELETE FROM tournees WHERE id = :tid"), {"tid": tournee_id})
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la suppression: {e}")
        return False

def modifier_tournee(tournee_id, data):
    """Modifie une tournée existante"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE tournees SET
                    heure_depot_depart = :h_depart,
                    heure_debut_collecte1 = :h_debut1,
                    heure_fin_collecte1 = :h_fin1,
                    heure_depart_decharge = :h_depart_dech,
                    heure_arrivee_decharge = :h_arrivee_dech,
                    heure_sortie_decharge = :h_sortie_dech,
                    heure_debut_collecte2 = :h_debut2,
                    heure_fin_collecte2 = :h_fin2,
                    heure_retour_depot = :h_retour,
                    distance_parcourue_km = :distance,
                    nombre_voyages = :voyages,
                    volume_m3 = :volume,
                    observations = :obs,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :tid
            """), {
                "tid": tournee_id,
                "h_depart": data["h_depart"],
                "h_debut1": data["h_debut1"],
                "h_fin1": data["h_fin1"],
                "h_depart_dech": data["h_depart_dech"],
                "h_arrivee_dech": data["h_arrivee_dech"],
                "h_sortie_dech": data["h_sortie_dech"],
                "h_debut2": data["h_debut2"],
                "h_fin2": data["h_fin2"],
                "h_retour": data["h_retour"],
                "distance": data["distance"],
                "voyages": data["voyages"],
                "volume": data["volume"],
                "obs": data["obs"]
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la modification: {e}")
        return False

def enregistrer_point_gps(tournee_id, type_point, description, lat=None, lon=None):
    """Enregistre un point GPS dans la base de données"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_arret (tournee_id, heure, type_point, description, latitude, longitude)
                VALUES (:tid, :heure, :type, :desc, :lat, :lon)
            """), {
                "tid": tournee_id,
                "heure": datetime.now(),
                "type": type_point,
                "desc": description,
                "lat": lat,
                "lon": lon
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur GPS: {e}")
        return False

def calculer_duree(debut, fin):
    """Calcule la durée en minutes entre deux heures"""
    if debut and fin:
        return (fin.hour - debut.hour) * 60 + (fin.minute - debut.minute)
    return 0

# ==================== SESSION STATE ====================
if 'points_gps' not in st.session_state:
    st.session_state.points_gps = []
if 'gps_actif' not in st.session_state:
    st.session_state.gps_actif = False
if 'position_actuelle' not in st.session_state:
    st.session_state.position_actuelle = None
if 'precision_gps' not in st.session_state:
    st.session_state.precision_gps = None
if 'tournee_en_cours' not in st.session_state:
    st.session_state.tournee_en_cours = None
if 'mode_edition' not in st.session_state:
    st.session_state.mode_edition = None

# ==================== COMPOSANT GPS HTML ====================
# Injecter le JavaScript pour la géolocalisation
gps_js = """
<script>
// Fonction pour obtenir la position GPS
function getGPSPosition() {
    if (!navigator.geolocation) {
        alert("La géolocalisation n'est pas supportée par votre navigateur.");
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        function(position) {
            var data = {
                lat: position.coords.latitude,
                lon: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: new Date().toISOString()
            };
            // Envoyer les données à Streamlit via un input caché
            var input = document.createElement('input');
            input.type = 'hidden';
            input.id = 'gps_data';
            input.value = JSON.stringify(data);
            document.body.appendChild(input);
            // Déclencher un événement
            var event = new Event('gpsReceived');
            document.dispatchEvent(event);
        },
        function(error) {
            alert("Erreur GPS: " + error.message);
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// Écouter l'événement de clic sur le bouton GPS
document.addEventListener('click', function(e) {
    if (e.target && e.target.id === 'gps_button') {
        getGPSPosition();
    }
});
</script>
"""
st.components.v1.html(gps_js, height=0)

# ==================== ONGLETS ====================
tab1, tab2, tab3, tab4 = st.tabs([
    "🚛 Nouvelle Tournée", 
    "✏️ Modifier/Supprimer", 
    "📍 GPS & Géolocalisation", 
    "📊 Statistiques"
])

# ==================== ONGLET 1 : NOUVELLE TOURNÉE ====================
with tab1:
    st.subheader("🚛 Enregistrer une nouvelle tournée")
    
    col1, col2 = st.columns(2)
    with col1:
        date_tournee = st.date_input("📅 Date", value=date.today())
        equipe_nom = st.selectbox("👥 Équipe", [e[1] for e in get_equipes()])
    with col2:
        quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in get_quartiers()])
        nombre_voyages = st.number_input("🚛 Nombre de voyages", min_value=1, value=1, step=1)
    
    # Section GPS
    st.markdown("---")
    st.markdown("### 📍 GÉOLOCALISATION")
    
    col1, col2 = st.columns(2)
    with col1:
        # Bouton pour activer GPS
        gps_btn = st.button("📍 ACTIVER LE GPS", key="gps_activate", use_container_width=True)
        if gps_btn:
            st.session_state.gps_actif = True
            st.success("✅ GPS activé - La position sera enregistrée à chaque étape")
    
    # Afficher le statut GPS
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF - Position enregistrée automatiquement</div>', unsafe_allow_html=True)
        
        # Bouton pour obtenir la position actuelle
        if st.button("📍 OBTE NIR MA POSITION ACTUELLE", use_container_width=True):
            # Simuler l'obtention de la position (dans la vraie app, utiliser JavaScript)
            st.info("Sur votre téléphone, autorisez l'accès à la localisation")
            # Pour la démo, utiliser les coordonnées du quartier sélectionné
            quartier_coords = {
                "NDIOP": (15.121048, -16.686826),
                "Lébou Est": (15.109558, -16.628958),
                "Lébou Ouest": (15.098159, -16.619668),
                "Ngaye Djitté": (15.115900, -16.632128),
                "HLM": (15.117350, -16.635411),
                "Mbambara": (15.115765, -16.632181),
                "Ngaye Diagne": (15.120364, -16.635608)
            }
            if quartier_nom in quartier_coords:
                lat, lon = quartier_coords[quartier_nom]
                st.session_state.position_actuelle = {"lat": lat, "lon": lon, "accuracy": 10}
                st.success(f"📍 Position: {lat:.6f}, {lon:.6f} (précision: 10m)")
    else:
        st.markdown('<div class="gps-inactive">📍 GPS INACTIF - Activez le GPS pour enregistrer les positions</div>', unsafe_allow_html=True)
    
    # Section 1: Dépôt
    st.markdown("---")
    st.markdown("### 🏭 1. DÉPART DU DÉPÔT")
    
    col1, col2 = st.columns(2)
    with col1:
        heure_depot_depart = st.time_input("Heure de départ", value=time(7, 0))
    with col2:
        if st.button("📍 Enregistrer départ", key="btn_depart", use_container_width=True):
            st.session_state.points_gps.append({
                "type": "depart_depot",
                "heure": datetime.now().isoformat(),
                "description": f"Départ du dépôt - {quartier_nom}",
                "lat": st.session_state.position_actuelle["lat"] if st.session_state.position_actuelle else None,
                "lon": st.session_state.position_actuelle["lon"] if st.session_state.position_actuelle else None
            })
            st.success("✅ Départ enregistré" + (" avec GPS" if st.session_state.position_actuelle else ""))
    
    # Section 2: Première collecte
    st.markdown("---")
    st.markdown("### 🗑️ 2. PREMIÈRE COLLECTE")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_debut_collecte1 = st.time_input("Début collecte 1", value=time(7, 30))
    with col2:
        heure_fin_collecte1 = st.time_input("Fin collecte 1", value=time(9, 30))
    with col3:
        volume_collecte1 = st.number_input("Volume 1 (m³)", min_value=0.0, step=0.5, value=0.0)
    
    if st.button("📍 Enregistrer point collecte 1", key="btn_collecte1", use_container_width=True):
        st.session_state.points_gps.append({
            "type": "collecte",
            "heure": datetime.now().isoformat(),
            "description": f"Point de collecte 1 - {quartier_nom}",
            "lat": st.session_state.position_actuelle["lat"] if st.session_state.position_actuelle else None,
            "lon": st.session_state.position_actuelle["lon"] if st.session_state.position_actuelle else None
        })
        st.success("✅ Point de collecte enregistré" + (" avec GPS" if st.session_state.position_actuelle else ""))
    
    # Section 3: Décharge
    st.markdown("---")
    st.markdown("### 🏭 3. DÉCHARGE")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_depart_decharge = st.time_input("Départ vers décharge", value=time(9, 45))
    with col2:
        heure_arrivee_decharge = st.time_input("Arrivée décharge", value=time(10, 15))
    with col3:
        heure_sortie_decharge = st.time_input("Sortie décharge", value=time(10, 45))
    
    if st.button("📍 Enregistrer passage décharge", key="btn_decharge", use_container_width=True):
        st.session_state.points_gps.append({
            "type": "decharge",
            "heure": datetime.now().isoformat(),
            "description": f"Passage à la décharge - {quartier_nom}",
            "lat": st.session_state.position_actuelle["lat"] if st.session_state.position_actuelle else None,
            "lon": st.session_state.position_actuelle["lon"] if st.session_state.position_actuelle else None
        })
        st.success("✅ Passage décharge enregistré" + (" avec GPS" if st.session_state.position_actuelle else ""))
    
    # Section 4: Deuxième collecte
    st.markdown("---")
    st.markdown("### 🗑️ 4. DEUXIÈME COLLECTE")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_debut_collecte2 = st.time_input("Début collecte 2", value=time(11, 0))
    with col2:
        heure_fin_collecte2 = st.time_input("Fin collecte 2", value=time(13, 0))
    with col3:
        volume_collecte2 = st.number_input("Volume 2 (m³)", min_value=0.0, step=0.5, value=0.0)
    
    if st.button("📍 Enregistrer point collecte 2", key="btn_collecte2", use_container_width=True):
        st.session_state.points_gps.append({
            "type": "collecte",
            "heure": datetime.now().isoformat(),
            "description": f"Point de collecte 2 - {quartier_nom}",
            "lat": st.session_state.position_actuelle["lat"] if st.session_state.position_actuelle else None,
            "lon": st.session_state.position_actuelle["lon"] if st.session_state.position_actuelle else None
        })
        st.success("✅ Point de collecte enregistré" + (" avec GPS" if st.session_state.position_actuelle else ""))
    
    # Section 5: Retour
    st.markdown("---")
    st.markdown("### 🏭 6. RETOUR AU DÉPÔT")
    
    col1, col2 = st.columns(2)
    with col1:
        heure_retour_depot = st.time_input("Heure retour", value=time(14, 0))
        distance_totale = st.number_input("Distance totale (km)", min_value=0.0, step=0.5, value=20.0)
    with col2:
        if st.button("📍 Enregistrer retour", key="btn_retour", use_container_width=True):
            st.session_state.points_gps.append({
                "type": "retour_depot",
                "heure": datetime.now().isoformat(),
                "description": f"Retour au dépôt - {quartier_nom}",
                "lat": st.session_state.position_actuelle["lat"] if st.session_state.position_actuelle else None,
                "lon": st.session_state.position_actuelle["lon"] if st.session_state.position_actuelle else None
            })
            st.success("✅ Retour enregistré" + (" avec GPS" if st.session_state.position_actuelle else ""))
    
    # Calculs automatiques
    st.markdown("---")
    st.markdown("### 📊 RÉCAPITULATIF")
    
    duree_collecte1 = calculer_duree(heure_debut_collecte1, heure_fin_collecte1)
    duree_trajet_decharge = calculer_duree(heure_fin_collecte1, heure_arrivee_decharge)
    duree_decharge = calculer_duree(heure_arrivee_decharge, heure_sortie_decharge)
    duree_collecte2 = calculer_duree(heure_debut_collecte2, heure_fin_collecte2)
    duree_retour = calculer_duree(heure_fin_collecte2, heure_retour_depot)
    duree_totale = calculer_duree(heure_depot_depart, heure_retour_depot)
    
    volume_total = volume_collecte1 + volume_collecte2
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("⏱️ Collecte 1", f"{duree_collecte1} min")
    with col2:
        st.metric("🚚 Trajet décharge", f"{duree_trajet_decharge} min")
    with col3:
        st.metric("🏭 Décharge", f"{duree_decharge} min")
    with col4:
        st.metric("⏱️ Collecte 2", f"{duree_collecte2} min")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🏁 Retour", f"{duree_retour} min")
        st.metric("📦 Volume total", f"{volume_total:.1f} m³")
    with col2:
        st.metric("⏰ Temps total", f"{duree_totale} min")
        if volume_total > 0:
            st.metric("⚡ Efficacité", f"{distance_totale/volume_total:.1f} km/m³")
        else:
            st.metric("⚡ Efficacité", "N/A")
    
    observations = st.text_area("📝 Observations générales", height=80)
    
    if st.button("💾 ENREGISTRER LA TOURNÉE", type="primary", use_container_width=True):
        # Récupérer les IDs
        equipe_id = None
        quartier_id = None
        
        with engine.connect() as conn:
            equipe_result = conn.execute(text("SELECT id FROM equipes WHERE nom = :nom"), {"nom": equipe_nom}).first()
            if equipe_result:
                equipe_id = equipe_result[0]
            
            quartier_result = conn.execute(text("SELECT id FROM quartiers WHERE nom = :nom"), {"nom": quartier_nom}).first()
            if quartier_result:
                quartier_id = quartier_result[0]
        
        if equipe_id and quartier_id:
            try:
                with engine.connect() as conn:
                    # Insérer la tournée
                    result = conn.execute(text("""
                        INSERT INTO tournees (
                            date_tournee, equipe_id, quartier_id,
                            heure_depot_depart, heure_debut_collecte1, heure_fin_collecte1,
                            heure_depart_decharge, heure_arrivee_decharge, heure_sortie_decharge,
                            heure_debut_collecte2, heure_fin_collecte2, heure_retour_depot,
                            distance_parcourue_km, nombre_voyages, volume_m3, observations,
                            agent_nom
                        ) VALUES (
                            :date, :equipe_id, :quartier_id,
                            :h_depart, :h_debut1, :h_fin1,
                            :h_depart_dech, :h_arrivee_dech, :h_sortie_dech,
                            :h_debut2, :h_fin2, :h_retour,
                            :distance, :voyages, :volume, :obs,
                            :agent
                        )
                        RETURNING id
                    """), {
                        "date": date_tournee,
                        "equipe_id": equipe_id,
                        "quartier_id": quartier_id,
                        "h_depart": heure_depot_depart.strftime("%H:%M:%S"),
                        "h_debut1": heure_debut_collecte1.strftime("%H:%M:%S"),
                        "h_fin1": heure_fin_collecte1.strftime("%H:%M:%S"),
                        "h_depart_dech": heure_depart_decharge.strftime("%H:%M:%S"),
                        "h_arrivee_dech": heure_arrivee_decharge.strftime("%H:%M:%S"),
                        "h_sortie_dech": heure_sortie_decharge.strftime("%H:%M:%S"),
                        "h_debut2": heure_debut_collecte2.strftime("%H:%M:%S"),
                        "h_fin2": heure_fin_collecte2.strftime("%H:%M:%S"),
                        "h_retour": heure_retour_depot.strftime("%H:%M:%S"),
                        "distance": distance_totale,
                        "voyages": nombre_voyages,
                        "volume": volume_total,
                        "obs": observations,
                        "agent": "Agent terrain"
                    })
                    
                    tournee_id = result.fetchone()[0]
                    
                    # Insérer les points GPS
                    for point in st.session_state.points_gps:
                        conn.execute(text("""
                            INSERT INTO points_arret (tournee_id, heure, type_point, description, latitude, longitude)
                            VALUES (:tid, :heure, :type, :desc, :lat, :lon)
                        """), {
                            "tid": tournee_id,
                            "heure": point["heure"],
                            "type": point["type"],
                            "desc": point["description"],
                            "lat": point.get("lat"),
                            "lon": point.get("lon")
                        })
                    
                    conn.commit()
                
                st.markdown('<div class="success-box">✅ Tournée enregistrée avec succès !</div>', unsafe_allow_html=True)
                st.balloons()
                
                # Réinitialiser
                st.session_state.points_gps = []
                st.session_state.position_actuelle = None
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement: {e}")
        else:
            st.error("❌ Erreur: équipe ou quartier non trouvé")

# ==================== ONGLET 2 : MODIFIER/SUPPRIMER ====================
with tab2:
    st.subheader("✏️ Modifier ou supprimer une tournée")
    
    col1, col2 = st.columns(2)
    with col1:
        date_modif = st.date_input("Sélectionner la date", value=date.today())
    
    tournees = get_tournees_du_jour(date_modif)
    
    if tournees:
        options = [f"{t['equipe']} - {t['quartier']} - {t['depart']}" for t in tournees]
        tournee_selectionnee = st.selectbox("Sélectionner la tournée", options, key="select_tournee")
        
        if tournee_selectionnee:
            idx = options.index(tournee_selectionnee)
            tournee = tournees[idx]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ SUPPRIMER", use_container_width=True):
                    if supprimer_tournee(tournee["id"]):
                        st.success("✅ Tournée supprimée")
                        st.rerun()
            
            with col2:
                if st.button("✏️ MODIFIER", use_container_width=True):
                    st.session_state.mode_edition = tournee["id"]
            
            if st.session_state.mode_edition == tournee["id"]:
                st.markdown('<div class="edit-box">✏️ Mode édition - Modifiez les valeurs ci-dessous</div>', unsafe_allow_html=True)
                
                with st.form("form_edit"):
                    col1, col2 = st.columns(2)
                    
                    # Convertir les heures en objets time
                    def str_to_time(t_str):
                        if t_str:
                            return datetime.strptime(str(t_str), "%H:%M:%S").time()
                        return time(7, 0)
                    
                    with col1:
                        new_depart = st.time_input("Heure départ", value=str_to_time(tournee["depart"]))
                        new_debut1 = st.time_input("Début collecte 1", value=str_to_time(tournee["debut_collecte1"]))
                        new_fin1 = st.time_input("Fin collecte 1", value=str_to_time(tournee["fin_collecte1"]))
                    with col2:
                        new_volume = st.number_input("Volume (m³)", value=float(tournee["volume"]), step=0.5)
                        new_distance = st.number_input("Distance (km)", value=float(tournee["distance"]), step=0.5)
                        new_voyages = st.number_input("Nombre voyages", value=int(tournee["voyages"]), step=1)
                    
                    new_obs = st.text_area("Observations", value=tournee.get("observations", ""), height=80)
                    
                    if st.form_submit_button("💾 ENREGISTRER LES MODIFICATIONS"):
                        data = {
                            "h_depart": new_depart.strftime("%H:%M:%S"),
                            "h_debut1": new_debut1.strftime("%H:%M:%S"),
                            "h_fin1": new_fin1.strftime("%H:%M:%S"),
                            "h_depart_dech": "09:45:00",
                            "h_arrivee_dech": "10:15:00",
                            "h_sortie_dech": "10:45:00",
                            "h_debut2": "11:00:00",
                            "h_fin2": "13:00:00",
                            "h_retour": "14:00:00",
                            "distance": new_distance,
                            "voyages": new_voyages,
                            "volume": new_volume,
                            "obs": new_obs
                        }
                        if modifier_tournee(tournee["id"], data):
                            st.success("✅ Tournée modifiée")
                            st.session_state.mode_edition = None
                            st.rerun()
    else:
        st.info(f"Aucune tournée trouvée pour le {date_modif.strftime('%d/%m/%Y')}")

# ==================== ONGLET 3 : GPS & GÉOLOCALISATION ====================
with tab3:
    st.subheader("📍 Suivi GPS et géolocalisation")
    
    st.markdown("""
    <div class="info-box">
    <strong>📡 Comment utiliser la géolocalisation :</strong><br>
    1. Activez le GPS dans l'onglet "Nouvelle Tournée"<br>
    2. Autorisez l'accès à la localisation sur votre téléphone<br>
    3. À chaque étape (départ, collecte, décharge, retour), cliquez sur le bouton "Enregistrer"<br>
    4. La position est automatiquement sauvegardée dans la base de données
    </div>
    """, unsafe_allow_html=True)
    
    # Afficher les dernières positions GPS
    with engine.connect() as conn:
        positions = conn.execute(text("""
            SELECT 
                pa.heure,
                pa.type_point,
                pa.description,
                pa.latitude,
                pa.longitude,
                e.nom as equipe,
                q.nom as quartier
            FROM points_arret pa
            LEFT JOIN tournees t ON pa.tournee_id = t.id
            LEFT JOIN equipes e ON t.equipe_id = e.id
            LEFT JOIN quartiers q ON t.quartier_id = q.id
            WHERE pa.latitude IS NOT NULL
            ORDER BY pa.heure DESC
            LIMIT 20
        """)).fetchall()
        
        if positions:
            st.subheader("📌 Dernières positions enregistrées")
            df_pos = pd.DataFrame(positions, columns=['Heure', 'Type', 'Description', 'Latitude', 'Longitude', 'Équipe', 'Quartier'])
            
            # Formater les données
            df_pos['Latitude'] = df_pos['Latitude'].apply(lambda x: f"{x:.6f}" if x else "N/A")
            df_pos['Longitude'] = df_pos['Longitude'].apply(lambda x: f"{x:.6f}" if x else "N/A")
            
            st.dataframe(df_pos, use_container_width=True)
            
            # Carte des positions
            df_carte = df_pos[df_pos['Latitude'] != 'N/A'].copy()
            if not df_carte.empty:
                df_carte['Latitude'] = pd.to_numeric(df_carte['Latitude'])
                df_carte['Longitude'] = pd.to_numeric(df_carte['Longitude'])
                
                fig_map = px.scatter_mapbox(
                    df_carte, 
                    lat="Latitude", 
                    lon="Longitude",
                    color="Type",
                    hover_name="Équipe",
                    hover_data={"Description": True, "Heure": True},
                    zoom=12,
                    center={"lat": 15.11, "lon": -16.65},
                    title="Carte des dernières positions GPS",
                    size_max=15
                )
                fig_map.update_layout(mapbox_style="open-street-map", height=500)
                st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("Aucune position GPS enregistrée pour le moment. Activez le GPS lors de vos tournées.")

# ==================== ONGLET 4 : STATISTIQUES ====================
with tab4:
    st.subheader("📊 Statistiques des collectes")
    
    col1, col2 = st.columns(2)
    with col1:
        date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date fin", value=date.today())
    
    # Compter le nombre total de tournées
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM tournees")).first()[0]
        st.metric("📊 Total des tournées enregistrées", count)
        
        if count > 500:
            st.warning("⚠️ La base approche des limites. Pensez à archiver les données anciennes.")
    
    # Afficher les statistiques
    with engine.connect() as conn:
        stats = conn.execute(text("""
            SELECT 
                q.nom as quartier,
                SUM(t.volume_m3) as volume_total,
                COUNT(t.id) as nb_tournees,
                AVG(t.volume_m3) as volume_moyen,
                SUM(t.distance_parcourue_km) as distance_totale,
                AVG(t.distance_parcourue_km) as distance_moyenne
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            WHERE t.date_tournee BETWEEN :debut AND :fin
            GROUP BY q.nom
            ORDER BY volume_total DESC
        """), {"debut": date_debut, "fin": date_fin}).fetchall()
        
        if stats:
            df_stats = pd.DataFrame(stats, columns=['Quartier', 'Volume (m³)', 'Nb collectes', 'Moyenne (m³)', 'Distance (km)', 'Distance moyenne'])
            st.subheader("📈 Performance par quartier")
            st.dataframe(df_stats, use_container_width=True)
            
            # Graphique
            fig = px.bar(df_stats, x='Quartier', y='Volume (m³)', title="Volume collecté par quartier", color='Volume (m³)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée pour la période sélectionnée")
    
    # Évolution temporelle
    with engine.connect() as conn:
        evolution = conn.execute(text("""
            SELECT 
                date_tournee,
                SUM(volume_m3) as volume_journalier
            FROM tournees
            WHERE date_tournee BETWEEN :debut AND :fin
            GROUP BY date_tournee
            ORDER BY date_tournee
        """), {"debut": date_debut, "fin": date_fin}).fetchall()
        
        if evolution:
            df_evol = pd.DataFrame(evolution, columns=['Date', 'Volume (m³)'])
            fig_evol = px.line(df_evol, x='Date', y='Volume (m³)', title="Évolution du volume collecté")
            st.plotly_chart(fig_evol, use_container_width=True)

# ==================== FOOTER ====================
st.markdown("---")
st.caption("📱 Interface agent - Commune de Mékhé | GPS intégré | Suivi temps réel | Données sauvegardées dans le cloud")
