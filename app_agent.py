import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text
import os

st.set_page_config(page_title="Agent Collecte - Mékhé", page_icon="🗑️", layout="centered")

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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé</p></div>', unsafe_allow_html=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL)

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        st.error(f"Erreur: {e}")
        return False

if not test_connection():
    st.stop()

def get_quartiers():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT nom FROM quartiers ORDER BY nom"))
        return [r[0] for r in result]

def get_equipes():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT nom FROM equipes ORDER BY nom"))
        return [r[0] for r in result]

with st.form("form_collecte", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        date_collecte = st.date_input("📅 Date", value=date.today())
        quartier = st.selectbox("📍 Quartier", get_quartiers())
    
    with col2:
        equipe = st.selectbox("👥 Équipe", get_equipes())
        tournee = st.selectbox("🕐 Tournée", ["Matin", "Après-midi", "Soir"])
    
    volume_m3 = st.number_input("📦 Volume (m³)", min_value=0.0, step=1.0, value=0.0)
    observations = st.text_area("📝 Observations")
    agent_nom = st.text_input("👤 Votre nom")
    
    submitted = st.form_submit_button("💾 ENREGISTRER", use_container_width=True)
    
    if submitted and volume_m3 > 0:
        with engine.connect() as conn:
            quartier_id = conn.execute(text("SELECT id FROM quartiers WHERE nom = :nom"), {"nom": quartier}).first()[0]
            equipe_id = conn.execute(text("SELECT id FROM equipes WHERE nom = :nom"), {"nom": equipe}).first()[0]
            
            conn.execute(text("""
                INSERT INTO collectes (date_collecte, quartier_id, equipe_id, volume_m3, tournee, observations, agent_nom)
                VALUES (:date, :qid, :eid, :volume, :tournee, :obs, :agent)
            """), {
                "date": date_collecte,
                "qid": quartier_id,
                "eid": equipe_id,
                "volume": volume_m3,
                "tournee": tournee,
                "obs": observations,
                "agent": agent_nom or "Agent"
            })
            conn.commit()
        
        st.success(f"✅ {volume_m3:.1f} m³ enregistrés pour {quartier}")
        st.balloons()
    elif submitted:
        st.warning("⚠️ Veuillez saisir un volume")

st.markdown("---")
st.subheader("📋 Dernières collectes")

with engine.connect() as conn:
    dernieres = conn.execute(text("""
        SELECT c.date_collecte, q.nom, c.volume_m3, c.agent_nom
        FROM collectes c
        JOIN quartiers q ON c.quartier_id = q.id
        ORDER BY c.created_at DESC LIMIT 10
    """)).fetchall()

if dernieres:
    df = pd.DataFrame(dernieres, columns=['Date', 'Quartier', 'Volume (m³)', 'Agent'])
    df['Volume (m³)'] = df['Volume (m³)'].apply(lambda x: f"{x:.1f}")
    st.dataframe(df, use_container_width=True)

st.caption("📱 Interface agent - Commune de Mékhé")
