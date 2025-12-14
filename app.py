import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import date

DB = "data.db"

# ======================
# BASE DE DONNÉES
# ======================
def connect():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = connect()
    con.execute(
        "CREATE TABLE IF NOT EXISTS produits ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "fournisseur TEXT NOT NULL,"
        "produit TEXT NOT NULL,"
        "ean TEXT NOT NULL UNIQUE,"
        "conditionnement INTEGER NOT NULL DEFAULT 1)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS stocks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "mois TEXT NOT NULL,"
        "site TEXT NOT NULL,"
        "ean TEXT NOT NULL,"
        "stock INTEGER NOT NULL,"
        "UNIQUE(mois, site, ean))"
    )
    con.commit()
    con.close()

def seed_produits_si_vide(con):
    n = con.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
    if n > 0:
        return

    if not os.path.exists("produits.csv"):
        return

    df = pd.read_csv("produits.csv")
    for _, r in df.iterrows():
        con.execute(
            "INSERT OR IGNORE INTO produits (fournisseur, produit, ean, conditionnement) VALUES (?, ?, ?, ?)",
            (
                str(r["fournisseur"]).strip(),
                str(r["produit"]).strip(),
                str(r["ean"]).strip(),
                int(r["conditionnement"]),
            )
        )
    con.commit()

def mois_cle(d):
    return d.replace(day=1).isoformat()

def mois_precedent(m):
    an = int(m[:4])
    mo = int(m[5:7])
    if mo == 1:
        return f"{an-1}-12-01"
    return f"{an}-{str(mo-1).zfill(2)}-01"

def build_table(con, site, mois_actuel):
    mois_prec = mois_precedent(mois_actuel)

    produits = pd.read_sql(
        "SELECT fournisseur, produit, ean, conditionnement FROM produits",
        con
    )

    colonnes = [
        "Fournisseur", "Produit", "EAN", "Conditionnement",
        "Stock précédent", "Stock du mois",
        "Consommation", "Commande colis", "Commande unités"
    ]

    if produits.empty:
        return pd.DataFrame(columns=colonnes)

    sp = pd.read_sql(
        "SELECT ean, stock FROM stocks WHERE mois=? AND site=?",
        con, params=(mois_prec, site)
    )
    sa = pd.read_sql(
        "SELECT ean, stock FROM stocks WHERE mois=? AND site=?",
        con, params=(mois_actuel, site)
    )

    sp_map = dict(zip(sp.ean, sp.stock))
    sa_map = dict(zip(sa.ean, sa.stock))

    lignes = []
    for _, r in produits.iterrows():
        cond = int(r["conditionnement"]) if int(r["conditionnement"]) > 0 else 1
        prev = int(sp_map.get(r["ean"], 0))
        cur = int(sa_map.get(r["ean"], 0))
        conso = max(prev - cur, 0)
        colis = (conso + cond - 1) // cond
        unites = colis * cond

        lignes.append({
            "Fournisseur": r["fournisseur"],
            "Produit": r["produit"],
            "EAN": r["ean"],
            "Conditionnement": cond,
            "Stock précédent": prev,
            "Stock du mois": cur,
            "Consommation": conso,
            "Commande colis": colis,
            "Commande unités": unites
        })

    return pd.DataFrame(lignes, columns=colonnes)

# ======================
# APPLICATION
# ======================
st.set_page_config(page_title="Gestion des commandes", layout="wide")
st.title("Stocks → Consommation → Commande")

init_db()
con = connect()
seed_produits_si_vide(con)

site = st.text_input("Site", value="Gambetta")
mois = st.date_input("Mois", value=date.today().replace(day=1))
mois_actuel = mois_cle(mois)

onglets = st.tabs(["Produits", "Stock mensuel", "Commande"])

# ======================
# ONGLET PRODUITS
# ======================
with onglets[0]:
    st.subheader("Référentiel produits (chargé automatiquement)")

    dfp = pd.read_sql(
        "SELECT fournisseur, produit, ean, conditionnement FROM produits",
        con
    )
    st.dataframe(dfp, use_container_width=True)

# ======================
# ONGLET STOCK
# ======================
with onglets[1]:
    st.subheader("Saisie du stock du mois")

    df = build_table(con, site, mois_actuel)

    if df.empty:
        st.warning("Aucun produit disponible.")
    else:
        edited = st.data_editor(
            df,
            disabled=[
                "Fournisseur", "Produit", "EAN", "Conditionnement",
                "Stock précédent", "Consommation",
                "Commande colis", "Commande unités"
            ],
            use_container_width=True
        )

        if st.button("Enregistrer les stocks"):
            for _, r in edited.iterrows():
                con.execute(
                    "INSERT INTO stocks (mois, site, ean, stock) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(mois, site, ean) DO UPDATE SET stock=excluded.stock",
                    (mois_actuel, site, r["EAN"], int(r["Stock du mois"]))
                )
            con.commit()
            st.success("Stocks enregistrés.")
            st.rerun()

# ======================
# ONGLET COMMANDE
# ======================
with onglets[2]:
    st.subheader("Commande à passer")

    df = build_table(con, site, mois_actuel)
    dfc = df[df["Commande unités"] > 0]

    st.dataframe(dfc, use_container_width=True)

    st.download_button(
        "Télécharger la commande (CSV)",
        dfc.to_csv(index=False).encode("utf-8"),
        "commande.csv",
        "text/csv"
    )

con.close()
