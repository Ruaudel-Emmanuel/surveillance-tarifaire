import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

class PriceMonitorAPI:
    def __init__(self):
        """Initialise le système avec l'API Perplexity"""
        load_dotenv()
        self.api_key = os.getenv('PERPLEXITY_API_KEY') or st.secrets.get('PERPLEXITY_API_KEY', '')
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.alerts = []
        
        self.products = {
            "Xiaomi Smart Projector L1 PRO Full HD Noir": {
                "competitors": ["Fnac", "Cdiscount", "Boulanger", "Darty", "Amazon", "Rue du Commerce"],
                "target_price": 350.0,
                "alert_threshold": 15.0
            },
            "TONOR Cardioïde Dynamique USB/XLR": {
                "competitors": ["Amazon", "Cdiscount", "Thomann", "Music Store", "Fnac", "Woodbrass"],
                "target_price": 60.0,
                "alert_threshold": 8.0 }
            }
        
    
    def check_pricing_trends(self, product_name):
        """Utilise l'API Perplexity pour récupérer les prix réels"""
        if not self.api_key:
            st.error("🔑 Clé API Perplexity manquante. Configurez PERPLEXITY_API_KEY.")
            return None
            
        product_info = self.products[product_name]
        competitors = product_info["competitors"]
        competitors_str = ", ".join(competitors)
        
        # Prompt optimisé pour la surveillance tarifaire
        prompt = f"""Recherche les prix actuels du {product_name} sur les sites suivants : {competitors_str}.
        
        Pour chaque site où le produit est disponible, donne-moi :
        - Le nom du site
        - Le prix exact en euros
        - La disponibilité (en stock/rupture)
        
        Format de réponse souhaité :
        Site: [Nom] | Prix: [XX.XX€] | Stock: [Disponible/Rupture]
        
        Si un site n'a pas le produit, indique "Non disponible"."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            }
        
        data = {
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}]
            }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            analysis = result['choices'][0]['message']['content']
            
            # Parse la réponse pour extraire les prix
            prices_data = self.parse_price_response(analysis, product_name)
            
            return {
                "product": product_name,
                "competitors": competitors,
                "prices_data": prices_data,
                "raw_analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Erreur API : {str(e)}")
            return None
        except Exception as e:
            st.error(f"❌ Erreur lors du parsing : {str(e)}")
            return None
    
    def parse_price_response(self, analysis, product_name):
        """Parse la réponse de l'API pour extraire les données de prix"""
        import re
        
        prices_data = []
        current_date = datetime.now().date()
        
        # Patterns pour extraire les informations
        lines = analysis.split('\n')
        
        for line in lines:
            if 'Site:' in line and 'Prix:' in line:
                # Extraction du nom du site
                site_match = re.search(r'Site:\s*([^|]+)', line)
                price_match = re.search(r'Prix:\s*(\d+[.,]\d+)', line)
                stock_match = re.search(r'Stock:\s*([^|]+)', line)
                
                if site_match and price_match:
                    site = site_match.group(1).strip()
                    price_str = price_match.group(1).replace(',', '.')
                    price = float(price_str)
                    
                    stock_info = stock_match.group(1).strip() if stock_match else "Inconnu"
                    available = "disponible" in stock_info.lower() or "stock" in stock_info.lower()
                    
                    prices_data.append({
                        'date': current_date,
                        'competitor': site,
                        'product': product_name,
                        'price': price,
                        'available': available,
                        'source': 'API'
                    })
        
        return prices_data

def main():
    """Interface Streamlit avec API réelle"""
    st.set_page_config( 
        page_title="Surveillance Tarifaire - API Live",
        page_icon="🔴",
        layout="wide")
    
    # Initialisation
    monitor = PriceMonitorAPI()
    
    st.title("🔴 Surveillance Tarifaire - Mode API")
    st.markdown("**Données en temps réel** via API Perplexity")
    
    # Vérification de la clé API
    if not monitor.api_key:
        st.warning("⚠️ Configuration requise : Ajoutez votre clé API Perplexity dans les secrets Streamlit.")
        st.info("📋 Allez dans Settings > Secrets de votre app Streamlit Cloud")
        st.code('PERPLEXITY_API_KEY = "votre_clé_ici"')
        st.stop()
    
    # Interface principale
    selected_product = st.sidebar.selectbox(
        "Produit à surveiller:",
        list(monitor.products.keys())
    )
    
    if st.sidebar.button("🔄 Actualiser les prix"):
        with st.spinner("🔍 Recherche des prix en cours..."):
            results = monitor.check_pricing_trends(selected_product)
            
            if results and results['prices_data']:
                df = pd.DataFrame(results['prices_data'])
                
                # Affichage des résultats
                st.subheader(f"📊 Résultats pour {selected_product}")
                
                # Métriques
                available_prices = df[df['available'] == True]
                if not available_prices.empty:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("💸 Prix minimum", f"{available_prices['price'].min():.2f}€")
                    
                    with col2:
                        st.metric("📊 Prix moyen", f"{available_prices['price'].mean():.2f}€")
                    
                    with col3:
                        availability = (df['available'].sum() / len(df)) * 100
                        st.metric("📦 Disponibilité", f"{availability:.0f}%")
                
                # Tableau des prix
                st.subheader("💰 Prix actuels")
                display_df = df.copy()
                display_df['Disponible'] = display_df['available'].map({True: '✅', False: '❌'})
                display_df = display_df[['competitor', 'price', 'Disponible']]
                display_df.columns = ['Concurrent', 'Prix (€)', 'Stock']
                st.dataframe(display_df, use_container_width=True)
                
                # Graphique
                if len(available_prices) > 1:
                    fig = px.bar(
                        available_prices,
                        x='competitor',
                        y='price',
                        title="Comparaison des prix disponibles",
                        color='price',
                        color_continuous_scale='RdYlGn_r')
                    st.plotly_chart(fig, use_container_width=True)
                
                # Analyse brute
                with st.expander("📄 Analyse détaillée de l'API"):
                    st.text(results['raw_analysis'])
            
            else:
                st.error("❌ Aucune donnée récupérée. Vérifiez votre clé API.")

if __name__ == "__main__":
    main()
