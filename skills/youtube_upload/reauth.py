#!/usr/bin/env python3
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CLIENT_SECRETS = os.path.expanduser("~/.secrets/client_secrets.json")
TOKEN_FILE = os.path.expanduser("~/.secrets/youtube_token.json")

def main():
    print("Lancement de la ré-authentification pour Alfred...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    flow.redirect_uri = 'http://localhost'
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print(f"\n--- LIEN D'AUTORISATION ---\n{auth_url}\n---------------------------")
    print("\n1. Cliquez sur le lien ci-dessus.")
    print("2. Connectez-vous avec le compte YouTube de la chaîne.")
    print("3. Acceptez toutes les permissions.")
    print("4. Vous serez redirigé vers localhost (la page ne chargera pas, c'est normal).")
    print("5. Copiez le code 'code=...' dans l'URL de votre navigateur.")
    
    code = input("\nEntrez le code d'autorisation ici : ").strip()
    # Extract code if user pasted the whole URL
    if "code=" in code:
        code = code.split("code=")[-1].split("&")[0]
        
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    
    print("\n✅ Token mis à jour avec succès ! Alfred a maintenant tous les droits.")

if __name__ == "__main__":
    main()
