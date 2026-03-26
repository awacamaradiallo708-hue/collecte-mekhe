import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy import create_engine, text
import os

st.set_page_config(page_title="Dashboard Mékhé", page_icon="🗑️", layout="wide")

st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Dashboard Collecte Déchets</h1><p>Commune de Mékhé</p></div>', unsafe_allow_html=True)

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

@st.cache_data(ttl=60)
def load_data():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT c.date_collecte, c.volume_m3, q.nom as quartier, 
                   q.latitude, q.longitude, q.population, e.nom as equipe, c.tournee
            FROM collectes c
            JOIN quartiers q ON c.quartier_id = q.id
            JOIN equipes e ON c.equipe_id = e.id
            ORDER BY c.date_collecte
        """)).fetchall()
        
        df = pd.DataFrame(result, columns=['date', 'volume_m3', 'quartier', 'latitude', 
                                           'longitude', 'population', 'equipe', 'tournee'])
        df['date'] = pd.to_datetime(df['date'])
        return df

df = load_data()

if df.empty:
    st.info("Aucune donnée pour le moment. Commencez par saisir des collectes !")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Volume total", f"{df['volume_m3'].sum():.1f} m³")
with col2:
    st.metric("📋 Collectes", len(df))
with col3:
    st.metric("📅 Jours", df['date'].nunique())
with col4:
    max_q = df.groupby('quartier')['volume_m3'].sum().idxmax()
    st.metric("🏆 Quartier max", max_q)

tab1, tab2 = st.tabs(["📊 Par quartier", "🗺️ Carte"])

with tab1:
    totals = df.groupby('quartier')['volume_m3'].sum().sort_values()
    fig = px.bar(x=totals.values, y=totals.index, orientation='h', text=totals.values)
    fig.update_traces(texttemplate='%{text:.1f} m³')
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    totals_map = df.groupby('quartier')['volume_m3'].sum().to_dict()
    coords = df[['quartier', 'latitude', 'longitude']].drop_duplicates()
    
    map_data = []
    for _, row in coords.iterrows():
        volume = totals_map.get(row['quartier'], 0)
        taille = max(15, min(70, volume / 3)) if volume > 0 else 10
        map_data.append({"lat": row['latitude'], "lon": row['longitude'], 
                         "quartier": row['quartier'], "volume": volume, "taille": taille})
    
    map_df = pd.DataFrame(map_data)
    fig_map = px.scatter_mapbox(map_df, lat="lat", lon="lon", size="taille", color="volume",
                                text="quartier", size_max=70, zoom=12,
                                center={"lat": 15.11, "lon": -16.65})
    fig_map.update_layout(mapbox_style="open-street-map", height=500)
    st.plotly_chart(fig_map, use_container_width=True)

st.caption(f"📊 Données du {df['date'].min().strftime('%d/%m/%Y')} au {df['date'].max().strftime('%d/%m/%Y')}")
