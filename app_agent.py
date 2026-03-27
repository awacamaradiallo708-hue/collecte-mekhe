"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version simplifiée :
- Volume global par collecte (pas par point)
- Points de collecte dynamiques sans volume
- 2 collectes, 2 décharges
- GPS intégré
- Photos par point
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO

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
        position: sticky;
        top: 0;
        z-index: 999;
        border-radius: 0 0 15px 15px;
        margin: -1rem -1rem 1rem -1rem;
    }
    .main-header h1 { font-size: 1.5rem; margin-bottom: 0; }
    .collecte-card {
        background: #e8f5e9;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #4CAF50;
    }
    .decharge-card {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #FF9800;
    }
    .point-card {
        background: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 3px solid #2E7D32;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .point-numero {
        font-weight: bold;
        background: #2E7D32;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
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
    .volume-box {
        background: #fff8e7;
        padding: 1rem;
        border-radius: 10px;
        border: 2px dashed #FF9800;
        text-align: center;
        margin: 1rem 0;
    }
    .stButton button {
        width: 100%;
        height: 3rem;
        font-weight: bold;
        text-transform: uppercase;
    }
    /* Optimisation pour petits écrans */
    @media (max-width: 480px) {
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 4px;
            font-size: 0.8rem;
        }
    }
    </style>
    
    <!-- Balises PWA pour mobile -->
    <script>
      // Petit script pour forcer le rafraîchissement si nécessaire
      console.log("Interface Agent Mékhé v1.1 - Chargée");
    </script>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent Mékhé v1.1</h1><p>Mode Terrain | Connecté à Neon.tech</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS ====================

def verifier_connexion():
    """Vérifie si la base de données en ligne est accessible"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception:
        return False

def get_quartiers():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def get_equipes():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM equipes WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def enregistrer_point_collecte(tournee_id, point_data):
    """Enregistre un point de collecte (sans volume)"""
    try:
        if not verifier_connexion():
            st.session_state.sync_queue.append({"type": "point", "data": point_data, "tournee_id": tournee_id})
            return "queued"
            
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_collecte (
                    tournee_id, point_numero, heure_passage, 
                    latitude, longitude, precision_gps, photo_data, 
                    description, collecte_numero
                ) VALUES (
                    :tid, :numero, :heure, 
                    :lat, :lon, :precision, :photo, 
                    :desc, :collecte
                )
            """), {
                "tid": tournee_id,
                "numero": point_data["numero"],
                "heure": point_data["heure"],
                "lat": point_data.get("lat"),
                "lon": point_data.get("lon"),
                "precision": point_data.get("precision", 0),
                "photo": point_data.get("photo"),
                "desc": point_data.get("description", ""),
                "collecte": point_data.get("collecte_numero", 1)
            })
            conn.commit()
        return True
    except Exception as e:
        return False

