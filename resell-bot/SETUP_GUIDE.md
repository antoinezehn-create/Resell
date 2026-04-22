# 🤖 Resell Bot — Guide d'installation complet

> Pas besoin de savoir coder. Suivez les étapes dans l'ordre et le bot tournera tout seul.

**Temps estimé : 30–45 minutes (une seule fois)**

---

## Ce dont vous aurez besoin

| Compte | Pourquoi | Gratuit ? |
|---|---|---|
| GitHub | Héberge le bot et le fait tourner | ✅ Oui |
| Telegram | Reçoit vos alertes deals | ✅ Oui |
| BrickLink | Prix de référence Lego | ✅ Oui |
| Cardmarket | Prix de référence Pokémon | ✅ Oui |
| PriceCharting | Prix de référence jeux rétro | ✅ Oui |

---

## ÉTAPE 1 — Créer un compte GitHub

1. Allez sur **https://github.com**
2. Cliquez sur **Sign up** (en haut à droite)
3. Entrez votre email, choisissez un mot de passe, un nom d'utilisateur
4. Vérifiez votre email (GitHub envoie un code)
5. Choisissez le plan **Free** quand il vous le propose

✅ Votre compte GitHub est prêt.

---

## ÉTAPE 2 — Créer le dépôt (votre "coffre" pour le bot)

1. Une fois connecté sur GitHub, cliquez sur le **+** en haut à droite → **New repository**
2. Remplissez :
   - **Repository name** : `resell-bot`
   - **Visibility** : choisissez **Public** (obligatoire pour les Actions gratuites illimitées)
   - Cochez **Add a README file**
3. Cliquez **Create repository**

✅ Votre dépôt est créé.

---

## ÉTAPE 3 — Uploader les fichiers du bot

1. Sur votre dépôt GitHub (page `github.com/VOTRE_NOM/resell-bot`), cliquez sur **Add file** → **Upload files**
2. Glissez-déposez **tout le contenu** du dossier `resell-bot` que vous avez reçu
   - ⚠️ Assurez-vous d'uploader aussi les dossiers (`scrapers/`, `prices/`, `utils/`, `notifier/`, `.github/`)
   - GitHub peut vous demander de confirmer — cliquez **Commit changes**

> 💡 **Astuce** : Si le drag-and-drop ne prend pas les sous-dossiers, utilisez l'application GitHub Desktop (gratuite) : https://desktop.github.com

✅ Tous les fichiers sont en ligne.

---

## ÉTAPE 4 — Créer votre bot Telegram

1. Ouvrez Telegram et cherchez **@BotFather** (le compte officiel avec la coche bleue)
2. Cliquez **Start** ou tapez `/start`
3. Tapez `/newbot`
4. Il vous demande un nom pour votre bot → tapez par exemple `MonResellBot`
5. Il vous demande un username → tapez par exemple `mon_resell_alerts_bot` (doit finir par `bot`)
6. BotFather vous donne un **token** qui ressemble à : `7234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   → **Copiez ce token, vous en aurez besoin à l'Étape 6**

**Récupérer votre Chat ID :**
1. Cherchez votre bot dans Telegram (le nom que vous venez de créer) et cliquez **Start**
2. Allez sur ce lien dans votre navigateur (remplacez VOTRE_TOKEN) :
   `https://api.telegram.org/botVOTRE_TOKEN/getUpdates`
3. Vous verrez un JSON — cherchez `"id"` sous `"chat"`. Ce nombre est votre **Chat ID**
   → **Notez ce numéro**

> 💡 Si le JSON dit `{"result":[]}` (vide), envoyez n'importe quel message à votre bot d'abord, puis rechargez la page.

✅ Vous avez votre Token et votre Chat ID Telegram.

---

## ÉTAPE 5 — Créer vos clés API

### 5a — BrickLink (pour les prix Lego)

