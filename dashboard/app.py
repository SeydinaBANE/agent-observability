import os

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API_URL = os.getenv("AGENT_OBS_URL", "http://localhost:8000")
API_KEY = os.getenv("AGENT_OBS_API_KEY", "demo-key-local-dev")
TOKEN = os.getenv("AGENT_OBS_TOKEN", "")


def api_headers():
    if TOKEN:
        return {"Authorization": f"Bearer {TOKEN}"}
    if API_KEY:
        return {"X-API-Key": API_KEY}
    return {}


def api_get(path: str) -> dict | list | None:
    try:
        resp = httpx.get(f"{API_URL}{path}", headers=api_headers(), timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


st.set_page_config(page_title="Agent Observability Dashboard", page_icon="🔍", layout="wide")
st.title("🔍 Agent Observability Dashboard")
st.caption("Production-grade monitoring pour agents LangGraph")

period = st.sidebar.selectbox("Période", ["1h", "6h", "24h", "7d", "30d"], index=2)
st.sidebar.divider()
st.sidebar.markdown("### Configuration")
api_key_input = st.sidebar.text_input("API Key", type="password", value=API_KEY)
token_input = st.sidebar.text_input("Token", type="password", value=TOKEN)
if api_key_input:
    os.environ["AGENT_OBS_API_KEY"] = api_key_input
if token_input:
    os.environ["AGENT_OBS_TOKEN"] = token_input

with st.spinner("Chargement des données..."):
    stats = api_get(f"/api/v1/dashboard?since={period}")

if not stats:
    st.warning("Impossible de contacter l'API. Vérifie la configuration.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Runs total", stats.get("total_runs", 0))
col2.metric("Tokens consommés", f"{stats.get('total_tokens', 0):,}")
col3.metric("Coût total", f"${stats.get('total_cost_usd', 0):.4f}")
col4.metric("Anomalies actives", stats.get("active_anomalies", 0))

col5, col6, col7 = st.columns(3)
col5.metric("Agents actifs", stats.get("active_agents", 0))
col6.metric("Erreurs", stats.get("errors", 0))
col7.metric("Latence moyenne", f"{stats.get('avg_duration_ms', 0):.0f}ms")

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Métriques", "🔄 Traces", "⚠️ Anomalies", "🔔 Alertes", "💰 Coûts"])

with tab1:
    st.subheader("Métriques par agent")
    costs = api_get(f"/api/v1/costs?since={period}")
    if costs and isinstance(costs, list):
        df = pd.DataFrame(costs)
        if not df.empty:
            col_a, col_b = st.columns(2)
            fig1 = px.bar(df, x="agent_name", y="total_cost_usd", title="Coût par agent ($)")
            col_a.plotly_chart(fig1, use_container_width=True)
            fig2 = px.bar(df, x="agent_name", y="total_tokens", title="Tokens par agent")
            col_b.plotly_chart(fig2, use_container_width=True)
            with st.expander("Tableau détaillé"):
                st.dataframe(df, use_container_width=True)

with tab2:
    st.subheader("Dernières traces")
    agent_list = api_get("/api/v1/agents")
    agent_id = None
    if isinstance(agent_list, list) and agent_list:
        agent_options = {a["name"]: a["id"] for a in agent_list}
        selected = st.selectbox("Agent", list(agent_options.keys()))
        agent_id = agent_options.get(selected)
    if agent_id:
        traces = api_get(f"/api/v1/traces/{agent_id}?limit=50")
        if traces and isinstance(traces, list):
            traces_df = pd.DataFrame(traces)
            if not traces_df.empty:
                traces_df["created_at"] = pd.to_datetime(traces_df["created_at"])
                st.dataframe(
                    traces_df[["created_at", "status", "duration_ms", "total_tokens", "cost_usd", "error"]],
                    use_container_width=True,
                )
                with st.expander("Détail d'une trace"):
                    selected_trace = st.selectbox("Choisir une trace", traces_df["id"].tolist())
                    if selected_trace:
                        trace_data = traces_df[traces_df["id"] == selected_trace].iloc[0]
                        st.json(trace_data.to_dict())

with tab3:
    st.subheader("Anomalies détectées")
    agent_list2 = api_get("/api/v1/agents")
    agent_id2 = None
    if isinstance(agent_list2, list) and agent_list2:
        agent_options2 = {a["name"]: a["id"] for a in agent_list2}
        selected2 = st.selectbox("Agent (anomalies)", list(agent_options2.keys()), key="anomaly_agent")
        agent_id2 = agent_options2.get(selected2)
    if agent_id2:
        anomalies = api_get(f"/api/v1/anomalies/{agent_id2}?limit=50")
        if anomalies and isinstance(anomalies, list):
            anom_df = pd.DataFrame(anomalies)
            if not anom_df.empty:
                color_map = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
                for _, a in anom_df.iterrows():
                    icon = color_map.get(a["severity"], "⚪")
                    with st.expander(f"{icon} [{a['anomaly_type']}] {a['title']}"):
                        st.markdown(f"**Sévérité :** {a['severity']}")
                        st.markdown(f"**Description :** {a['description']}")
                        if a.get("evidence"):
                            st.json(a["evidence"])
            else:
                st.success("Aucune anomalie détectée.")

with tab4:
    st.subheader("Alertes actives")
    alerts = api_get("/api/v1/alerts")
    if alerts and isinstance(alerts, list):
        alerts_df = pd.DataFrame(alerts)
        if not alerts_df.empty:
            st.dataframe(alerts_df, use_container_width=True)
        else:
            st.success("Aucune alerte active.")
    else:
        st.info("API non disponible")

with tab5:
    st.subheader("Rapport de coûts")
    costs2 = api_get(f"/api/v1/costs?since={period}")
    if costs2 and isinstance(costs2, list):
        cost_df = pd.DataFrame(costs2)
        if not cost_df.empty:
            total_cost = cost_df["total_cost_usd"].sum()
            total_tok = cost_df["total_tokens"].sum()
            st.metric("Coût total période", f"${total_cost:.4f}")
            st.metric("Tokens totaux", f"{total_tok:,}")
            fig = go.Figure(data=[go.Pie(labels=cost_df["agent_name"], values=cost_df["total_cost_usd"])])
            fig.update_layout(title="Répartition des coûts par agent")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                cost_df[["agent_name", "runs", "total_cost_usd", "total_tokens", "avg_duration_ms"]], use_container_width=True
            )