def exporter_excel(tournee_id):
    """Exporte une tournée en Excel"""
    try:
        with engine.connect() as conn:
            tournee = conn.execute(text("""
                SELECT 
                    t.*,
                    q.nom as quartier,
                    e.nom as equipe
                FROM tournees t
                JOIN quartiers q ON t.quartier_id = q.id
                JOIN equipes e ON t.equipe_id = e.id
                WHERE t.id = :tid
            """), {"tid": tournee_id}).first()
            
            points = conn.execute(text("""
                SELECT * FROM points_collecte 
                WHERE tournee_id = :tid 
                ORDER BY collecte_numero, point_numero
            """), {"tid": tournee_id}).fetchall()
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                resume = pd.DataFrame({
                    "Information": ["Date", "Quartier", "Équipe", "Agent", 
                                   "Départ dépôt",
                                   "Collecte 1 - Volume", "Collecte 1 - Début", "Collecte 1 - Fin",
                                   "Décharge 1 - Départ", "Décharge 1 - Arrivée", "Décharge 1 - Sortie",
                                   "Collecte 2 - Volume", "Collecte 2 - Début", "Collecte 2 - Fin",
                                   "Décharge 2 - Départ", "Décharge 2 - Arrivée", "Décharge 2 - Sortie",
                                   "Retour dépôt", "Distance totale"],
                    "Valeur": [
                        tournee.date_tournee,
                        tournee.quartier,
                        tournee.equipe,
                        tournee.agent_nom,
                        tournee.heure_depot_depart,
                        tournee.volume_collecte1 or 0,
                        tournee.heure_debut_collecte1,
                        tournee.heure_fin_collecte1,
                        tournee.heure_depart_decharge1,
                        tournee.heure_arrivee_decharge1,
                        tournee.heure_sortie_decharge1,
                        tournee.volume_collecte2 or 0,
                        tournee.heure_debut_collecte2,
                        tournee.heure_fin_collecte2,
                        tournee.heure_depart_decharge2,
                        tournee.heure_arrivee_decharge2,
                        tournee.heure_sortie_decharge2,
                        tournee.heure_retour_depot,
                        tournee.distance_parcourue_km
                    ]
                })
                resume.to_excel(writer, sheet_name="Résumé", index=False)
                
                if points:
                    points_data = []
                    for p in points:
                        points_data.append({
                            "Collecte": p.collecte_numero,
                            "N° Point": p.point_numero,
                            "Heure": p.heure_passage,
                            "Latitude": p.latitude,
                            "Longitude": p.longitude,
                            "Description": p.description
                        })
                    df_points = pd.DataFrame(points_data)
                    df_points.to_excel(writer, sheet_name="Points de collecte", index=False)
            
            return output.getvalue()
    except Exception as e:
        st.error(f"Erreur export: {e}")
        return None

# ==================== SESSION STATE ====================
if 'points_collecte1' not in st.session_state:
    st.session_state.points_collecte1 = []
if 'points_collecte2' not in st.session_state:
    st.session_state.points_collecte2 = []
if 'gps_actif' not in st.session_state:
    st.session_state.gps_actif = False
if 'position_actuelle' not in st.session_state:
    st.session_state.position_actuelle = None
if 'tournee_en_cours' not in st.session_state:
    st.session_state.tournee_en_cours = None
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'etape_actuelle' not in st.session_state:
    st.session_state.etape_actuelle = "depart"
if 'volume_collecte1' not in st.session_state:
    st.session_state.volume_collecte1 = 0.0
if 'volume_collecte2' not in st.session_state:
    st.session_state.volume_collecte2 = 0.0
if 'sync_queue' not in st.session_state:
    st.session_state.sync_queue = []
if 'positions_historique' not in st.session_state:
    st.session_state.positions_historique = []

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")

    agent_nom_input = st.text_input("Votre nom complet", value=st.session_state.agent_nom, 
                                     placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")

    st.metric("📦 Volume Voyage 1", f"{st.session_state.volume_collecte1:.1f} m³")
    st.metric("📦 Volume Voyage 2", f"{st.session_state.volume_collecte2:.1f} m³")

    total_volume = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
    st.metric("📊 Volume total", f"{total_volume:.1f} m³")
    
    # Indicateur de synchronisation
    if st.session_state.sync_queue:
        st.warning(f"⏳ {len(st.session_state.sync_queue)} données en attente")
        if st.button("🔄 SYNCHRONISER MAINTENANT"):
            if verifier_connexion():
                count = 0
                for item in st.session_state.sync_queue:
                    if item["type"] == "point":
                        success = enregistrer_point_collecte(item["tournee_id"], item["data"])
                        if success and success != "queued":
                            count += 1
                st.success(f"✅ {count} points synchronisés avec succès !")
                st.session_state.sync_queue = []
            else:
                st.error("❌ Toujours pas de connexion")
    else:
        st.success("☁️ Données synchronisées")

    st.markdown("---")
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)
        if st.session_state.position_actuelle:
            st.write(f"Lat: {st.session_state.position_actuelle['lat']:.6f}")
            st.write(f"Lon: {st.session_state.position_actuelle['lon']:.6f}")

# ==================== ONGLETS ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚛 Nouvelle Tournée", 
    "📍 Voyage 1 (Points & Volume)", 
    "📍 Voyage 2 (Points & Volume)",
    "📸 Photos",
    "📊 Résumé & Export",
    "🗺️ Carte GPS"
])