1. Créez un compte sur **https://www.bricklink.com** (gratuit)
2. Connectez-vous, puis allez sur : **My BrickLink** → **API Settings** → **Create API Key**
   (ou directement : https://www.bricklink.com/v3/api.page)
3. Remplissez le formulaire :
   - App Name : `ResellBot`
   - Registered IP : laissez vide
4. Vous obtenez 4 clés :
   - **Consumer Key**
   - **Consumer Secret**
   - **Token Value** (c'est le Token Key)
   - **Token Secret**

→ **Notez ces 4 valeurs**

### 5b — Cardmarket (pour les prix Pokémon)

1. Créez un compte vendeur sur **https://www.cardmarket.com** (gratuit)
   - Lors de l'inscription, choisissez "Seller account"
2. Connectez-vous, puis allez dans : **Account** → **Seller Tools** → **API**
   (ou directement : https://api.cardmarket.com/ws/documentation/API_2.0:Auth)
3. Cliquez **Request developer account** → validez votre email
4. Une fois approuvé (quelques heures), allez dans **My Apps** → **Create App**
5. Vous obtenez :
   - **App Token**
   - **App Secret**
   - **Access Token**
   - **Access Token Secret**

→ **Notez ces 4 valeurs**

### 5c — PriceCharting (pour les jeux rétro)

1. Allez sur **https://www.pricecharting.com/api**
2. Entrez votre email pour recevoir une clé API gratuite
3. Vérifiez votre boîte mail — vous recevrez votre **API Key**

→ **Notez cette clé**

✅ Vous avez toutes vos clés API.

---

## ÉTAPE 6 — Ajouter vos clés secrètes à GitHub

> ⚠️ **Important** : Les clés API ne vont PAS dans les fichiers du bot — elles vont dans les "Secrets" GitHub pour rester invisibles.

1. Sur votre dépôt GitHub, cliquez sur **Settings** (engrenage, en haut de la page)
2. Dans le menu gauche, cliquez **Secrets and variables** → **Actions**
3. Cliquez **New repository secret** pour chaque ligne ci-dessous :

| Nom du secret | Valeur |
|---|---|
| `TELEGRAM_TOKEN` | Votre token BotFather |
| `TELEGRAM_CHAT_ID` | Votre Chat ID Telegram |
| `BRICKLINK_CONSUMER_KEY` | Consumer Key BrickLink |
| `BRICKLINK_CONSUMER_SECRET` | Consumer Secret BrickLink |
| `BRICKLINK_TOKEN_KEY` | Token Value BrickLink |
| `BRICKLINK_TOKEN_SECRET` | Token Secret BrickLink |
| `CARDMARKET_APP_TOKEN` | App Token Cardmarket |
| `CARDMARKET_APP_SECRET` | App Secret Cardmarket |
| `CARDMARKET_ACCESS_TOKEN` | Access Token Cardmarket |
| `CARDMARKET_ACCESS_SECRET` | Access Token Secret Cardmarket |
| `PRICECHARTING_API_KEY` | API Key PriceCharting |

Pour chaque secret : cliquez **New repository secret** → entrez le Nom → entrez la Valeur → cliquez **Add secret**.

✅ Vos secrets sont protégés.

---

## ÉTAPE 7 — Activer GitHub Actions

1. Sur votre dépôt, cliquez sur l'onglet **Actions**
2. Si GitHub vous demande "I understand my workflows…" → cliquez **Enable**
3. Dans la liste à gauche, vous verrez **Resell Bot**
4. Cliquez dessus, puis cliquez **Run workflow** → **Run workflow** (bouton vert)

Le bot va tourner une première fois maintenant. Vous verrez le cercle tourner pendant ~2-3 minutes.

5. Une fois terminé, regardez votre Telegram — si tout est bien configuré, vous recevrez un message !

✅ Le bot tourne. À partir de maintenant il se lance **automatiquement toutes les 30 minutes**, sans que vous fassiez quoi que ce soit.

---

## ÉTAPE 8 — Vérifier que ça marche

**Comment voir si le bot a trouvé des deals ?**
→ Regardez Telegram. Chaque deal vous envoie un message avec le lien direct.

**Comment voir les logs du bot (ce qu'il fait) ?**
→ Sur GitHub, onglet **Actions** → cliquez sur la dernière exécution → cliquez **run-bot** → vous voyez tous les logs en temps réel.

**Comment savoir si une exécution a planté ?**
→ GitHub vous enverra un email automatiquement si une exécution échoue.

---

## ⚙️ Personnaliser le bot

Tout se passe dans le fichier `config.yml` de votre dépôt.

Pour le modifier : sur GitHub, cliquez sur `config.yml` → cliquez le crayon ✏️ (en haut à droite du fichier) → modifiez → cliquez **Commit changes**.

**Ce que vous pouvez changer :**

```yaml
alerts:
  min_margin_percent: 20    # ← changer le % minimum de marge
  min_profit_euros: 50      # ← changer le bénéfice minimum en €
  min_prices:
    lego: 20                # ← ignorer les annonces Lego sous 20€
    pokemon: 5              # ← ignorer les annonces Pokémon sous 5€
    games: 5                # ← ignorer les annonces jeux sous 5€
```

Pour ajouter des sets Lego à surveiller en priorité, ajoutez leur numéro dans `lego_watchlist_sets`.

---

## ❓ Problèmes fréquents

**"Je ne reçois rien sur Telegram"**
→ Vérifiez que vous avez bien cliqué Start sur votre bot Telegram.
→ Vérifiez le Chat ID (refaites l'étape 4 si besoin).
→ Lancez le bot manuellement (Étape 7) et regardez les logs Actions.

**"L'Action échoue avec une erreur rouge"**
→ Cliquez sur l'exécution → cliquez `run-bot` → lisez le message d'erreur.
→ 90% du temps c'est une clé API manquante ou mal copiée dans les Secrets.

**"Le bot tourne mais ne trouve pas de deals"**
→ C'est normal ! Les deals ne sont pas permanents. Le bot scanne en continu.
→ Vous pouvez baisser le seuil dans `config.yml` pour tester (ex: `min_margin_percent: 5`).

**"GitHub dit que les Actions sont désactivées"**
→ Allez dans **Settings** → **Actions** → **General** → sélectionnez **Allow all actions** → Save.

---

## 📱 Format des alertes Telegram

Voici à quoi ressemble une alerte :

```
🔥🔥 GROS DEAL — 🏷️ Leboncoin
🧱 Lego #75192

💰 Prix affiché : 350 €
📊 Prix marché  : 520 € (BrickLink avg sold)
💵 Bénéfice     : +170 € (+33%)

📝 Millennium Falcon complet, boîte abîmée mais pièces...

🔗 https://www.leboncoin.fr/jeux_jouets/...
```

**Niveaux d'alerte :**
- 🔥🔥 GROS DEAL = +40% de marge ou +200€ de bénef
- 🔥 BON DEAL = +25% de marge ou +100€ de bénef
- ✅ DEAL = seuil minimum atteint (20% ou 50€)

---

*Bot créé avec ❤️ — mis à jour automatiquement toutes les 30 minutes, 24h/24.*
