import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

DB_PATH = "data.db"

# =========================
# BASE DE DONNÉES
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fournisseur TEXT NOT NULL,
        produit TEXT NOT NULL,
        code_barres TEXT NOT NULL UNIQUE,
        conditionnement INTEGER NOT NULL DEFAULT 1,
        actif INTEGER NOT NULL DEFAULT 1
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mois TEXT NOT NULL,
        site TEXT NOT NULL,
        code_barres TEXT NOT NULL,
        stock INTEGER NOT NULL,
        UNIQUE(mois, site, code_barres)
    );
    """)
    conn.commit()
    conn.close()

def month_key(d):
    return d.replace(day=1).isoformat()

def prev_month_key(mois):
    y, m = int(mois[:4]), int(mois[5:7])
    if m == 1:
        return f"{y-1}-12-01"
    return f"{y}-{str(m-1).zfill(2)}-01"

# =========================
# DONNÉES
# =========================
def load_produits(conn):
    return pd.read_sql("SELECT * FROM produits WHERE actif = 1", conn)

def load_stock(conn, mois, site):
    return pd.read_sql(
        "SELECT code_barres, stock FROM stocks WHERE mois=? AND site=?",
        conn, params=(mois, site)
    )

def save_stock(conn, mois, site, code_barres, stock):
    conn.execute("""
    INSERT INTO stocks (mois, site, code_barres, stock)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(mois, site, code_barres)
    DO UPDATE SET stock=excluded.stock
    """, (mois, site, code_barres, stock))
    conn.commit()

# =========================
# INTERFACE
# =========================
st.set_page_config(page_title="Commande automatique", layout="wide")
init_db()
conn = get_conn()

st.title("Gestion Stocks → Consommation → Commande")

sites = ["Gambetta"]

site = st.selectbox("Site", sites)
mois = st.date_input("Mois", date.today().replace(day=1))
mois_key = month_key(mois)
prev_mois = prev_month_key(mois_key)

tabs = st.tabs(["Produits", "Saisie mensuelle", "Commande"])

# =========================
# ONGLET PRODUITS
# =========================
with tabs[0]:
    st.subheader("Référentiel Produits")

    with st.form("add_product"):
        fournisseur = st.text_input("Fournisseur")
        produit = st.text_input("Produit")
        ean = st.text_input("Code-barres")
        conditionnement = st.number_input("Conditionnement (pack)", min_value=1, value=1)
        submit = st.form_submit_button("Ajouter")

        if submit:
            conn.execute("""
            INSERT INTO produits (fournisseur, produit, code_barres, conditionnement)
            VALUES (?, ?, ?, ?)
            """, (fournisseur, produit, ean, conditionnement))
            conn.commit()
            st.success("Produit ajouté")

    df_prod = load_produits(conn)
    st.dataframe(df_prod, use_container_width=True)

# =========================
# ONGLET SAISIE
# =========================
with tabs[1]:
    st.subheader("Saisie du stock du mois")

    produits = load_produits(conn)
    stock_prev = load_stock(conn, prev_mois, site)
    stock_prev_map = dict(zip(stock_prev.code_barres, stock_prev.stock))

    stock_current = load_stock(conn, mois_key, site)
    stock_current_map = dict(zip(stock_current.code_barres, stock_current.stock))

    rows = []
    for _, p in produits.iterrows():
        prev = stock_prev_map.get(p.code_barres, 0)
        current = stock_current_map.get(p.code_barres, 0)
        conso = max(prev - current, 0)
        commande_colis = -(-conso // p.conditionnement)
        commande_units = commande_colis * p.conditionnement

        rows.append({
            "Produit": p.produit,
            "EAN": p.code_barres,
            "Stock précédent": prev,
            "Stock du mois": current,
            "Consommation": conso,
            "Commande colis": commande_colis,
            "Commande unités": commande_units
        })

    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df,
        disabled=["Produit", "EAN", "Stock précédent", "Consommation", "Commande colis", "Commande unités"],
        use_container_width=True
    )

    if st.button("Enregistrer les stocks"):
        for _, r in edited.iterrows():
            save_stock(conn, mois_key, site, r["EAN"], int(r["Stock du mois"]))
        st.success("Stocks enregistrés")

# =========================
# ONGLET COMMANDE
# =========================
with tabs[2]:
    st.subheader("Commande à passer")

    df_cmd = df[df["Commande unités"] > 0]
    st.dataframe(df_cmd, use_container_width=True)

    csv = df_cmd.to_csv(index=False).encode("utf-8")
    st.download_button("Télécharger la commande (CSV)", csv, "commande.csv")

conn.close()
streamlit
pandas
# Application de gestion des commandes (sans Excel)

## Principe
- Vous saisissez uniquement le stock du mois en cours
- La consommation est calculée automatiquement
- La commande est arrondie au conditionnement

## Lancer en local
```bash
pip install -r requirements.txt
streamlit run app.py
