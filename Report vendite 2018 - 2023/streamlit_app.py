from pathlib import Path
import kagglehub
import streamlit as st
import pandas as pd
import plotly.express as px
import os

#CONFIGURAZIONE PAGINA STREAMLIT

st.set_page_config(
page_title="ANALISI ANDAMENTO VENDITE",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETTE = {
    "MOBILE":    "#1F3A5F",
    "ACCESSORY": "#56B4E9",
    "TABLET": "#687FF2",
}

@st.cache_data
def load_data():
    # 1. Recuperiamo il percorso della cartella tramite kagglehub
    path = kagglehub.dataset_download("shubham2703/smartphone-retail-outlet-sales-data")
    
    # 2. Troviamo il file CSV all'interno di quel percorso
    csv_files = [f for f in os.listdir(path) if f.endswith('.csv')]
    file_path = os.path.join(path, csv_files[0])
    
    # 3. Leggiamo il dataset
    df = pd.read_csv(file_path)
    
    # 4. Applichiamo le tue trasformazioni originali
    df['Date_parsed'] = pd.to_datetime(df['Date'], dayfirst=True)
    df['Mese'] = df['Date_parsed'].dt.to_period('M').dt.to_timestamp()
    df['vendite_k_eur'] = df['Amount'] / 1000
    df['Prezzo_tipico'] = df.groupby('P_NO')['Price'].transform(lambda x: x.mode()[0])
    df['Sconto_sospetto'] = df['Price'] < df['Prezzo_tipico']
    
    return df

# Richiamiamo la funzione (non serve più passargli il file_path tra parentesi)
df = load_data()

# SIDEBAR

def sidebar_controls(df: pd.DataFrame) -> dict:
    """Renderizza i controlli sidebar e restituisce i filtri scelti."""
    with st.sidebar:
        st.header("SELZIONE DEI FILTRI")


        with st.expander(":information_source: Come funziona", expanded=False):
            st.markdown(
                "**Trend:** andamento del fatturato e sulle quantità vendute su anno mobile.\n\n"
                "**Per categoria:** confronto delle vendite per categoria.\n\n"
                "**Identificazione periodi di sconto:** percentuale di vendite con sconto sospetto.\n\n"
                "**Dati:** tabella filtrata con export CSV."
            )

        st.divider()
        st.subheader("Filtri")

        Categorie_prodotto = st.multiselect(
            "Categorie prodotto",
            sorted(df["TYPE OF PRODUCT"].unique()),
            default=sorted(df["TYPE OF PRODUCT"].unique()),
        )
        
        # Periodo: anno e mese selezionabili separatamente (non necessariamente un range continuo)
        anni_disponibili = sorted(df["Date_parsed"].dt.year.unique())
        anni_selezionati = st.multiselect(
            "Anno",
            anni_disponibili,
            default=anni_disponibili,
        )
        nomi_mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        mesi_selezionati_label = st.multiselect(
            "Mese",
            nomi_mesi,
            default=nomi_mesi,
        )
        mesi_selezionati = [nomi_mesi.index(m) + 1 for m in mesi_selezionati_label]

        

    return {
        "Categorie_prodotto": Categorie_prodotto,
        "anni_selezionati": anni_selezionati,
        "mesi_selezionati": mesi_selezionati,
    
    }


def apply_filters(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Applica i filtri al DataFrame."""
    return df[
        df["TYPE OF PRODUCT"].isin(f["Categorie_prodotto"])
        & df["Date_parsed"].dt.year.isin(f["anni_selezionati"])
        & df["Date_parsed"].dt.month.isin(f["mesi_selezionati"])
    ]


def apply_filters_no_year(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Applica i filtri al DataFrame escludendo il filtro Anno (per confronti anno su anno)."""
    return df[
        df["TYPE OF PRODUCT"].isin(f["Categorie_prodotto"])
        & df["Date_parsed"].dt.month.isin(f["mesi_selezionati"])
    ]

#KPI
def render_kpi_row(df_f: pd.DataFrame) -> None:
    """Quattro KPI: Fatturato Totale, Mese di picco, Anno migliore (Best Year), Categoria top."""
    if len(df_f) == 0:
        return

    tot = df_f["Amount"].sum()

    # Mese di picco (sul filtrato)
    per_mese = df_f.groupby("Mese", as_index=False)["Amount"].sum()
    mese_top = per_mese.loc[per_mese["Amount"].idxmax()]

    # Anno migliore e categoria leader
    anno_top = df_f.groupby(df_f["Date_parsed"].dt.year)["Amount"].sum().idxmax()
    categoria_top = df_f.groupby("TYPE OF PRODUCT")["Amount"].sum().idxmax()

    c1, c2, c3, c4, c5 = st.columns(5)

    # Fatturato per anno: l'anno è selezionabile da menù a tendina, mostrato sotto la metrica
    metric_slot = c1.empty()
    anni_disponibili = sorted(df_f["Date_parsed"].dt.year.unique(), reverse=True)
    anno_selezionato = c1.selectbox("Anno", anni_disponibili, index=0)
    fatturato_anno = df_f.loc[df_f["Date_parsed"].dt.year == anno_selezionato, "Amount"].sum()
    quota_perc = fatturato_anno / tot * 100 if tot else 0
    metric_slot.metric(
        f"Fatturato anno {anno_selezionato}",
        f"€ {fatturato_anno/1e6:,.2f} Mln",
        delta=f"{quota_perc:.1f}% sul totale filtrato",
    )
    c2.metric(
        "Fatturato totale",
        f"€ {tot/1e6:,.2f} Mln",
    )
    c3.metric(
        "Mese di picco",
        mese_top["Mese"].strftime("%b %Y"),
        delta=f"€ {mese_top['Amount']:,.0f}",
    )
    c4.metric("Anno migliore",   str(anno_top))
    c5.metric("Categoria leader", categoria_top)

#TAB: TREND
def render_trend_chart(df_f: pd.DataFrame, df_yoy: pd.DataFrame) -> None:
    st.subheader('Andamento vendinte')

    col_a, col_b = st.columns([2,1])


    with col_a:
        # Variazione % anno su anno (fatturato e quantità) - non risente del filtro Anno
        andamento_annuale = df_yoy.groupby('F.Y').agg({
            'Amount': 'sum',
            'Quantity': 'sum'
        })

        crescita_yoy = andamento_annuale.pct_change() * 100
        crescita_yoy = crescita_yoy.dropna().rename(columns={'Amount': 'Variazione % fatturato', 'Quantity': 'Variazione % quantità'})

        crescita_yoy_long = crescita_yoy.reset_index().melt(
            id_vars='F.Y', var_name='Indicatore', value_name='Variazione %'
        )

        fig = px.bar(
            crescita_yoy_long,
            x='F.Y',
            y='Variazione %',
            color='Indicatore',
            barmode='group',
            title='Variazione % anno su anno',
            color_discrete_map={
                'Variazione % fatturato': '#2a78d6',
                'Variazione % quantità': '#1baf7a',
            },
            labels={'F.Y': 'Anno fiscale', 'Indicatore': 'Legenda'},
        )
        fig.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
        fig.add_hline(y=0, line_color='#c3c2b7', line_width=1)
        fig.update_layout(height=420, template='plotly_white', legend_title_text='Legenda')
        st.plotly_chart(fig, width="stretch")

    with col_b:
        # vendite per categoria:
        vendite_per_categoria = df_f.groupby('TYPE OF PRODUCT')['Amount'].sum().reset_index()
        vendite_per_categoria = vendite_per_categoria.sort_values(by='Amount', ascending=False)
        fig2 = px.pie(
            vendite_per_categoria,
            values='Amount',
            names='TYPE OF PRODUCT',
            color='TYPE OF PRODUCT',
            color_discrete_map=PALETTE,
            title='Vendite per Categoria',
        )
        fig2.update_traces(textinfo='label+percent', textposition='outside')
        fig2.update_layout(height=420, template='plotly_white')
        st.plotly_chart(fig2, width="stretch")

    st.divider()

    #Metodo di pagamento favorito dalla clientela
    st.subheader("Metodo di pagamento più utilizzato")
    metodo_pagamento = (pd.crosstab(df_f['TYPE OF PRODUCT'], df_f['PAYMENT TYPE'], normalize='index')*100
    )
    metodo_pagamento_long = metodo_pagamento.reset_index().melt(
        id_vars='TYPE OF PRODUCT', var_name='PAYMENT TYPE', value_name='Percentuale'
    )
    fig3 = px.bar(
        metodo_pagamento_long,
        x='PAYMENT TYPE',
        y='Percentuale',
        color='TYPE OF PRODUCT',
        barmode='group',
        title='Metodo di pagamento più utilizzato per categoria',
        color_discrete_map=PALETTE,
    )
    fig3.update_layout(height=420, template="plotly_white")
    st.plotly_chart(fig3, width="stretch")

    
# TAB: SCONTI
def render_sconti_chart(df_f: pd.DataFrame) -> None:
    # Trend mensile per categoria (small multiples implicito via colore)
    st.subheader("Andamento vendite per categoria")
    per_mese_cat = (
        df_f.groupby(['Mese', 'TYPE OF PRODUCT'], as_index=False)["vendite_k_eur"].sum()
    )
    fig = px.line(
        per_mese_cat,
        x="Mese",
        y="vendite_k_eur",
        color="TYPE OF PRODUCT",
        markers=True,
        color_discrete_map= PALETTE,
        labels={"Mese": "", "vendite_k_eur": "Vendite (k€)"},
    )
    fig.update_layout(height=360, template="plotly_white")
    fig.update_yaxes(rangemode='tozero')
    fig.update_xaxes(
        tickmode='array',
        tickvals=sorted(per_mese_cat['Mese'].unique()),
        tickformat="%m-%Y",
        tickangle=-90,
    )
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # Andamento percentuale di transazioni scontate per mese
    st.subheader("Percentuale di transazioni scontate per mese")
    sconti = df_f[df_f['Sconto_sospetto']].copy()
    transazioni_per_mese = df_f.groupby('Mese').size()
    sconti_per_mese = sconti.groupby('Mese').size()
    tasso_sconto_mensile = (
        sconti_per_mese.div(transazioni_per_mese).fillna(0) * 100
    ).rename('Percentuale')

    fig = px.line(
        tasso_sconto_mensile.reset_index(),
        x="Mese",
        y="Percentuale",
        markers=True,
        labels={"Mese": "", "Percentuale": "Percentuale di transazioni scontate"},
    )
    fig.update_layout(height=360, template="plotly_white")
    fig.update_xaxes(
        tickmode='array',
        tickvals=sorted(tasso_sconto_mensile.index.unique()),
        tickformat="%m-%Y",
        tickangle=-90,
    )
    st.plotly_chart(fig, width="stretch")

    # Entità dello sconto (solo sulle transazioni scontate)
    media_sconto_perc = (
        (sconti['Prezzo_tipico'] - sconti['Price']) / sconti['Prezzo_tipico'] * 100
    ).mean() if len(sconti) else 0
    totale_sconto_eur = ((sconti['Prezzo_tipico'] - sconti['Price']) * sconti['Quantity']).sum()

    k1, k2 = st.columns(2)
    k1.metric("Sconto medio applicato", f"{media_sconto_perc:.1f}%")
    k2.metric("Sconto totale stimato", f"€ {totale_sconto_eur / 1e6:,.2f} Mln")

# TAB: DATI
def render_data_table(df_f: pd.DataFrame) -> None:
    st.subheader("Dati filtrati")
    st.dataframe(df_f, width="stretch")

    #conteggio mesi considerati per anno fiscale (sul dataset filtrato)
    conta_mese = df_f.groupby('F.Y')['Mese'].nunique().rename('Mesi considerati')
    st.caption("Numero di mesi considerati per anno fiscale (dati filtrati):")
    st.dataframe(conta_mese, width="stretch")

    # Export CSV
    csv = df_f.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Esporta dati filtrati in CSV",
        data=csv,
        file_name='dati_filtrati.csv',
        mime='text/csv',
    )


# Main function to run the Streamlit app

def main() -> None:
    st.title(":iphone: Andamento vendite - Dashboard")
    st.caption(
        'Analisi dei dati di vendita di un negozio di telefonia mobile, con focus su trend, sconti e dati filtrati.'
    )

    df = load_data()

    # --- Sidebar e filtri
    filters = sidebar_controls(df)
    df_f = apply_filters(df, filters)
    df_yoy = apply_filters_no_year(df, filters)

    # --- Caso "filtri troppo stretti"
    if len(df_f) == 0:
        st.warning(
            ":warning: Filtri troppo stretti: nessuna riga selezionata. "
            "Si consiglia di allargare almeno uno dei filtri in sidebar."
        )
        st.stop()

    # --- KPI sempre visibili
    render_kpi_row(df_f)
    st.divider()

    # --- Tab di contenuto
    tab_trend, tab_sconti, tab_data = st.tabs(
        [":chart_with_upwards_trend: Trend",
         ":moneybag: Sconti",
         ":clipboard: Dati"]
    )
    with tab_trend: render_trend_chart(df_f, df_yoy)
    with tab_sconti:   render_sconti_chart(df_f)
    with tab_data:  render_data_table(df_f)

    st.divider()
    st.caption(
        'Fonte dei dati: https://www.kaggle.com/datasets/shubham2703/smartphone-retail-outlet-sales-data'
    )


if __name__ == "__main__":
    main()




