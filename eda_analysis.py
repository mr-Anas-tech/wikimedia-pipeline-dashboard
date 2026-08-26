import streamlit as st
import pandas as pd
import plotly.express as px
import toml
import os

# Page Config
st.set_page_config(page_title="Wikimedia Traffic Spikes", page_icon="⚡", layout="wide")

# Cached Data Loader with Fallback Logic
@st.cache_data(ttl=3600)
def load_data():
    try:
        # Live Snowflake Connection
        import snowflake.connector
        
        # Local secrets handle karein
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            secrets = toml.load(secrets_path)["snowflake"]
        else:
            secrets = st.secrets["snowflake"] # Streamlit Cloud secrets

        conn = snowflake.connector.connect(
            user=secrets["user"],
            password=secrets["password"],
            account=secrets["account"],
            warehouse=secrets["warehouse"],
            database=secrets["database"],
            schema=secrets["schema"],
            role=secrets["role"]
        )
        query = "SELECT * FROM WIKIMEDIA_DB.DBT_DEV.FCT_HOURLY_TRAFFIC_SPIKES;"
        df = pd.read_sql(query, conn)
        conn.close()
        data_source = "Snowflake DB (Live)"
    except Exception:
        # Fallback to local Parquet backup
        df = pd.read_parquet("data/hourly_spikes_backup.parquet")
        data_source = "Parquet Backup (Offline)"
    
    # Feature Engineering
    df['EVENT_HOUR'] = pd.to_datetime(df['EVENT_HOUR'])
    df['HOUR_OF_DAY'] = df['EVENT_HOUR'].dt.hour
    df['EDITS_PER_CONTRIBUTOR'] = df['EDIT_VOLUME'] / df['ACTIVE_CONTRIBUTORS']
    return df, data_source

df, source = load_data()

# Header & Sidebar Status
st.title("⚡ Wikimedia Real-Time Traffic Spike Monitor")
st.sidebar.caption(f"Connected Source: **{source}**")

# Sidebar Filter
st.sidebar.header("Filters")
selected_types = st.sidebar.multiselect("Edit Types:", options=df['EDIT_TYPE'].unique(), default=df['EDIT_TYPE'].unique())
filtered_df = df[df['EDIT_TYPE'].isin(selected_types)]

# KPI Row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Events Tracked", f"{len(filtered_df):,}")
c2.metric("Total Edit Volume", f"{filtered_df['EDIT_VOLUME'].sum():,}")
c3.metric("Max Volume in Single Hour", f"{filtered_df['EDIT_VOLUME'].max():,}")
c4.metric("Avg Contributors / Event", f"{filtered_df['ACTIVE_CONTRIBUTORS'].mean():.1f}")

st.divider()

# Grid 1: Peak Hours & Action Ratios
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Peak Traffic Hours")
    hourly_trend = filtered_df.groupby('HOUR_OF_DAY')['EDIT_VOLUME'].sum().reset_index()
    fig1 = px.line(hourly_trend, x='HOUR_OF_DAY', y='EDIT_VOLUME', markers=True, title="Edit Volume by Hour of Day")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("2. Action Breakdown")
    edit_type_df = filtered_df.groupby('EDIT_TYPE')['EDIT_VOLUME'].sum().reset_index()
    fig2 = px.pie(edit_type_df, values='EDIT_VOLUME', names='EDIT_TYPE', hole=0.4, title="Edit Type Distribution")
    st.plotly_chart(fig2, use_container_width=True)

# Grid 2: Top Wikis & Automation Detection
col3, col4 = st.columns(2)
with col3:
    st.subheader("3. Top 10 Active Wikis")
    top_wikis = filtered_df.groupby('WIKI_NAME')['EDIT_VOLUME'].sum().nlargest(15).reset_index()
    fig3 = px.bar(top_wikis, x='EDIT_VOLUME', y='WIKI_NAME', orientation='h', title="Highest Traffic Wiki Domains")
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    st.subheader("4. Bot / Automation Spike Alerts")
    bot_df = filtered_df.sort_values(by='EDITS_PER_CONTRIBUTOR', ascending=False).head(10)
    st.caption("Top 10 Spikes by Edit Volume vs Contributor Ratio")
    st.dataframe(bot_df[['EVENT_HOUR','HOUR_OF_DAY', 'WIKI_NAME', 'EDIT_TYPE', 'EDIT_VOLUME', 'ACTIVE_CONTRIBUTORS', 'EDITS_PER_CONTRIBUTOR']], use_container_width=True)