import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import os


DB = "data.db"

# ----------------------
# BASE DE DONNÉES
# ----------------------
def connect():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    def seed_produits_si_vide(con):
    # Si la table produits est vide, on charge produits.csv automatiquement
    n = con.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
    if n > 0:
        return

    if not os.path.exists("produits.csv"):
        return

    df = pd.read_csv("produits.csv")
    for _, r in df.iterrows():
        con.execute(
            "INSERT OR IGNORE INTO produits (fournisseur, produit, ean, conditionnement) VALUES (?, ?, ?, ?)",
            (str(r["fournisseur"]).strip(),
             str(r["produit"]).strip(),
             str(r["ean"]).strip(),
             int(r["conditionnement"]))
        )
    con.commit()

    con = connect()
    seed_produits_si_vide(con)
    con.execute(
        "CREATE TABLE IF NOT EXISTS produits ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "fournisseur TEXT,"
        "produit TEXT,"
        "ean TEXT UNIQUE,"
        "conditionnement INTEGER)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS stocks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "mois TEXT,"
        "site TEXT,"
        "ean TEXT,"
        "stock INTEGER,"
        "UNIQUE(mois, site, ean))"
    )
    con.commit()
    con.close()

def mois_cle(d):
    return d.replace(day=1).isoformat()

def mois_precedent(m):
    an = int(m[:4])
    mo = int(m[5:7])
    if mo == 1:
        return f"{an-1}-12-01"
    return f"{an}-{str(mo-1).zfill(2)}-01"

# ----------------------
# APP
# ----------------------
st.set_page_config(layout="wide")
st.title("Stocks → Consommation → Commande")

init_db()
con = connect()

site = "Gambetta"
mois = st.date_input("Mois", date.today().replace(day=1))
mois_actuel = mois_cle(mois)
mois_prec = mois_precedent(mois_actuel)

tabs = st.tabs(["Produits", "Stock mensuel", "Commande"])

# ----------------------
# PRODUITS
# ----------------------
with tabs[0]:
    st.subheader("Produits")

    with st.form("ajout"):
        f = st.text_input("Fournisseur")
        p = st.text_input("Produit")
        e = st.text_input("Code-barres")
        c = st.number_input("Conditionnement", 1, 100, 1)
        ok = st.form_submit_button("Ajouter")

        if ok and f and p and e:
            con.execute(
                "INSERT OR IGNORE INTO produits "
                "(fournisseur, produit, ean, conditionnement) "
                "VALUES (?, ?, ?, ?)",
                (f, p, e, c)
            )
            con.commit()

    dfp = pd.read_sql("SELECT fournisseur, produit, ean, conditionnement FROM produits", con)
    st.dataframe(dfp, use_container_width=True)

# ----------------------
# SAISIE STOCK
# ----------------------
with tabs[1]:
    st.subheader("Stock du mois")

    produits = pd.read_sql("SELECT * FROM produits", con)

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
        prev = sp_map.get(r.ean, 0)
        cur = sa_map.get(r.ean, 0)
        conso = max(prev - cur, 0)
        colis = (conso + r.conditionnement - 1) // r.conditionnement

        lignes.append({
            "Produit": r.produit,
            "EAN": r.ean,
            "Stock précédent": prev,
            "Stock du mois": cur,
            "Consommation": conso,
            "Commande colis": colis,
            "Commande unités": colis * r.conditionnement
        })

    df = pd.DataFrame(lignes)

    edit = st.data_editor(
        df,
        disabled=["Produit", "EAN", "Stock précédent", "Consommation", "Commande colis", "Commande unités"],
        use_container_width=True
    )

    if st.button("Enregistrer"):
        for _, r in edit.iterrows():
            con.execute(
                "INSERT INTO stocks (mois, site, ean, stock) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(mois, site, ean) DO UPDATE SET stock=excluded.stock",
                (mois_actuel, site, r["EAN"], int(r["Stock du mois"]))
            )
        con.commit()
        st.success("Stocks enregistrés")

# ----------------------
# COMMANDE
# ----------------------
with tabs[2]:
    st.subheader("Commande à passer")
    dfc = df[df["Commande unités"] > 0]
    st.dataframe(dfc, use_container_width=True)
    st.download_button(
        "Télécharger CSV",
        dfc.to_csv(index=False).encode("utf-8"),
        "commande.csv",
        "text/csv"
    )

con.close()
