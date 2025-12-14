import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "data.db"

# ======================
# BASE DE DONNÉES
# ======================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mois TEXT NOT NULL,
            site TEXT NOT NULL,
            code_barres TEXT NOT NULL,
            stock INTEGER NOT NULL,
            UNIQUE(mois, site, code_barres)
        )
    """)
    conn.commit()
    conn.close()

def mois_key(d):
    return d.replace(day=1).isoformat()

def mois_precedent(mois):
    annee = int(mois[:4])
    mois_num = int(mois[5:7])
    if mois_num == 1:
        return f"{annee-1}-12-01"
    return f"{annee}-{str(mois_num-1).zfill(2)}-01"

# ======================
# INTERFACE
# ======================
st.set_page_config(page_title="Gestion des commandes", layout="wide")
init_db()
conn = get_conn()

st.title("Gestion Stocks → Consommation → Commande")

site = "Gambetta"
mois = st.date_input("Mois", date.today().replace(day=1))
mois_courant = mois_key(mois)
mois_prec = mois_precedent(mois_courant)

onglets = st.tabs(["Produits", "Saisie stock", "Commande"])

# ======================
# ONGLET PRODUITS
# ======================
with onglets[0]:
    st.subheader("Produits")

    with st.form("ajout_produit"):
        fournisseur = st.text_input("Fournisseur")
        produit = st.text_input("Produit")
        code = st.text_input("Code-barres")
        conditionnement = st.number_input("Conditionnement", min_value=1, value=1)
        ajouter = st.form_submit_button("Ajouter")

        if ajouter and fournisseur and produit and code:
            conn.execute("""
                INSERT OR IGNORE INTO produits
                (fournisseur, produit, code_barres, conditionnement)
                VALUES (?, ?, ?, ?)
            """, (fournisseur, produit, code, conditionnement))
            conn.commit()

    df_produits = pd.read_sql(
        "SELECT fournisseur, produit, code_barres, conditionnement FROM produits WHERE actif = 1",
        conn
    )
    st.dataframe(df_produits, use_container_width=True)

# ======================
# ONGLET SAISIE STOCK
# ======================
with onglets[1]:
    st.subheader("Saisie du stock du mois")

    produits = pd.read_sql("SELECT * FROM produits WHERE actif = 1", conn)

    stock_prec = pd.read_sql(
        "SELECT code_barres, stock FROM stocks WHERE mois=? AND site=?",
        conn, params=(mois_prec, site)
    )
    stock_prec_map = dict(zip(stock_prec.code_barres, stock_prec.stock))

    stock_actuel = pd.read_sql(
        "SELECT code_barres, stock FROM s_