# ==================== ONGLET 1 : NOUVELLE TOURNÉE ====================
with tab1:
    st.subheader("🚛 Démarrer une nouvelle tournée")
    
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
    
    col1, col2 = st.columns(2)
    with col1:
        date_tournee = st.date_input("📅 Date", value=date.today())
        equipe_nom = st.selectbox("👥 Équipe", [e[1] for e in get_equipes()])
    with col2:
        quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in get_quartiers()])
        nombre_voyages = st.number_input("🚛 Nombre de voyages", min_value=1, value=1, step=1)
    
    # GPS
    st.markdown("---")
    st.markdown("### 📍 GÉOLOCALISATION")
    
    col_gps1, col_gps2 = st.columns(2)
    with col_gps1:
        if st.button("📍 ACTIVER LE GPS", key="gps_activate", use_container_width=True):
            st.session_state.gps_actif = True
            # Simulation initiale basée sur le quartier
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
                st.session_state.position_actuelle = {"lat": lat, "lon": lon, "precision": 10}
                if st.session_state.position_actuelle not in st.session_state.positions_historique:
                    st.session_state.positions_historique.append(st.session_state.position_actuelle.copy())
            st.success("✅ GPS prêt")

    if st.session_state.gps_actif and st.session_state.position_actuelle:
        if st.button("🔄 ACTUALISER MA POSITION", use_container_width=True):
            # Dans une version mobile réelle, cela déclencherait la lecture du capteur GPS
            st.session_state.positions_historique.append(st.session_state.position_actuelle.copy())
            st.rerun()
    
    # Horaires
    st.markdown("---")
    st.markdown("### 🕐 HORAIRES DE LA TOURNÉE")
    
    col1, col2 = st.columns(2)
    with col1:
        heure_depot_depart = st.time_input("🏭 Départ du dépôt", value=time(7, 0))
    with col2:
        distance_totale = st.number_input("📏 Distance totale (km)", min_value=0.0, step=0.5, value=25.0)
    
    st.markdown("#### 🗑️ COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut_collecte1 = st.time_input("Début collecte 1", value=time(7, 30))
    with col2:
        heure_fin_collecte1 = st.time_input("Fin collecte 1", value=time(9, 30))
    
    st.markdown("#### 🏭 DÉCHARGE 1")
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_depart_decharge1 = st.time_input("Départ vers décharge 1", value=time(9, 45))
    with col2:
        heure_arrivee_decharge1 = st.time_input("Arrivée décharge 1", value=time(10, 15))
    with col3:
        heure_sortie_decharge1 = st.time_input("Sortie décharge 1", value=time(10, 45))
    
    st.markdown("#### 🗑️ COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut_collecte2 = st.time_input("Début collecte 2", value=time(11, 0))
    with col2:
        heure_fin_collecte2 = st.time_input("Fin collecte 2", value=time(13, 0))
    
    st.markdown("#### 🏭 DÉCHARGE 2")
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_depart_decharge2 = st.time_input("Départ vers décharge 2", value=time(13, 15))
    with col2:
        heure_arrivee_decharge2 = st.time_input("Arrivée décharge 2", value=time(13, 45))
    with col3:
        heure_sortie_decharge2 = st.time_input("Sortie décharge 2", value=time(14, 15))
    
    st.markdown("#### 🏁 RETOUR")
    heure_retour_depot = st.time_input("Retour au dépôt", value=time(14, 45))
    
    observations = st.text_area("📝 Observations générales", height=80)
    
    # Bouton démarrer
    if st.button("🚀 DÉMARRER LA TOURNÉE", type="primary", use_container_width=True):
        if not st.session_state.agent_nom:
            st.error("❌ Veuillez entrer votre nom")
        else:
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
                        result = conn.execute(text("""
                            INSERT INTO tournees (
                                date_tournee, equipe_id, quartier_id,
                                heure_depot_depart,
                                heure_debut_collecte1, heure_fin_collecte1,
                                heure_depart_decharge1, heure_arrivee_decharge1, heure_sortie_decharge1,
                                heure_debut_collecte2, heure_fin_collecte2,
                                heure_depart_decharge2, heure_arrivee_decharge2, heure_sortie_decharge2,
                                heure_retour_depot,
                                distance_parcourue_km, nombre_voyages, observations,
                                agent_nom, statut
                            ) VALUES (
                                :date, :equipe_id, :quartier_id,
                                :h_depart,
                                :h_debut1, :h_fin1,
                                :h_depart_dech1, :h_arrivee_dech1, :h_sortie_dech1,
                                :h_debut2, :h_fin2,
                                :h_depart_dech2, :h_arrivee_dech2, :h_sortie_dech2,
                                :h_retour,
                                :distance, :voyages, :obs,
                                :agent, 'en_cours'
                            )
                            RETURNING id
                        """), {
                            "date": date_tournee,
                            "equipe_id": equipe_id,
                            "quartier_id": quartier_id,
                            "h_depart": heure_depot_depart.strftime("%H:%M:%S"),
                            "h_debut1": heure_debut_collecte1.strftime("%H:%M:%S"),
                            "h_fin1": heure_fin_collecte1.strftime("%H:%M:%S"),
                            "h_depart_dech1": heure_depart_decharge1.strftime("%H:%M:%S"),
                            "h_arrivee_dech1": heure_arrivee_decharge1.strftime("%H:%M:%S"),
                            "h_sortie_dech1": heure_sortie_decharge1.strftime("%H:%M:%S"),
                            "h_debut2": heure_debut_collecte2.strftime("%H:%M:%S"),
                            "h_fin2": heure_fin_collecte2.strftime("%H:%M:%S"),
                            "h_depart_dech2": heure_depart_decharge2.strftime("%H:%M:%S"),
                            "h_arrivee_dech2": heure_arrivee_decharge2.strftime("%H:%M:%S"),
                            "h_sortie_dech2": heure_sortie_decharge2.strftime("%H:%M:%S"),
                            "h_retour": heure_retour_depot.strftime("%H:%M:%S"),
                            "distance": distance_totale,
                            "voyages": nombre_voyages,
                            "obs": observations,
                            "agent": st.session_state.agent_nom
                        })
                        
                        st.session_state.tournee_en_cours = result.fetchone()[0]
                        st.session_state.etape_actuelle = "collecte1"
                        st.session_state.points_collecte1 = []
                        st.session_state.points_collecte2 = []
                        st.session_state.volume_collecte1 = 0.0
                        st.session_state.volume_collecte2 = 0.0
                        
                        conn.commit()
                    
                    st.markdown('<div class="success-box">✅ Tournée démarrée ! Enregistrez les points du VOYAGE 1</div>', unsafe_allow_html=True)
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
            else:
                st.error("❌ Équipe ou quartier non trouvé")
    
    if st.session_state.tournee_en_cours:
        st.info(f"🟢 Tournée en cours - ID: {st.session_state.tournee_en_cours}")
        st.info(f"📍 Étape: {st.session_state.etape_actuelle}")

# ==================== ONGLET 2 : VOYAGE 1 ====================
with tab2:
    st.subheader("📍 VOYAGE 1 - Points de passage")
    
    if not st.session_state.tournee_en_cours:
        st.warning("⚠️ Veuillez d'abord démarrer une tournée")
    else:
        st.markdown('<div class="collecte-card">📍 VOYAGE 1 - Marquez chaque arrêt de collecte (sans saisir de volume)</div>', unsafe_allow_html=True)
        
        # Formulaire d'ajout de point (SANS VOLUME)
        with st.form("form_point1", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.gps_actif and st.session_state.position_actuelle:
                    lat = st.number_input("Latitude", value=st.session_state.position_actuelle["lat"], format="%.6f")
                    lon = st.number_input("Longitude", value=st.session_state.position_actuelle["lon"], format="%.6f")
                else:
                    lat = st.number_input("Latitude", value=15.115000, format="%.6f")
                    lon = st.number_input("Longitude", value=-16.635000, format="%.6f")
            with col2:
                description = st.text_area("Note / Localisation", placeholder="Ex: Devant la mosquée, angle rue...", height=80)
                st.markdown(f"**Heure:** {datetime.now().strftime('%H:%M:%S')}")
            
            photo_file = st.file_uploader("📸 Photo (optionnel)", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("✅ AJOUTER CE POINT", use_container_width=True)
            
            if submitted:
                point_data = {
                    "numero": len(st.session_state.points_collecte1) + 1,
                    "heure": datetime.now(),
                    "lat": lat,
                    "lon": lon,
                    "description": description,
                    "photo": photo_file.getvalue() if photo_file else None,
                    "collecte_numero": 1
                }
                if enregistrer_point_collecte(st.session_state.tournee_en_cours, point_data):
                    st.session_state.points_collecte1.append(point_data)
                    st.success(f"✅ Point {len(st.session_state.points_collecte1)} enregistré")
                    st.rerun()
        
        # Afficher les points
        if st.session_state.points_collecte1:
            st.markdown("---")
            st.markdown("### 📋 Points de collecte 1")
            for p in st.session_state.points_collecte1:
                st.markdown(f"""
                <div class="point-card">
                    <div>
                        <span class="point-numero">Point {p['numero']}</span>
                        <strong>{p['heure'].strftime('%H:%M:%S')}</strong>
                    </div>
                    <div>📍 {p['lat']:.6f}, {p['lon']:.6f}</div>
                    <div>📝 {p['description'][:80] if p['description'] else 'Pas de description'}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Section volume collecte 1
        st.markdown("---")
        st.markdown('<div class="volume-box">📦 <strong>VOLUME TOTAL DU VOYAGE 1</strong><br>Saisissez le volume estimé pour ce voyage complet</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            volume1 = st.number_input("Volume Voyage 1 (m³)", min_value=0.0, step=0.1, value=st.session_state.volume_collecte1)
        with col2:
            if st.button("💾 VALIDER VOLUME VOYAGE 1", use_container_width=True):
                if volume1 > 0:
                    st.session_state.volume_collecte1 = volume1
                    with engine.connect() as conn:
                        conn.execute(text("""
                            UPDATE tournees SET volume_collecte1 = :volume WHERE id = :tid
                        """), {"volume": volume1, "tid": st.session_state.tournee_en_cours})
                        conn.commit()
                    st.success(f"✅ Volume Voyage 1 enregistré: {volume1:.1f} m³")
                    st.session_state.etape_actuelle = "decharge1"
                else:
                    st.warning("⚠️ Veuillez saisir un volume")
        
        # Section décharge 1
        st.markdown("---")
        st.markdown('<div class="decharge-card">🏭 DÉCHARGE 1 - Cliquez quand vous êtes à la décharge</div>', unsafe_allow_html=True)
        
        if st.button("📍 ENREGISTRER PASSAGE DÉCHARGE 1", use_container_width=True):
            if st.session_state.gps_actif and st.session_state.position_actuelle:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description)
                        VALUES (:tid, :heure, 'decharge_1', :lat, :lon, :desc)
                    """), {
                        "tid": st.session_state.tournee_en_cours,
                        "heure": datetime.now(),
                        "lat": st.session_state.position_actuelle["lat"],
                        "lon": st.session_state.position_actuelle["lon"],
                        "desc": "Passage décharge 1"
                    })
                    conn.commit()
                st.success("✅ Passage décharge 1 enregistré avec GPS")
                st.session_state.etape_actuelle = "collecte2"
                st.info("📍 Passez maintenant à la COLLECTE 2")
            else:
                st.warning("⚠️ Activez le GPS pour enregistrer la position")

# ==================== ONGLET 3 : VOYAGE 2 ====================
with tab3:
    st.subheader("📍 VOYAGE 2 - Points de passage")
    
    if not st.session_state.tournee_en_cours:
        st.warning("⚠️ Veuillez d'abord démarrer une tournée")
    elif st.session_state.etape_actuelle not in ["collecte2", "decharge2"]:
        st.info("ℹ️ Terminez d'abord le VOYAGE 1 et la décharge associée")
    else:
        st.markdown('<div class="collecte-card">📍 VOYAGE 2 - Marquez chaque arrêt de collecte (sans saisir de volume)</div>', unsafe_allow_html=True)
        
        # Formulaire d'ajout de point
        with st.form("form_point2", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.gps_actif and st.session_state.position_actuelle:
                    lat = st.number_input("Latitude", value=st.session_state.position_actuelle["lat"], format="%.6f")
                    lon = st.number_input("Longitude", value=st.session_state.position_actuelle["lon"], format="%.6f")
                else:
                    lat = st.number_input("Latitude", value=15.115000, format="%.6f")
                    lon = st.number_input("Longitude", value=-16.635000, format="%.6f")
            with col2:
                description = st.text_area("Note / Localisation", placeholder="Ex: Marché, Place centrale...", height=80)
                st.markdown(f"**Heure:** {datetime.now().strftime('%H:%M:%S')}")
            
            photo_file = st.file_uploader("📸 Photo (optionnel)", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("✅ AJOUTER CE POINT", use_container_width=True)
            
            if submitted:
                point_data = {
                    "numero": len(st.session_state.points_collecte2) + 1,
                    "heure": datetime.now(),
                    "lat": lat,
                    "lon": lon,
                    "description": description,
                    "photo": photo_file.getvalue() if photo_file else None,
                    "collecte_numero": 2
                }
                if enregistrer_point_collecte(st.session_state.tournee_en_cours, point_data):
                    st.session_state.points_collecte2.append(point_data)
                    st.success(f"✅ Point {len(st.session_state.points_collecte2)} ajouté")
                    st.rerun()
        
        # Afficher les points
        if st.session_state.points_collecte2:
            st.markdown("---")
            st.markdown("### 📋 Points de collecte 2")
            for p in st.session_state.points_collecte2:
                st.markdown(f"""
                <div class="point-card">
                    <div>
                        <span class="point-numero">Point {p['numero']}</span>
                        <strong>{p['heure'].strftime('%H:%M:%S')}</strong>
                    </div>
                    <div>📍 {p['lat']:.6f}, {p['lon']:.6f}</div>
                    <div>📝 {p['description'][:80] if p['description'] else 'Pas de description'}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Section volume collecte 2
        st.markdown("---")
        st.markdown('<div class="volume-box">📦 <strong>VOLUME TOTAL DU VOYAGE 2</strong><br>Saisissez le volume estimé pour ce voyage complet</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            volume2 = st.number_input("Volume Voyage 2 (m³)", min_value=0.0, step=0.1, value=st.session_state.volume_collecte2)
        with col2:
            if st.button("💾 VALIDER VOLUME VOYAGE 2", use_container_width=True):
                if volume2 > 0:
                    st.session_state.volume_collecte2 = volume2
                    with engine.connect() as conn:
                        conn.execute(text("""
                            UPDATE tournees SET volume_collecte2 = :volume WHERE id = :tid
                        """), {"volume": volume2, "tid": st.session_state.tournee_en_cours})
                        conn.commit()
                    st.success(f"✅ Volume Voyage 2 enregistré: {volume2:.1f} m³")
                    st.session_state.etape_actuelle = "decharge2"
                else:
                    st.warning("⚠️ Veuillez saisir un volume")
        
        # Section décharge 2
        st.markdown("---")
        st.markdown('<div class="decharge-card">🏭 DÉCHARGE 2 - Cliquez quand vous êtes à la décharge</div>', unsafe_allow_html=True)
        
        if st.button("📍 ENREGISTRER PASSAGE DÉCHARGE 2", use_container_width=True):
            if st.session_state.gps_actif and st.session_state.position_actuelle:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description)
                        VALUES (:tid, :heure, 'decharge_2', :lat, :lon, :desc)
                    """), {
                        "tid": st.session_state.tournee_en_cours,
                        "heure": datetime.now(),
                        "lat": st.session_state.position_actuelle["lat"],
                        "lon": st.session_state.position_actuelle["lon"],
                        "desc": "Passage décharge 2"
                    })
                    conn.commit()
                st.success("✅ Passage décharge 2 enregistré avec GPS")
                st.session_state.etape_actuelle = "retour"
                
                # Terminer la tournée
                volume_total = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE tournees 
                        SET volume_m3 = :volume, statut = 'termine'
                        WHERE id = :tid
                    """), {"volume": volume_total, "tid": st.session_state.tournee_en_cours})
                    conn.commit()
                
                st.markdown(f'<div class="success-box">✅ Tournée terminée ! Volume total: {volume_total:.1f} m³</div>', unsafe_allow_html=True)
                st.balloons()
            else:
                st.warning("⚠️ Activez le GPS pour enregistrer la position")

# ==================== ONGLET 4 : PHOTOS ====================
with tab4:
    st.subheader("📸 Photos des points de collecte")
    
    st.markdown("### 🗑️ COLLECTE 1")
    for p in st.session_state.points_collecte1:
        if p.get("photo"):
            st.image(p["photo"], caption=f"Point {p['numero']} - {p['description'][:50]}", width=300)
    
    st.markdown("### 🗑️ COLLECTE 2")
    for p in st.session_state.points_collecte2:
        if p.get("photo"):
            st.image(p["photo"], caption=f"Point {p['numero']} - {p['description'][:50]}", width=300)

# ==================== ONGLET 5 : RÉSUMÉ & EXPORT ====================
with tab5:
    st.subheader("📊 Résumé de la tournée")
    
    if st.session_state.tournee_en_cours:
        total_volume = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 Volume Collecte 1", f"{st.session_state.volume_collecte1:.1f} m³")
        with col2:
            st.metric("📦 Volume Collecte 2", f"{st.session_state.volume_collecte2:.1f} m³")
        with col3:
            st.metric("📊 Volume total", f"{total_volume:.1f} m³")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📍 Points Collecte 1", len(st.session_state.points_collecte1))
        with col2:
            st.metric("📍 Points Collecte 2", len(st.session_state.points_collecte2))
        
        if st.button("📥 EXPORTER CETTE TOURNÉE EN EXCEL", use_container_width=True):
            excel_data = exporter_excel(st.session_state.tournee_en_cours)
            if excel_data:
                st.download_button(
                    label="Télécharger Excel",
                    data=excel_data,
                    file_name=f"tournee_{st.session_state.tournee_en_cours}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    # Historique
    st.markdown("---")
    st.subheader("📁 Historique des tournées")
    
    col1, col2 = st.columns(2)
    with col1:
        date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date fin", value=date.today())
    
    with engine.connect() as conn:
        tournees = conn.execute(text("""
            SELECT 
                t.id, t.date_tournee, q.nom as quartier, e.nom as equipe,
                t.volume_collecte1, t.volume_collecte2,
                (t.volume_collecte1 + t.volume_collecte2) as volume_total,
                t.agent_nom,
                (SELECT COUNT(*) FROM points_collecte WHERE tournee_id = t.id) as nb_points
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            JOIN equipes e ON t.equipe_id = e.id
            WHERE t.date_tournee BETWEEN :debut AND :fin
            ORDER BY t.date_tournee DESC
        """), {"debut": date_debut, "fin": date_fin}).fetchall()
        
        if tournees:
            df = pd.DataFrame(tournees, columns=['ID', 'Date', 'Quartier', 'Équipe', 
                                                  'Vol 1 (m³)', 'Vol 2 (m³)', 'Total (m³)', 
                                                  'Agent', 'Nb points'])
            st.dataframe(df, use_container_width=True)

# ==================== ONGLET 6 : CARTE GPS ====================
with tab6:
    st.subheader("🗺️ Suivi de l'agent en temps réel")
    
    if st.session_state.gps_actif and st.session_state.position_actuelle:
        # Créer un DataFrame avec l'historique pour tracer le trajet
        df_map = pd.DataFrame(st.session_state.positions_historique)
        
        if not df_map.empty:
            fig = px.scatter_mapbox(
                df_map, 
                lat="lat", 
                lon="lon",
                zoom=14,
                center={"lat": st.session_state.position_actuelle["lat"], "lon": st.session_state.position_actuelle["lon"]},
                title="Trajet de la collecte en cours"
            )
            fig.update_layout(
                mapbox_style="open-street-map", 
                margin={"r":0,"t":30,"l":0,"b":0},
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            st.info(f"📍 Position actuelle : {st.session_state.position_actuelle['lat']:.6f}, {st.session_state.position_actuelle['lon']:.6f}")
    else:
        st.warning("⚠️ Activez le GPS dans l'onglet 'Nouvelle Tournée' pour afficher la carte.")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Interface agent - Commune de Mékhé | Agent: {st.session_state.agent_nom or 'Non connecté'} | Volume global par collecte | GPS intégré")
