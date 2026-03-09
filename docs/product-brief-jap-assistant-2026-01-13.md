---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - '_bmad-output/analysis/brainstorming-session-2026-01-07.md'
  - '_bmad-output/planning-artifacts/technical-decisions.md'
date: '2026-01-13'
author: 'Clemtard'
---

# Product Brief: jap-assistant

<!-- Content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

**jap-assistant** est une application web mobile-first qui révolutionne la gestion des tournois de padel en libérant les Juges Arbitres de Padel (JAP) de leurs tableurs Excel et en donnant aux joueurs une visibilité temps réel sur le déroulement des tournois.

Alors que le padel explose en France et que les tournois se multiplient, les JAP restent prisonniers d'une solution inadaptée: Excel sur ordinateur. Les templates FFT sont complexes, la gestion mobile est impossible (écran trop petit, interface inadaptée), et les JAP passent leur temps à répondre aux joueurs qui demandent "quand est-ce que je joue?". De l'autre côté, les joueurs vivent une attente frustrante et imprévisible, sans visibilité sur le déroulement du tournoi.

**jap-assistant** comble le vide béant entre les apps de réservation (qui s'arrêtent à l'inscription) et la gestion réelle du tournoi. La solution se distingue par son approche **gratuite, mobile-first, et centrée sur l'expérience des deux côtés**: le JAP qui gère depuis son téléphone sur le terrain, et le joueur qui suit en temps réel via QR code.

Le moment magique se produit quand le JAP ouvre l'app sur son mobile et voit instantanément qui doit jouer, pour quelles places, sur quel terrain - **la lisibilité instantanée** qui remplace le parcours chaotique dans les onglets Excel. Pour le joueur, c'est quand il scanne le QR code et voit "ton prochain match dans 2 matchs, ~25 min" au lieu de devoir demander au JAP toutes les 10 minutes.

Conçu par un joueur qui devient JAP, **jap-assistant** comprend les frustrations des deux côtés et les résout dans une seule expérience fluide.

---

## Core Vision

### Problem Statement

**Pour les Juges Arbitres de Padel (JAP):**

La gestion des tournois de padel repose aujourd'hui sur Excel ou les templates papier/numériques de la FFT, des outils conçus pour un bureau avec grand écran, pas pour la mobilité requise le jour du tournoi. Les JAP sont coincés devant leur ordinateur alors qu'ils devraient être proches des terrains et des joueurs. Utiliser Excel sur mobile est un cauchemar: écran trop petit, interface inadaptée, navigation entre onglets chaotique pour trouver qui joue, pour quelles places, sur quel terrain.

Résultat: le JAP passe son temps à parcourir ses feuilles Excel et à répondre sans cesse aux mêmes questions des joueurs au lieu de se concentrer sur l'arbitrage et la fluidité du tournoi.

**Pour les joueurs:**

Les joueurs vivent une attente frustrante et imprévisible entre leurs matchs. Ils n'ont aucune visibilité sur:
- Quand ils vont jouer
- Combien de temps ils doivent attendre
- Contre qui ils vont affronter
- Leur position dans le tableau
- Le déroulement global du tournoi

Même quand un club partage l'Excel sur une TV (rare), les joueurs doivent rester à proximité et déchiffrer un tableau peu lisible. Ils sont réduits à demander constamment au JAP "quand est-ce que je joue?", ce qui crée une charge mentale des deux côtés et une expérience dégradée.

### Problem Impact

**Impact pour les JAP:**
- **Mobilité entravée**: Impossible de gérer efficacement depuis le terrain, coincés devant un ordi
- **Charge cognitive**: Parcourir l'Excel constamment pour répondre aux joueurs
- **Complexité inutile**: Les templates FFT sont lourds et difficiles à manipuler
- **Expérience dégradée**: Passer du temps sur la logistique au lieu de l'arbitrage

**Impact pour les joueurs:**
- **Attente perçue longue**: Sans visibilité, chaque minute semble interminable
- **Frustration**: Devoir demander sans cesse au JAP
- **Incompréhension**: Difficulté à comprendre leur position dans le tableau
- **Désengagement**: Certains quittent le club entre leurs matchs et ratent leur convocation

**Impact sur l'écosystème padel:**
- Avec l'explosion du padel en France, les tournois se multiplient
- Les nouveaux JAP sont découragés par la complexité des outils actuels
- L'expérience joueur médiocre nuit à l'attractivité des tournois
- Le temps de gestion pourrait être utilisé pour améliorer la qualité de l'arbitrage

### Why Existing Solutions Fall Short

**Excel / Google Sheets:**
- ❌ Conçu pour un bureau, pas pour la mobilité
- ❌ Interface inadaptée sur mobile (écran trop petit)
- ❌ Rendu visuel médiocre, difficilement lisible
- ❌ Navigation chaotique entre onglets/cellules
- ❌ Reproduction manuelle des tableaux complexe
- ❌ Aucune expérience pour les joueurs

**Templates FFT (papier/numériques):**
- ❌ Grands documents complexes et peu pratiques
- ❌ Difficiles à utiliser efficacement
- ❌ Pas de mobilité, pas de temps réel
- ❌ Aucune visibilité pour les joueurs

**Applications de réservation (Anybuddy, Ten'Up, etc.):**
- ✅ Gèrent bien l'inscription
- ❌ S'arrêtent après l'inscription
- ❌ Aucune fonctionnalité de gestion du tournoi
- ❌ Vide complet après que les joueurs ont payé

**Padel Club (solution payante existante):**
- ✅ Comble partiellement le vide
- ❌ Payant - barrière à l'adoption
- ❌ Fonctionnalités limitées (à confirmer - non testé)
- ❌ Expérience joueur potentiellement limitée

**Le gap identifié:**
Il existe un **vide béant** entre "inscription terminée" et "gestion du tournoi le jour J". Les JAP retombent sur Excel/papier manuellement, alors que tout le reste de l'écosystème padel se digitalise.

### Proposed Solution

**jap-assistant** est une application web **mobile-first** qui transforme la gestion des tournois de padel en une expérience fluide et intuitive pour les JAP et les joueurs.

**Pour les JAP - Avant le tournoi:**

1. **Import automatisé**: Import CSV des joueurs inscrits (depuis app de réservation)
2. **Récupération auto classements**: Parsing des PDFs FFT mensuels pour récupérer les classements automatiquement (matching nom/prénom/ligue)
3. **Configuration en quelques clics**: Type de tournoi, nombre de terrains, règles FFT
4. **Génération automatique**: Tableaux propres, tirages au sort, horaires de convocation calculés
5. **QR Code prêt**: À partager aux joueurs immédiatement

**Pour les JAP - Le jour J:**

- **Mobilité totale**: Gestion depuis le téléphone, proche des terrains et des joueurs
- **Saisie simple**: Résultats des matchs en quelques taps
- **Lancement flexible**: Choisir n'importe quel match à lancer sur n'importe quel terrain (pas forcément le prochain de la liste)
- **Lisibilité instantanée**: Interface claire montrant qui joue, pour quelles places, sur quel terrain - le "moment magique" vs le chaos Excel
- **Mise à jour automatique**: Tableaux et prochains matchs se mettent à jour en temps réel

**Pour les joueurs - Le jour J:**

1. **Accès sans friction**: Scanner le QR Code unique partagé par le JAP
2. **Vue publique par défaut**: Tableaux complets, matchs en cours, classements temps réel
3. **Identification optionnelle** (facultatif): "Je suis Martin" → Vue personnalisée
   - Prochain match dans X matchs (~25 min)
   - Adversaires
   - Terrain
   - Enjeu (places 5-6, demi-finale, etc.)
4. **Visibilité totale**: Parcours dans le tournoi, classement temps réel, matchs en cours
5. **Attente prévisible**: Timer estimé basé sur durée moyenne des matchs précédents

**Architecture technique retenue:**

- **Web application responsive**: Fonctionne sur ordi (préparation) et mobile (jour J)
- **QR Code unique**: Pas de comptes, pas de téléchargements
- **Temps réel**: Mise à jour instantanée pour tous les utilisateurs
- **Parsing PDF FFT**: Solution retenue pour récupération classements (vs API Tenup bloquée par CAPTCHA/Cloudflare)
- **Gratuit & open source** (à terme): Accessible à tous les JAP

### Key Differentiators

**1. Double perspective unique:**
- Conçu par un joueur qui devient JAP
- Comprend les frustrations des DEUX côtés
- Résout les problèmes JAP ET joueur dans une seule expérience

**2. Mobile-first par design:**
- Pas un Excel adapté au mobile, mais une app conçue pour le mobile dès le départ
- Interface optimisée pour saisie rapide sur le terrain
- Lisibilité instantanée vs parcours chaotique dans des onglets

**3. Gratuit & accessible:**
- Aucune barrière financière à l'adoption
- Vise l'accessibilité maximale pour tous les JAP
- Open source à terme pour la communauté padel

**4. Expérience joueur intégrée:**
- Pas juste un outil JAP avec une "vue publique" afterthought
- L'expérience joueur est un pilier de la conception
- QR Code sans friction (0 compte, 0 téléchargement)
- Visibilité temps réel qui réduit la frustration de l'attente

**5. Simplicité radicale:**
- Import/config pré-tournoi en quelques minutes vs heures sur Excel
- Interface épurée qui montre l'essentiel instantanément
- Le "moment magique" = comprendre en 2 secondes qui joue, où, pourquoi

**6. Timing parfait:**
- Le padel explose en France, les tournois se multiplient
- Nouvelle génération de JAP à convaincre (moins attachés à Excel)
- Gap énorme non comblé entre réservation et gestion tournoi
- Les outils actuels ne scalent pas avec la croissance du padel

**7. Fonctionnalités JAP avancées:**
- Lancement flexible des matchs (n'importe quel match, n'importe quel terrain)
- Gestion forfaits conforme FFT
- Export CSV pour outils FFT (réduction double saisie)
- Mode affichage public TV (remplace Excel partagé)

**Unfair advantage difficile à copier:**
- La double casquette joueur + JAP qui informe chaque décision UX
- Le focus gratuit & communautaire vs solutions commerciales
- La compréhension intime des frustrations terrain (pas juste théorique)

---

## Target Users

### Primary Users

#### Persona 1: Thomas - Le JAP Débutant Passionné

**Profil:**
- 30 ans, ancien professeur de tennis reconverti en prof de padel
- Devenu JAP il y a 6 mois après formation FFT
- Membre actif du club, gère 10-20 tournois par an
- Transition tennis → padel il y a 3 ans, "accro comme beaucoup de joueurs"

**Contexte d'utilisation:**
Pendant un tournoi, Thomas est installé à une table avec son laptop Excel ouvert. Il se déplace régulièrement pour aller voir les joueurs sur les terrains, mais doit constamment revenir à sa table pour consulter et mettre à jour ses feuilles. Navigation chaotique entre onglets, zoom/dézoom pour lire les cellules sur son écran.

**Problème vécu:**
Thomas est stressé AVANT le tournoi (création du tableau, tirages au sort) et PENDANT (gestion des matchs). Sa plus grande peur: **faire une erreur dans le tableau qui invaliderait le tournoi** - attribuer de mauvais points FFT, créer des rencontres qui n'auraient pas dû avoir lieu, ne pas respecter les règles complexes de la FFT. Chaque question d'un joueur le distrait et augmente le risque d'erreur de saisie.

**Pain Points:**
- "Est-ce que mon tirage au sort respecte TOUTES les règles FFT?"
- "Impossible de vérifier le tableau depuis le terrain, je dois retourner à ma table"
- "Les joueurs me demandent sans cesse 'quand je joue?' alors que je dois me concentrer"
- "Si je me trompe, je peux impacter les classements FFT de dizaines de joueurs"

**Success Vision:**
Thomas rêve d'un outil qui:
1. **Le rassure sur la conformité FFT** (tirage au sort validé automatiquement)
2. **Lui donne la mobilité** pour gérer depuis son téléphone sur le terrain
3. **Réduit les interruptions** des joueurs qui ont l'info en temps réel
4. **Minimise le risque d'erreur** avec une interface claire et des validations automatiques

**Citation typique:**
_"J'adore organiser des tournois, mais j'ai toujours cette boule au ventre: 'et si je me suis trompé dans le tableau?'. Et rester collé à mon ordi alors que je devrais être avec les joueurs, c'est frustrant."_

---

#### Persona 2: Philippe - Le JAP Expérimenté Pragmatique

**Profil:**
- 48 ans, membre du bureau de l'association du club depuis 12 ans
- JAP depuis 8 ans, gère 15-20 tournois par an
- Maîtrise Excel, a développé ses propres templates au fil des années
- Ouvert aux nouvelles solutions si elles sont gratuites et vraiment meilleures

**Contexte d'utilisation:**
Philippe a son workflow Excel bien rodé. Il connaît ses feuilles par cœur, a ses raccourcis, ses formules. Mais il reconnaît les limites: mobilité nulle, partage compliqué, joueurs qui demandent constamment. Il a entendu parler de Padel Club mais refuse de payer pour un outil qu'il gère déjà "gratuitement" avec Excel.

**Problème vécu:**
Après des années, Philippe sent que **son système ne scale plus** avec la croissance du padel. Plus de tournois, plus de joueurs, plus de questions. Il passe autant de temps à répondre aux joueurs qu'à gérer le tournoi. Il sait qu'une solution moderne existe, mais il veut quelque chose de gratuit, simple à adopter, et qui ne le rende pas dépendant d'un outil payant.

**Pain Points:**
- "Excel fonctionne, mais je suis prisonnier de mon ordinateur"
- "Je pourrais payer Padel Club, mais pourquoi payer pour quelque chose que je fais déjà?"
- "Les nouveaux JAP du club galèrent avec mes Excel - il faudrait quelque chose de plus simple"
- "Partager l'Excel sur la TV du club, c'est bricolé et pas terrible"

**Success Vision:**
Philippe adopterait une solution si elle:
1. **Reste gratuite** (ou open source à terme)
2. **Ne complique pas** son workflow actuel (import/export facile)
3. **Apporte un vrai plus** (mobilité, expérience joueur, moins de questions)
4. **Peut devenir un standard** (potentiel outil officiel FFT = gage de pérennité)

**Citation typique:**
_"Excel fonctionne depuis 8 ans, mais je vois bien que les joueurs veulent plus. Si un outil gratuit me donne la mobilité et réduit les questions, je suis preneur. Mais je ne paierai pas pour ça."_

---

### Secondary Users

#### Persona 3: Clément - Le Joueur Compétitif Impatient

**Profil:**
- 30 ans, joueur classé P1000 (15 selon nouveau système FFT)
- Joue ~2 tournois par mois = 20 tournois par an
- Participe en paire, parfois avec sa compagne et enfants mais c'est rare (tournoi trop long)
- Arrive toujours 10 minutes avant sa convocation

**Contexte d'utilisation:**
Clément arrive au club, fait son premier match, puis **entre dans une période d'attente floue**. Il regarde d'autres matchs, prend un café, discute avec d'autres joueurs, mais **ne sait jamais précisément quand il va rejouer**. Entre chaque match, il va voir le JAP: _"Je joue quand? Sur quel terrain?"_. Réponse typique: _"Vous jouez le prochain match sur le 2"_ - mais "le prochain" peut être dans 10 minutes ou 40 minutes selon la durée du match en cours.

**Problème vécu:**
L'attente est **imprévisible et mentalement fatigante**. Clément reste au club toute la journée jusqu'à ses derniers matchs (il part avant la finale s'il n'y est pas). Impossible de vraiment se détendre, toujours dans l'incertitude. Quand il amène sa compagne et ses enfants (rare), c'est encore pire: ils s'ennuient et ça dure plusieurs heures.

**Pain Points:**
- "Je ne sais jamais combien de temps j'ai avant mon prochain match"
- "Je dois interrompre le JAP alors qu'il est occupé juste pour savoir si je joue bientôt"
- "Impossible de quitter le club pour aller manger - et si mon match avance?"
- "L'attente semble interminable quand on ne sait pas combien de temps ça va durer"
- "Quand je viens avec ma famille, c'est long pour eux et je me sens coupable"

**Success Vision:**
Clément voudrait:
1. **Savoir en temps réel** combien de matchs avant le sien (~combien de temps)
2. **Voir le tableau en direct** sur son téléphone sans déranger le JAP
3. **Comprendre son parcours** dans le tournoi (pour quelle place il joue)
4. **Planifier son attente** (temps pour un café? pour aller manger?)

**Citation typique:**
_"Attendre, ça va. Mais attendre sans savoir COMBIEN DE TEMPS, c'est épuisant mentalement. Je reste scotché au club toute la journée 'au cas où'. Si je pouvais juste voir 'ton match dans 2 matchs, ~25 min', je pourrais me détendre."_

---

**Stakeholder Stratégique: FFT (Fédération Française de Tennis)**

**Relation:**
- **Court terme**: Pas d'interaction directe
- **Moyen terme**: jap-assistant devient un outil reconnu dans l'écosystème padel français
- **Long terme**: Ambition de devenir un outil officiel FFT (gratuit, communautaire, aligné avec les règles FFT)

**Valeur pour la FFT:**
- Outil qui respecte et applique rigoureusement les règles FFT
- Améliore l'expérience des tournois = attractivité du padel compétitif
- Solution gratuite et accessible = démocratisation de la gestion des tournois
- Réduction des erreurs de gestion qui impactent les classements FFT

---

### User Journey

#### Journey du JAP (Primary User)

**Phase 1 - Préparation (24-48h avant le tournoi):**

1. **Import des joueurs** (5 min au lieu de 2h)
   - Reçoit CSV depuis app de réservation (Anybuddy, Ten'Up)
   - Import en un clic dans jap-assistant
   - Récupération automatique des classements FFT via parsing PDF (matching nom/prénom/ligue)
   - Validation visuelle des joueurs et classements
   - **"Aha moment #1"**: "Wow, je viens d'importer 48 joueurs en 2 minutes au lieu de passer 2h à tout saisir manuellement"

2. **Configuration du tournoi** (10 min au lieu de 1h)
   - Type de tableau (final, ligne, section, poules)
   - Nombre de terrains disponibles
   - Génération automatique selon règles FFT
   - **Validation conformité FFT automatique** ✓
   - **"Aha moment #2"**: "Le système me dit que mon tirage respecte toutes les règles FFT - je peux dormir tranquille"

3. **QR Code et partage**
   - QR Code généré automatiquement
   - Prêt à partager sur WhatsApp groupe / affiches club
   - **"Aha moment #3"**: "Les joueurs vont avoir l'info en temps réel, ils vont arrêter de me déranger toutes les 5 minutes"

**Phase 2 - Le Jour J (pendant le tournoi):**

4. **Mobilité totale**
   - Ouvre jap-assistant sur son téléphone
   - Interface mobile optimisée, lisible instantanément
   - Proche des terrains, proche des joueurs
   - **"Moment magique"**: "Je vois d'un coup d'œil qui joue, sur quel terrain, pour quelles places. Plus besoin de parcourir mes onglets Excel."

5. **Gestion fluide des matchs**
   - Lance n'importe quel match sur n'importe quel terrain (flexibilité totale)
   - Saisie résultats en quelques taps
   - Tableaux et prochains matchs mis à jour automatiquement en temps réel
   - **Sérénité**: Moins d'interruptions des joueurs, ils ont l'info sur leur téléphone

6. **Fin du tournoi**
   - Export CSV pour outils FFT (réduction double saisie)
   - Données du tournoi sauvegardées pour historique

**Phase 3 - Long terme:**

7. **Adoption et recommandation**
   - Parle de l'outil aux autres JAP du club et de la ligue
   - "C'est gratuit, c'est mobile, les joueurs adorent - essayez-le"
   - Contribue au feedback pour améliorer l'outil

---

#### Journey du Joueur (Secondary User)

**Phase 1 - Avant le tournoi:**

1. **Inscription** via app de réservation habituelle (Anybuddy, Ten'Up, etc.)
2. **Découverte de jap-assistant** via communication du JAP/club
   - Message WhatsApp groupe avec QR Code
   - Affiche au club avec QR Code
   - Bouche-à-oreille entre joueurs

**Phase 2 - Le Jour du tournoi:**

3. **Arrivée au club** (10 min avant convocation)
   - Scanne le QR Code avec son téléphone
   - **Accès instantané** sans compte, sans téléchargement
   - Voit les tableaux complets, matchs en cours, classement temps réel

4. **Après son premier match - L'attente**
   - **Avant jap-assistant**: Va voir le JAP, "Je joue quand? Quel terrain?"
   - **Avec jap-assistant**: Regarde son téléphone
     - "Ton prochain match dans 2 matchs (~25 min)"
     - Adversaires: Martin/Dupont
     - Enjeu: Places 5-6
     - Terrain: Court 3
   - **"Moment magique"**: "Je sais COMBIEN DE TEMPS j'ai. Je peux aller boire un café tranquillement."

5. **Entre les matchs (attente prévisible)**
   - Regarde les autres matchs en cours (sur le terrain ou sur son téléphone)
   - Suit l'évolution du tableau en temps réel
   - Voit son parcours dans le tournoi
   - **Frustration de l'attente réduite**: L'attente est prévisible, donc moins stressante

6. **Fin de ses matchs**
   - Part avant la finale (sauf s'il y est)
   - Peut continuer à suivre le tournoi depuis chez lui s'il le souhaite

**Phase 3 - Après le tournoi:**

7. **Adoption future**
   - Demande aux JAP des prochains tournois: "Vous utilisez jap-assistant?"
   - Parle de l'outil aux autres joueurs
   - Attend avec impatience que tous les JAP l'adoptent

---

## Success Metrics

### User Success Metrics

**Pour les JAP (Primary Users):**

**Métriques de valeur immédiate:**
- **Gain de temps préparation**: Import + configuration < 15 minutes (vs 2-3h actuellement)
- **Réduction du stress**: Validation automatique conformité FFT = 0 erreur de tableau
- **Mobilité opérationnelle**: 100% des saisies résultats depuis mobile (vs 0% avec Excel)
- **"Aha moments" atteints**:
  - Moment #1 (import): < 5 min pour importer 48 joueurs
  - Moment #2 (validation): Confirmation conformité FFT automatique
  - Moment #3 (mobilité): Gestion complète depuis terrain via mobile

**Métriques de succès à long terme:**
- **Adoption première utilisation**: JAP réussit son premier tournoi sans blocage
- **Utilisation répétée**: 90% des JAP reviennent pour un 2e tournoi
- **Abandon Excel mesuré**: (Tournois gérés dans jap-assistant / Total tournois organisés par le club) > 80%
- **Fréquence d'usage**: 12 tournois/an par JAP en moyenne
- **Recommandation**: 1 JAP actif amène au moins 1 nouveau JAP
- **Adoption club**: Club impose l'outil pour tous ses tournois

**Indicateurs comportementaux:**
- JAP crée un tournoi et le mène à terme sans support
- JAP utilise l'app pour 100% de ses tournois après la première utilisation
- JAP recommande activement l'outil à d'autres JAP de la ligue

---

**Pour les Joueurs (Secondary Users):**

**Métriques d'engagement:**
- **Taux de scan QR Code**: > 60% des joueurs scannent le QR Code
- **Fréquence de consultation**: Joueur consulte en moyenne 3-5 fois pendant le tournoi
- **Engagement actif**: > 50% des consultations = clics actifs (pas juste vue rapide)
- **Réduction interruptions JAP**: < 30% des joueurs demandent "quand je joue?" vs 100% actuellement

**Métriques de satisfaction:**
- **Perception attente**: Joueurs déclarent que l'attente "passe plus vite" / "est plus prévisible"
- **Retour positif**: Joueurs demandent aux JAP "Vous utilisez jap-assistant?" pour prochains tournois
- **Bouche-à-oreille**: Joueurs parlent positivement de l'expérience à d'autres joueurs

---

### Business Objectives

**Phase 1 - Validation locale (Mois 1-3):**

**Objectif:** Prouver que le produit fonctionne et crée de la valeur

**Métriques clés:**
- **Adoption initiale**: 4-5 JAP utilisateurs actifs
- **Volume**: 2-3 tournois minimum par JAP = 8-15 tournois total
- **Satisfaction**: > 80% des JAP satisfaits (feedback qualitatif)
- **Rétention première période**: 80% des JAP reviennent pour un 2e tournoi
- **Zones géographiques**: Clubs de la ligue locale

**Jalons de succès:**
- ✅ Au moins 1 JAP utilise l'app pour 100% de ses tournois
- ✅ 0 erreur bloquante reportée pendant tournois
- ✅ Feedback positif des joueurs sur visibilité temps réel
- ✅ Au moins 1 club envisage d'imposer l'outil

---

**Phase 2 - Croissance régionale (Mois 4-12):**

**Objectif:** Devenir l'outil de référence dans la ligue

**Métriques clés:**
- **Adoption clubs**: 5 clubs actifs dans la ligue
- **Pénétration marché**: 15% des JAP de la ligue utilisent l'outil
- **Volume**: 100-150 tournois gérés sur l'année
- **Rétention**: 90% des JAP utilisent l'outil pour chaque tournoi
- **Croissance organique**: 1 JAP actif amène 1 nouveau JAP minimum
- **Clubs ambassadeurs**: Au moins 2 clubs imposent l'usage de l'outil

**Jalons de succès:**
- ✅ Un club de référence utilise exclusivement jap-assistant
- ✅ Bouche-à-oreille positif entre JAP de différents clubs
- ✅ Demandes inbound de JAP qui découvrent l'outil via joueurs
- ✅ 0 retour à Excel après adoption

---

**Phase 3 - Objectif FFT (Mois 12+):**

**Objectif:** Préparer le dossier pour devenir outil officiel FFT

**Métriques jalons:**
- **Adoption critique**: 20% des JAP de padel en France utilisent l'outil
- **Satisfaction démontrée**: 90% de satisfaction utilisateurs
- **Volume démontré**: 500+ tournois gérés avec succès
- **Conformité FFT**: 100% respect des règles FFT (validation automatique)
- **Réduction erreurs**: Démontrer réduction significative erreurs vs Excel
- **Expérience joueur**: Feedback positif joueurs documenté

**Conditions d'approche FFT:**
- Outil stable, testé sur des centaines de tournois
- Cas d'usage documentés avec témoignages JAP
- Démonstration d'amélioration qualité gestion tournois
- Proposition de gratuité ou modèle économique adapté

---

### Key Performance Indicators (KPIs)

**KPIs Adoption & Engagement:**

**Mois 1-3 (Validation):**
- JAP actifs: 4-5
- Tournois gérés: 8-15
- Taux de rétention 2e tournoi: > 80%
- Satisfaction: > 80%

**Mois 4-6 (Croissance précoce):**
- JAP actifs: 10-12
- Clubs actifs: 3
- Tournois gérés: 40-60 cumulé
- Taux de rétention: > 85%
- Recommandation: 50% des JAP ont amené 1+ nouveau JAP

**Mois 7-12 (Scale régional):**
- JAP actifs: 15-20 (15% des JAP de la ligue)
- Clubs actifs: 5
- Tournois gérés: 100-150 cumulé
- Taux de rétention: 90%
- Clubs ambassadeurs: 2 (imposent l'usage)

**Année 2 (Expansion):**
- JAP actifs: 50-100
- Pénétration nationale: 5-10% des JAP padel France
- Tournois gérés: 500+
- Préparation dossier FFT

---

**KPIs Techniques & Qualité:**

- **Disponibilité**: > 99% uptime pendant tournois (weekends critiques)
- **Performance mobile**: Chargement pages < 2 secondes
- **Erreurs bloquantes**: 0 erreur empêchant de terminer un tournoi
- **Conformité FFT**: 100% des tableaux générés respectent règles FFT
- **Support utilisateur**: Temps de réponse < 24h sur questions/bugs

---

**KPIs Financiers & Viabilité:**

- **Coût d'hébergement**: < 150€/mois (base + back + front)
- **Coût par tournoi**: < 1€/tournoi en moyenne (objectif scale)
- **Donations**: À partir mois 6-12, objectif couvrir 20-30% des coûts via donations
- **Modèle long terme**: Revente ou licensing à FFT (gratuit pour utilisateurs finaux)

---

**KPIs Stratégiques (Vers FFT):**

- **Couverture géographique**: Présent dans au moins 5 ligues régionales
- **Légitimité**: Au moins 1 ligue régionale recommande officiellement l'outil
- **Documentation**: Cas d'usage documentés avec retours JAP et joueurs
- **Écosystème**: Intégration avec apps de réservation (Anybuddy, Ten'Up) testée
- **Communauté**: Base utilisateurs actifs prêts à témoigner valeur ajoutée

---

### Métriques de Succès Connectées à la Vision

**Lien Vision → Métriques Utilisateur → Métriques Business:**

1. **Vision**: Libérer les JAP d'Excel et donner visibilité aux joueurs
   - **Métrique utilisateur**: 90% des JAP abandonnent Excel, 60%+ joueurs scannent QR
   - **Métrique business**: 15% pénétration ligue = outil devient standard

2. **Vision**: Solution gratuite et accessible
   - **Métrique utilisateur**: 0 barrière financière adoption
   - **Métrique business**: Budget < 150€/mois, modèle donations + FFT

3. **Vision**: Outil officiel FFT à terme
   - **Métrique utilisateur**: 90% satisfaction + 100% conformité FFT
   - **Métrique business**: 20% JAP France + dossier solide pour approche FFT

4. **Vision**: Mobile-first et simplicité radicale
   - **Métrique utilisateur**: 100% saisies depuis mobile + "moment magique" atteint
   - **Métrique business**: Adoption organique 1:1, clubs imposent l'usage

---

**Anti-Vanity Metrics:**

**Métriques à ÉVITER (ne conduisent pas à des décisions):**
- ❌ Nombre de visites site web
- ❌ Nombre de comptes créés (pas de comptes!)
- ❌ Temps passé sur l'app (ne mesure pas la valeur)
- ❌ Pages vues (vanity metric sans contexte)

**Focus sur les métriques qui comptent:**
- ✅ Tournois menés à terme avec succès
- ✅ JAP qui reviennent et recommandent
- ✅ Clubs qui adoptent et imposent l'usage
- ✅ Abandon d'Excel mesurable
- ✅ Satisfaction démontrable pour dossier FFT

---

## MVP Scope

### Core Features (Must-Have for Launch)

Le MVP de **jap-assistant** comprend **18 fonctionnalités essentielles** organisées par phase d'utilisation. Ces features permettent de délivrer la proposition de valeur complète pour les JAP et les joueurs dès le lancement.

---

#### Phase Préparation (Avant le tournoi)

**1. Import CSV des joueurs inscrits**
- Import automatisé depuis apps de réservation (Anybuddy, Ten'Up, etc.)
- Mapping automatique des colonnes (nom, prénom, classement, ligue, email optionnel)
- Validation des données importées
- Édition manuelle possible pour corrections

**2. Récupération automatique des classements via parsing PDF FFT**
- Téléchargement mensuel des PDFs de classement FFT
- Parsing automatique et extraction des données (nom, prénom, ligue, classement)
- Matching automatique avec joueurs importés (nom + prénom + ligue)
- Gestion des cas ambigus (homonymes) avec validation manuelle
- Mise en cache des classements pour réutilisation

**3. Protection contre tournois sur dates du calendrier FFT**
- Vérification automatique que la date du tournoi ne chevauche pas un événement calendrier FFT
- Alerte si conflit détecté (tournoi régional, national, championnat)
- Blocage ou warning selon la criticité du conflit
- Lien vers calendrier FFT officiel pour consultation

**4. Configuration du tournoi**
- Type de tableau (final, ligne, section, poules)
- Nombre de terrains disponibles
- Règles FFT applicables selon le type
- Paramètres personnalisables (durée match estimée, temps entre matchs)
- Sauvegarde de configurations réutilisables

**5. Génération automatique des tableaux selon règles FFT**
- Tirage au sort conforme FFT (têtes de série, répartition géographique)
- Validation automatique conformité FFT (rules engine)
- Génération des matchs de qualification, tableau principal, tableau secondaire
- Calcul des horaires de convocation
- Visualisation claire des tableaux générés

**6. Génération d'un QR Code unique pour accès joueurs**
- QR Code généré automatiquement à la création du tournoi
- URL unique et sécurisée pour chaque tournoi
- Téléchargeable en haute résolution (affiche club)
- Partageable directement via WhatsApp, email, etc.
- QR Code actif pendant toute la durée du tournoi + quelques jours après

---

#### Phase Jour J - Côté JAP

**7. Interface mobile optimisée pour saisie et gestion**
- Design mobile-first responsive
- Lisibilité instantanée (qui joue, où, pour quelles places)
- Navigation intuitive entre tableaux, matchs en cours, prochains matchs
- Interface optimisée pour utilisation terrain (gros boutons, contraste élevé)
- Gestion hors-connexion partielle (saisie résultats en cache si coupure réseau)

**8. Saisie rapide des résultats de matchs**
- Formulaire simple et rapide (scores par set)
- Validation automatique des scores (cohérence FFT)
- Correction possible en cas d'erreur
- Historique des modifications pour traçabilité
- Confirmation visuelle de la saisie

**9. Lancement flexible des matchs (n'importe quel match sur n'importe quel terrain)**
- Liste des matchs prêts à être lancés
- Choix libre du match à lancer (pas forcément le prochain de la liste)
- Assignation libre du terrain disponible
- Optimisation suggérée (match prioritaire, terrain optimal) mais pas imposée
- Gestion des retards et ajustements en temps réel

**10. Gestion des forfaits conforme FFT**
- Déclaration forfait avant match ou pendant match
- Application automatique des règles FFT (adversaire qualifié, points attribués)
- Mise à jour instantanée des tableaux
- Traçabilité des forfaits pour export FFT
- Gestion des cas particuliers (forfait équipe entière, forfait partiel)

**11. Mise à jour temps réel des tableaux et matchs**
- Synchronisation instantanée de tous les clients connectés
- Push notifications côté joueurs lors de changements importants
- Rafraîchissement automatique sans rechargement page
- Indicateurs visuels de mise à jour (animation, badge "nouveau")
- Gestion des conflits de saisie simultanée (rare mais possible)

**12. Mode affichage public sur TV/écran club**
- Interface d'affichage optimisée grand écran
- Rotation automatique entre tableaux, matchs en cours, classement
- QR Code visible en permanence sur l'écran
- Lisibilité à distance (polices grandes, couleurs contrastées)
- Mode plein écran sans éléments de navigation

---

#### Phase Jour J - Côté Joueurs

**13. Accès via scan QR Code sans création de compte**
- Scan QR Code → accès instantané
- Aucun téléchargement, aucune installation
- Aucune création de compte, aucune authentification
- Fonctionne sur tous les smartphones (iOS, Android)
- Accès persistant pendant toute la durée du tournoi

**14. Consultation des tableaux en temps réel**
- Vue complète des tableaux (principal, secondaire, qualification)
- Mise à jour en temps réel sans rechargement
- Navigation intuitive entre tableaux
- Zoom et navigation tactile fluide
- Recherche rapide d'un joueur dans les tableaux

**15. Vue des matchs en cours et prochains matchs**
- Liste des matchs en cours avec scores live
- Liste des prochains matchs à venir
- Terrain assigné visible pour chaque match
- Temps estimé avant début (basé sur durée moyenne matchs précédents)
- Indicateur visuel "ton match" pour joueurs identifiés

**16. Timer estimé avant son prochain match**
- Calcul dynamique basé sur durée moyenne des matchs en cours
- Affichage "ton prochain match dans X matchs (~Y min)"
- Mise à jour en temps réel si durée des matchs varie
- Notification push quand match approche (optionnel)
- Marge de sécurité intégrée pour éviter les retards

**17. Notifications push pour les joueurs (match bientôt, match lancé)**
- Opt-in notification lors du premier accès
- Notification "Ton match commence dans 15 min" (configurable)
- Notification "Ton match est lancé sur le terrain X"
- Notification "Ton match suivant est prêt" après victoire
- Désactivation possible à tout moment

---

#### Phase Après le tournoi

**18. Export CSV pour outils FFT (réduction double saisie)**
- Export CSV conforme format FFT
- Toutes les données nécessaires: résultats, forfaits, points attribués
- Téléchargement direct depuis l'app
- Nom de fichier normalisé (date, nom tournoi, type)
- Conservation des données pour historique JAP

---

### Out of Scope for MVP (Version 2+)

Les fonctionnalités suivantes sont **intentionnellement exclues du MVP** pour garantir un lancement rapide et focalisé sur les use cases critiques. Elles seront évaluées et priorisées pour les versions ultérieures en fonction des retours utilisateurs.

**V2.1 - Identification joueur et personnalisation**
- Identification joueur "Je suis Martin" pour vue personnalisée
- Historique personnel des matchs du joueur dans le tournoi
- Statistiques personnelles (ratio victoires, sets gagnés/perdus)
- Parcours détaillé dans le tournoi avec graphe visuel

**V2.2 - Historique et statistiques long terme**
- Historique des tournois précédents pour un JAP
- Statistiques sur plusieurs tournois (taux de forfaits, durée moyenne, etc.)
- Réutilisation de configurations de tournois passés
- Export et analyse de données agrégées

**V2.3 - Gestion dynamique des terrains**
- Déclaration de terrain indisponible temporairement (maintenance, nettoyage)
- Réorganisation automatique des matchs selon terrains disponibles
- Optimisation suggestion terrain selon contraintes (lumière, qualité surface, etc.)

**V2.4 - Convocations automatiques par email/SMS**
- Envoi automatique des convocations par email avant le tournoi
- Rappel SMS le jour J avant le premier match
- Notifications personnalisées selon préférences joueur
- Intégration avec services d'envoi (Twilio, SendGrid, etc.)

**V2.5 - Mode hors-ligne complet**
- Fonctionnement 100% hors-ligne pour JAP (PWA)
- Synchronisation automatique lors du retour en ligne
- Gestion des conflits de synchronisation
- Cache local des données joueurs et classements

**V2.6 - Intégrations directes avec apps de réservation**
- API directe avec Anybuddy, Ten'Up, etc.
- Import automatique en temps réel (pas de CSV manuel)
- Synchronisation bidirectionnelle (résultats → app réservation)
- Single Sign-On pour JAP (si app réservation supporte)

---

### MVP Success Criteria

Le MVP sera considéré comme **réussi** si les trois critères de validation suivants sont atteints:

#### Gate 1: Validation Utilisateur (Mois 1-3)

**Critère de succès:**
- **4-5 JAP actifs** utilisent l'outil pour au moins 2 tournois chacun
- **Satisfaction > 80%** (feedback qualitatif + NPS)
- **0 blocage critique** empêchant de terminer un tournoi
- **60%+ des joueurs** scannent le QR Code et consultent l'app
- **Au moins 1 JAP** utilise l'app pour 100% de ses tournois

**Questions de validation:**
- Le JAP peut-il préparer et gérer un tournoi complet sans support externe?
- Les joueurs trouvent-ils la vue temps réel utile et claire?
- Y a-t-il des bugs bloquants ou des features manquantes critiques?

**Décision:**
- ✅ **PASS**: Continuer vers Phase 2 (croissance régionale)
- ⚠️ **PIVOT**: Ajuster features ou UX selon feedback avant scale
- ❌ **FAIL**: Retour à la conception (rare, signale problème fondamental)

---

#### Gate 2: Validation Technique (Mois 1-3)

**Critère de succès:**
- **Uptime > 99%** pendant les weekends (heures critiques tournois)
- **0 erreur conformité FFT** sur les tableaux générés
- **Performance mobile < 2s** chargement pages
- **Synchronisation temps réel** fonctionne sans latence perceptible
- **Parsing PDF FFT** atteint > 95% de matching automatique correct

**Questions de validation:**
- L'infrastructure tient-elle la charge de 5 tournois en parallèle?
- Les règles FFT sont-elles correctement implémentées et validées?
- Y a-t-il des problèmes de performance sur mobile 4G en conditions réelles?

**Décision:**
- ✅ **PASS**: Infrastructure stable pour scale
- ⚠️ **OPTIMISE**: Corrections techniques nécessaires avant croissance
- ❌ **REFACTOR**: Architecture technique ne scale pas (rare)

---

#### Gate 3: Validation Business (Mois 3)

**Critère de succès:**
- **Budget < 150€/mois** pour héberger 8-15 tournois
- **Au moins 1 club** envisage d'imposer l'outil pour tous ses tournois
- **Croissance organique observée**: Au moins 1 JAP a amené un nouveau JAP
- **0 retour à Excel** après adoption (retention 100% pour JAP ayant fait 2+ tournois)

**Questions de validation:**
- Le modèle économique est-il soutenable à long terme?
- L'adoption organique fonctionne-t-elle (bouche-à-oreille)?
- L'outil crée-t-il suffisamment de valeur pour devenir standard dans un club?

**Décision:**
- ✅ **PASS**: Go pour Phase 2 avec stratégie croissance claire
- ⚠️ **ADJUST**: Modèle business ou stratégie croissance à revoir
- ❌ **STOP**: Product-market fit non atteint (rare si Gate 1 passé)

---

### Future Vision (Beyond MVP)

**Année 1 (Post-MVP):**
- Atteindre 15% de pénétration dans la ligue locale (15-20 JAP actifs)
- Devenir l'outil de référence dans au moins 2 clubs ambassadeurs
- Implémenter features V2 prioritaires selon feedback utilisateurs
- Commencer à documenter cas d'usage et témoignages pour dossier FFT

**Année 2:**
- Expansion à 3-5 ligues régionales (50-100 JAP actifs)
- Intégrations directes avec apps de réservation majeures
- Historique et statistiques long terme
- Budget donations couvrant 20-30% des coûts

**Année 3+:**
- Atteindre 20% des JAP de padel en France (objectif FFT)
- Dossier complet pour approche FFT (témoignages, métriques, conformité)
- Proposition de partenariat ou licensing officiel FFT
- Outil gratuit et accessible pérenne pour la communauté padel française

**Vision long terme:**
- **jap-assistant** devient l'outil officiel recommandé par la FFT pour la gestion des tournois de padel
- Gratuit pour les utilisateurs finaux, soutenu par la FFT ou via modèle communautaire
- Standard de l'écosystème padel français, intégré avec tous les outils FFT existants
- Contribue à l'amélioration de l'expérience tournois et à la croissance du padel compétitif en France

---