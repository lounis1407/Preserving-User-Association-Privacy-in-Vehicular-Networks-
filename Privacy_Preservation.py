import random
import pandas as pd
import math
import string
from cryptography.fernet import Fernet
#toutes les bibliothèques nécessaires pour le code
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import seaborn as sns

# 
# Configuration globale du réseau routier
# 
INTERSECTIONS = {
    "A": (10, 10),
    "B": (80, 10),
    "C": (80, 50),
    "D": (50, 80),
    "E": (10, 80)
}

ROUTES = {
    ("A", "B"): {"distance": 70.0, "type": "autoroute"},
    ("B", "C"): {"distance": 40.0, "type": "principale"},
    ("C", "D"): {"distance": 40.0, "type": "secondaire"},
    ("D", "E"): {"distance": 50.0, "type": "principale"},
    ("A", "E"): {"distance": 70.0, "type": "secondaire"}
}

# Rendre les routes bidirectionnelles
temp = list(ROUTES.items())
for (n1, n2), info in temp:
    if (n2, n1) not in ROUTES:
        ROUTES[(n2, n1)] = {"distance": info["distance"], "type": info["type"]}

VITESSE_MAX_PAR_TYPE = {
    "autoroute": 130.0,
    "principale": 80.0,
    "secondaire": 50.0
}

# 
# Configuration générale pour la simulation
# 
ZONE_X = 100
ZONE_Y = 100
PORTEE_CONNEXION_LOCALE = 300
PORTEE_CONNEXION_LONGUE = 600

COUT_FIXE = 2.0
COUT_DISTANCE = 0.1
TEMPS_BASE = 1.0
TEMPS_PAR_UNITE = 0.05
TEMPS_FIABILITE_FACTOR = 0.3
TEMPS_CONGESTION_FACTOR = 0.2

SEUIL_SUSPICION = 2
SEUIL_ENERGIE_REFUS = 5.0
SEUIL_ENERGIE_ADAPTATION = 30.0

DUREE_CONGESTION = 3

# Clé de chiffrement partagée
cle_secrete = Fernet.generate_key()
cipher = Fernet(cle_secrete)

def generer_pseudonyme():
    """Génère un pseudonyme aléatoire de 6 caractères."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# 
# Classe Antenne
# 
class Antenne:
    PRIORITY_MAPPING = {
        "Urgence": 3,
        "Mise à jour de trafic": 2,
        "Standard": 1
    }
    
    MAX_CONNEXIONS = 5  # Limite maximale de connexions simultanées par antenne

    def __init__(self, id, fiabilite, x, y, type_antenne="locale", disponible=True):
        self.id = id
        self.fiabilite = fiabilite
        self.x = x
        self.y = y
        self.type_antenne = type_antenne
        self.portee_base = PORTEE_CONNEXION_LOCALE if type_antenne == "locale" else PORTEE_CONNEXION_LONGUE
        self.portee = self.portee_base
        self.disponible = disponible

        # Gestion de la congestion
        self.congestion = 0
        self.historique_congestion = {}

        # Gestion des défaillances
        self.probabilite_panne = 0.05  # Probabilité de tomber en panne à chaque étape
        self.duree_panne_max = 5       # Durée maximale d'une panne
        self.panne_duree_restante = 0   # Durée restante de la panne actuelle

        # File d'attente des connexions
        self.connexion_queue = []

        # Gestion des connexions actives
        self.active_connections = 0
        self.total_connections = 0  #  

    def recevoir_message(self, message_chiffre):
        message = cipher.decrypt(message_chiffre).decode()
        return message

    def tomber_en_panne(self):
        self.disponible = False
        self.panne_duree_restante = random.randint(1, self.duree_panne_max)
        # Statistique additionnelle : nombre de pannes
        self.total_connections += 0  # Placeholder si besoin

    def reparer(self):
        self.disponible = True
        self.panne_duree_restante = 0

    def verifier_panne(self):
        if self.disponible:
            if random.random() < self.probabilite_panne:
                self.tomber_en_panne()
        else:
            self.panne_duree_restante -= 1
            if self.panne_duree_restante <= 0:
                self.reparer()

    def incrementer_congestion(self, current_step):
        self.congestion += 1
        fin_congestion = current_step + DUREE_CONGESTION
        if fin_congestion not in self.historique_congestion:
            self.historique_congestion[fin_congestion] = 0
        self.historique_congestion[fin_congestion] += 1

        # Réduction de la portée en fonction de la congestion
        self.portee = max(100, self.portee_base - self.congestion * 10)  # Exemple de réduction

    def mettre_a_jour_congestion(self, current_step):
        if current_step in self.historique_congestion:
            nb_connexions_terminees = self.historique_congestion[current_step]
            self.congestion = max(0, self.congestion - nb_connexions_terminees)
            del self.historique_congestion[current_step]

        # Réajuster la portée en fonction de la congestion
        self.portee = max(100, self.portee_base - self.congestion * 10)  #

    def mettre_a_jour_degradation(self):
        """Simule la dégradation de l'antenne au fil du temps."""
        degradation = random.uniform(0, 1)  # Facteur de dégradation aléatoire
        self.portee = max(50, self.portee - degradation)  # Réduction minimale de la portée

    def submit_connection_request(self, vehicule):
        """Ajoute une demande de connexion à la file d'attente en fonction de la priorité du véhicule."""
        priority = self.PRIORITY_MAPPING.get(vehicule.priorite, 1)
        self.connexion_queue.append((priority, vehicule))

    def process_connection_queue(self, current_step):
        """Traite les demandes de connexion en fonction de la priorité et de la capacité."""
        if not self.disponible:
            return  # Si l'antenne est en panne, ignorer les demandes

        if not self.connexion_queue:
            return  # Pas de demandes à traiter

        # Trier la file d'attente par priorité décroissante
        self.connexion_queue.sort(key=lambda x: x[0], reverse=True)

        # Traiter les connexions jusqu'à la limite
        for priority, vehicule in self.connexion_queue:
            if self.active_connections >= self.MAX_CONNEXIONS:
                break  # Atteint la capacité maximale
            vehicule.process_connection_with_antenne(self, current_step)
            self.active_connections += 1
            self.total_connections += 1  

        # Vider la file d'attente après traitement
        self.connexion_queue = []

# 
# Classe Vehicule
# 
class Vehicule:
    def __init__(self, id, itineraire, vitesse=5.0, exigence=3, is_malicious=False, type_energie=None, is_privacy=False):
        """
        - itineraire : liste d'intersections (ex: ["A","B","C","D"])
        - vitesse    : distance que parcourt le véhicule par "pas" de simulation 
                       (on peut l'interpréter comme km/h / nb d'itérations, 
                       ou une unité arbitraire).
        - exigence   : fiabilité minimale attendue
        - is_malicious : True si c'est un véhicule espion
        - type_energie : "Electrique" ou "Thermique"
        - is_privacy   : True si le véhicule applique des politiques de confidentialité
        """
        self.id = id
        self.itineraire = itineraire
        self.vitesse = vitesse  # vitesse "maximale" interne au véhicule
        self.is_malicious = is_malicious
        self.exigence = exigence
        self.is_privacy = is_privacy  

        # Détermination du type d'énergie si non spécifié
        if type_energie is None:
            self.type_energie = random.choices(
                ["Electrique", "Thermique"],
                weights=[0.5, 0.5],  
                k=1
            )[0]
        else:
            self.type_energie = type_energie

        # Définition des taux de consommation selon le type d'énergie
        if self.type_energie == "Electrique":
            self.consommation_base = 0.05  # par unité de distance
            self.consommation_connexion = 0.01  # par connexion aux antennes
            self.energie_initiale = 100.0
        else:  # Thermique
            self.consommation_base = 0.1
            self.consommation_connexion = 0.02
            self.energie_initiale = 80.0

        # Politique d'économie, priorités
        self.priorite = random.choice(["Urgence", "Mise à jour de trafic", "Standard"])

        # Pseudonyme, énergie
        self.pseudonyme = generer_pseudonyme()
        self.energie = self.energie_initiale
        self.compteur_connexions = 0

        # Historique de connexions
        self.connexions_antennes = []
        self.connexions_relayees = []
        self.connexions_interceptees = []

        # Détection espion
        self.suspicion_score = 0
        self.est_detecte = False
        self.suspected_espions = {}

        # Itinéraire : index_noeud_courant, index_noeud_suivant
        self.index_noeud_courant = 0
        self.index_noeud_suivant = 1 if len(itineraire) > 1 else 0

        # Position initiale = coord. du 1er noeud
        start_node = self.itineraire[0]
        self.x, self.y = INTERSECTIONS[start_node]

        # Distances sur le segment en cours
        self.segment_length = 0.0
        self.distance_restante_segment = 0.0

        if len(itineraire) > 1:
            self._init_segment()

        # 
        # Attributs pour Communication V2V
        # 
        self.v2v_range = 50.0  # Portée de communication V2V 
        self.received_messages = []  # Liste des messages reçus

        # Statistiques additionnelles
        self.total_connection_time = 0.0  # Temps total passé en connexions

    def _init_segment(self):
        n1 = self.itineraire[self.index_noeud_courant]
        n2 = self.itineraire[self.index_noeud_suivant]
        info_route = ROUTES[(n1, n2)]
        self.segment_length = info_route["distance"]
        self.distance_restante_segment = self.segment_length

        #
        if self.index_noeud_courant == 0 and self.index_noeud_suivant == 1:
            offset = random.uniform(0, 0.3) * self.segment_length  #
            ratio = offset / self.segment_length
            x1, y1 = INTERSECTIONS[n1]
            x2, y2 = INTERSECTIONS[n2]
            self.x += ratio * (x2 - x1)
            self.y += ratio * (y2 - y1)
            self.distance_restante_segment -= offset

    def deplacer(self):
        """Fait avancer le véhicule sur son itinéraire en fonction de sa vitesse + limite route."""
        if self.index_noeud_courant == self.index_noeud_suivant:
            return  # plus de segment

        # On détermine la vitesse maximale autorisée sur la route courante
        n1 = self.itineraire[self.index_noeud_courant]
        n2 = self.itineraire[self.index_noeud_suivant]
        info_route = ROUTES[(n1, n2)]
        type_route = info_route["type"]
        vitesse_max_route = VITESSE_MAX_PAR_TYPE[type_route]  #

        # La "vitesse effective" est le min entre la vitesse du véhicule et la vitesse max autorisée
        distance_par_step = min(self.vitesse, vitesse_max_route)

        distance_a_parcourir = distance_par_step

        while distance_a_parcourir > 0:
            if distance_a_parcourir < self.distance_restante_segment:
                ratio = distance_a_parcourir / self.segment_length
                self._move_on_segment(ratio)
                self.distance_restante_segment -= distance_a_parcourir
                # Consommation énergétique
                self.consommer_energie(distance_a_parcourir, connexions=0)
                distance_a_parcourir = 0
            else:
                ratio = self.distance_restante_segment / self.segment_length
                self._move_on_segment(ratio)
                # Consommation énergétique
                self.consommer_energie(self.distance_restante_segment, connexions=0)
                distance_a_parcourir -= self.distance_restante_segment
                self.distance_restante_segment = 0

                self.index_noeud_courant = self.index_noeud_suivant
                if self.index_noeud_suivant < len(self.itineraire) - 1:
                    self.index_noeud_suivant += 1
                    self._init_segment()
                else:
                    self.index_noeud_suivant = self.index_noeud_courant
                    break

    def _move_on_segment(self, ratio):
        n1 = self.itineraire[self.index_noeud_courant]
        n2 = self.itineraire[self.index_noeud_suivant]
        x1, y1 = INTERSECTIONS[n1]
        x2, y2 = INTERSECTIONS[n2]
        self.x += ratio * (x2 - x1)
        self.y += ratio * (y2 - y1)

    def consommer_energie(self, distance, connexions):
        """
        Consomme de l'énergie en fonction de la distance et des connexions.
        - distance : distance parcourue dans cette étape
        - connexions : nombre de connexions actives (influence la consommation)
        """
        consommation = (self.consommation_base * distance) + (self.consommation_connexion * connexions)
        self.energie = max(0, self.energie - consommation)

    # 
    # Outils de distance pour les antennes
    # 
    def distance(self, autre_objet):
        return math.sqrt((self.x - autre_objet.x) ** 2 + (self.y - autre_objet.y) ** 2)

    # 
    # Politique d'économie adaptative
    # 
    def verifier_energie_adaptation(self):
        if self.energie < SEUIL_ENERGIE_ADAPTATION:
            self.exigence = max(1, self.exigence - 1)
            if self.priorite == "Standard":
                self.priorite = "Basse_Priorite"
            elif self.priorite == "Mise à jour de trafic":
                self.priorite = "Standard"

    def refuser_si_energie_faible(self):
        return self.energie < SEUIL_ENERGIE_REFUS

    # 
    # Connexions
    # 
    def accepter_connexion(self, antenne):
        """Détermine si la connexion est acceptée en fonction de la fiabilité de l'antenne et de l'exigence du véhicule."""
        fiabilite_antenne = antenne.fiabilite
        if self.priorite == "Urgence":
            return fiabilite_antenne >= self.exigence - 1
        elif self.priorite == "Mise à jour de trafic":
            return fiabilite_antenne >= self.exigence
        elif self.priorite in ("Standard", "Basse_Priorite"):
            return fiabilite_antenne > self.exigence
        return False

    def envoyer_message_chiffre(self, antenne_id, message):
        message_chiffre = cipher.encrypt(message.encode())
        return (antenne_id, message_chiffre)

    def essayer_connexion_antenne(self, antenne, current_step):
        """Soumet une demande de connexion à l'antenne en fonction des politiques de confidentialité."""
        self.verifier_energie_adaptation()
        
        if self.is_privacy:
            #refuser les antennes avec fiabilité < seuil
            seuil_privacy = 4  #seuil de fiabilité
            if antenne.fiabilite < seuil_privacy:
                # Ne pas tenter de connexion
                return
        antenne.submit_connection_request(self)

    def process_connection_with_antenne(self, antenne, current_step):
        """Traite la connexion avec l'antenne (appelé par l'antenne)."""
        dist = self.distance(antenne)
        if self.refuser_si_energie_faible():
            resultat = "Refus (energie trop faible)"
            cout_connexion = 0.0
            temps_connexion = 0.0
        elif not antenne.disponible:
            resultat = "Panne"
            cout_connexion = COUT_FIXE
            temps_connexion = TEMPS_BASE
            self.energie = max(0, self.energie - cout_connexion)
            # Consommation énergétique due à la tentative de connexion
            self.consommer_energie(0, connexions=1)
        else:
            antenne.incrementer_congestion(current_step)
            if dist <= antenne.portee:
                if self.accepter_connexion(antenne):
                    resultat = "Acceptée"
                else:
                    resultat = "Refusée"
            else:
                resultat = "Hors de portée"

            cout_connexion = COUT_FIXE + dist * COUT_DISTANCE
            fiabilite_factor = max(0.5, 1.5 - (antenne.fiabilite - 3) * TEMPS_FIABILITE_FACTOR)
            congestion_factor = 1 + antenne.congestion * TEMPS_CONGESTION_FACTOR
            temps_connexion = TEMPS_BASE + dist * TEMPS_PAR_UNITE
            temps_connexion *= fiabilite_factor
            temps_connexion *= congestion_factor

            self.energie = max(0, self.energie - cout_connexion)
            # Consommation énergétique due à la connexion
            if resultat == "Acceptée":
                self.consommer_energie(0, connexions=1)
                self.total_connection_time += temps_connexion  #

        message = (
            f"Pseudonyme: {self.pseudonyme}, Priorite: {self.priorite}, "
            f"Resultat: {resultat}, Distance: {dist:.2f}, Temps: {temps_connexion:.2f}, "
            f"Fiabilite: {antenne.fiabilite}, Congestion: {antenne.congestion}, "
            f"Cost: {cout_connexion:.2f}, EnergieRestante: {self.energie:.2f}"
        )
        antenne_id, message_chiffre = self.envoyer_message_chiffre(antenne.id, message)

        self.connexions_antennes.append({
            "Vehicule": self.pseudonyme,
            "Type_Energie": self.type_energie,
            "Malveillant": self.is_malicious,
            "Detecte": self.est_detecte,
            "SuspicionScore": self.suspicion_score,
            "Priorite": self.priorite,
            "Exigence": self.exigence,
            "EnergieInitiale": self.energie_initiale,
            "EnergieRestante": self.energie,  #
            "Antenne_ID": antenne_id,
            "Fiabilite_Antenne": antenne.fiabilite,
            "Resultat": resultat,
            "Distance": dist,  # 
            "Temps": temps_connexion,        # 
            "Cout": cout_connexion,           # 
            "Message_chiffre": message_chiffre  # Ajout de la clé manquante
        })

    def relayer_connexion(self, autre_vehicule, antenne):
        if (self.distance(antenne) <= antenne.portee
                and antenne.disponible
                and not self.est_detecte):
            autre_vehicule.connexions_relayees.append({
                "Antenne_ID": antenne.id,
                "Relais_Vehicule": self.pseudonyme,
                "Fiabilite_Antenne": antenne.fiabilite
            })
            # Consommation énergétique due au relais
            self.consommer_energie(0, connexions=1)

    # 
    # Espionnage
    # 
    def intercepter_connexion(self, vehicule_cible):
        if not self.is_malicious or self.est_detecte:
            return
        if vehicule_cible.connexions_antennes:
            derniere_connexion = vehicule_cible.connexions_antennes[-1]
            try:
                msg_chiffre = derniere_connexion["Message_chiffre"]
                self.connexions_interceptees.append({
                    "Victime": vehicule_cible.pseudonyme,
                    "Message_chiffre": msg_chiffre
                })
                self.suspicion_score += 1
                if self.suspicion_score >= SEUIL_SUSPICION:
                    self.est_detecte = True
            except KeyError:
                print(f"Alerte: 'Message_chiffre' manquant dans les connexions de {vehicule_cible.pseudonyme}")

    def suspecter_espion(self, espion_pseudonyme):
        if espion_pseudonyme not in self.suspected_espions:
            self.suspected_espions[espion_pseudonyme] = 0
        self.suspected_espions[espion_pseudonyme] += 1

    # 
    # Communication V2V
    # 
    def detect_nearby_vehicles(self, vehicules):
        """Détecte les véhicules à proximité dans la portée V2V."""
        nearby = []
        for veh in vehicules:
            if veh.id != self.id:
                distance = self.distance(veh)
                if distance <= self.v2v_range:
                    nearby.append(veh)
        return nearby

    def send_v2v_messages(self, vehicules):
        """
        Envoie des messages V2V aux véhicules à proximité.
        Les messages peuvent inclure des informations sur les antennes ou les routes.
        """
        nearby_vehicles = self.detect_nearby_vehicles(vehicules)
        for veh in nearby_vehicles:
            # partage des antennes congestionnées
            congested_antennes = [c["Antenne_ID"] for c in self.connexions_antennes if c["Resultat"] == "Acceptée" and c["Fiabilite_Antenne"] < 4]
            if congested_antennes:
                # Conversion des IDs en chaînes de caractères pour éviter l'erreur
                message = f"Antenne(s) congestionnée(s) : {', '.join(map(str, congested_antennes))}. Considérez l'utilisation d'une autre antenne."
                veh.receive_v2v_message(self.pseudonyme, message)

    def receive_v2v_message(self, sender_pseudonyme, message):
        """Reçoit un message V2V et le stocke."""
        self.received_messages.append({
            "Sender": sender_pseudonyme,
            "Message": message
        })

    def process_received_messages(self):
        """Traite les messages V2V reçus."""
        for msg in self.received_messages:
            #
            # 
            print(f"{self.pseudonyme} a reçu un message de {msg['Sender']}: {msg['Message']}")
            #ajuster la priorité si une antenne est congestionnée
            if "Antenne(s) congestionnée(s)" in msg['Message']:
                #on ajuste la priorité vers "Standard"
                if self.priorite != "Standard":
                    print(f"{self.pseudonyme} ajuste sa priorité de {self.priorite} à Standard suite au message V2V.")
                    self.priorite = "Standard"
        # Vider les messages après traitement
        self.received_messages = []

# 
# Fonctions de Simulation
# 
def run_simulation(NB_ETAPES=10, show_animation=True):
    """
    On crée quelques itinéraires possibles pour les véhicules,
    et on leur attribue un itinéraire.
    """
    # Liste d'itinéraires possibles (A -> B -> C -> D -> E) on peut changer l'ordre si on souhaite un itinéraire différent
    possible_paths = [
        ["A", "B", "C", "D", "E"],
        ["A", "E", "D", "C", "B"],
        ["A", "B", "C"],
        ["C", "B", "A", "E"],
        ["E", "D", "C", "B"]
    ]

    # 1) Création des antennes
    antennes = [
        Antenne(
            id=i,
            fiabilite=random.randint(3, 6),
            x=random.randint(0, ZONE_X),
            y=random.randint(0, ZONE_Y),
            type_antenne="locale" if i % 2 == 0 else "principale",
            disponible=True  # Initialement disponibles
        )
        for i in range(1, 7)
    ]

    # 2) Création des véhicules (avec itinéraire)
    nombre_vehicules = 15
    vehicules = []
    for i in range(1, nombre_vehicules + 1):
        path = random.choice(possible_paths)
        is_malicious = (random.random() < 0.3)
        vitesse_alea = random.uniform(3.0, 7.0)  # vitesse propre du véhicule

        # Détermination du type d'énergie avec 50% de chances pour chaque type
        type_energie = random.choices(
            ["Electrique", "Thermique"],
            weights=[0.5, 0.5],
            k=1
        )[0]

        # Détermination aléatoire du statut de privacy (50% de chance)
        is_privacy = random.choice([True, False])

        v = Vehicule(
            id=i,
            itineraire=path,
            vitesse=vitesse_alea,
            exigence=random.randint(3, 6),
            is_malicious=is_malicious,
            type_energie=type_energie,
            is_privacy=is_privacy
        )
        vehicules.append(v)

    # 3) Pour l’animation
    all_positions = []

    # 
    # Initialisation des Statistiques
    # 
    total_success = 0
    total_refused = 0
    connection_durations = []
    vehicles_completed = []
    antenne_pannes = {antenne.id: 0 for antenne in antennes}
    antenne_congestions = {antenne.id: 0 for antenne in antennes}

    privacy_success = 0
    privacy_refused = 0
    privacy_espionnage = 0

    non_privacy_success = 0
    non_privacy_refused = 0
    non_privacy_espionnage = 0

    # **ADDITION : Collecte des données pour les nouveaux graphiques**
    congestion_par_etape = []
    espionnage_par_etape = []

    # **ADDITION : Utilisation de DataFrames pour collecter les connexions**
    connexions_data = {
        "Vehicule": [],
        "Type_Energie": [],
        "Malveillant": [],
        "Detecte": [],
        "SuspicionScore": [],
        "Priorite": [],
        "Exigence": [],
        "EnergieInitiale": [],
        "EnergieRestante": [],
        "Antenne_ID": [],
        "Fiabilite_Antenne": [],
        "Resultat": [],
        "Distance": [],
        "Temps": [],
        "Cout": [],
        "Message_chiffre": []
    }

    # **ADDITION : Statistiques additionnelles**
    connexions_par_antenne = {antenne.id: {"Acceptée": 0, "Refusée": 0, "Panne": 0, "Hors de portée": 0} for antenne in antennes}
    temps_connexion_par_vehicule = {vehicule.pseudonyme: 0.0 for vehicule in vehicules}

    # 4) Boucle de simulation
    for step in range(NB_ETAPES):
        print(f"\n--- Étape {step+1} ---")
        pannes_actuelles = 0  # Compteur pour les pannes actuelles
        for antenne in antennes:
            # Vérifier les pannes
            antenne.verifier_panne()
            if not antenne.disponible and antenne.panne_duree_restante == antenne.duree_panne_max:
                antenne_pannes[antenne.id] += 1
                pannes_actuelles += 1  # Incrementer les pannes actuelles
            # Mettre à jour la dégradation
            antenne.mettre_a_jour_degradation()
            # Mettre à jour la congestion
            antenne.mettre_a_jour_congestion(step)
            # Mise à jour des niveaux de congestion pour rapport
            antenne_congestions[antenne.id] = antenne.congestion

        #Calculer et enregistrer la congestion totale pour cette étape
        total_congestion = sum(antenne.congestion for antenne in antennes)
        congestion_par_etape.append(total_congestion)

        #Initialiser le compteur d'espionnage pour cette étape
        espionnage_actuel = 0

        # Déplacement et soumission des demandes de connexion
        for vehicule in vehicules:
            # Avance sur l'itinéraire
            vehicule.deplacer()

            # Vérifier si le véhicule a terminé son itinéraire
            if vehicule.index_noeud_courant == vehicule.index_noeud_suivant and vehicule.distance_restante_segment == 0:
                if vehicule.pseudonyme not in vehicles_completed:
                    vehicles_completed.append(vehicule.pseudonyme)
                    print(f"{vehicule.pseudonyme} a terminé son itinéraire.")

            # Soumission des demandes de connexion aux antennes
            for antenne in antennes:
                vehicule.essayer_connexion_antenne(antenne, current_step=step)

            # Relais
            for autre_vehicule in vehicules:
                if autre_vehicule != vehicule:
                    for antenne in antennes:
                        vehicule.relayer_connexion(autre_vehicule, antenne)

            # Espionnage
            if vehicule.is_malicious and not vehicule.est_detecte:
                victime = random.choice(vehicules)
                if victime != vehicule:
                    pre_detection = len(victime.connexions_antennes) + len(victime.connexions_relayees) + len(victime.connexions_interceptees)
                    vehicule.intercepter_connexion(victime)
                    post_detection = len(victime.connexions_antennes) + len(victime.connexions_relayees) + len(victime.connexions_interceptees)
                    if post_detection > pre_detection:
                        espionnage_actuel += 1
                    victime.suspecter_espion(vehicule.pseudonyme)

        #Enregistrer les espionnages de cette étape pour le graphique
        espionnage_par_etape.append(espionnage_actuel)

        # Traitement des files d'attente des antennes après toutes les demandes
        for antenne in antennes:
            antenne.process_connection_queue(step)

        # Communication V2V : Envoi de messages
        for vehicule in vehicules:
            vehicule.send_v2v_messages(vehicules)

        # Communication V2V : Traitement des messages reçus
        for vehicule in vehicules:
            vehicule.process_received_messages()

        # Mise à jour des Statistiques de Connexion
        for vehicule in vehicules:
            for c in vehicule.connexions_antennes:
                # Remplir connexions_data
                connexions_data["Vehicule"].append(c["Vehicule"])
                connexions_data["Type_Energie"].append(c["Type_Energie"])
                connexions_data["Malveillant"].append(c["Malveillant"])
                connexions_data["Detecte"].append(c["Detecte"])
                connexions_data["SuspicionScore"].append(c["SuspicionScore"])
                connexions_data["Priorite"].append(c["Priorite"])
                connexions_data["Exigence"].append(c["Exigence"])
                connexions_data["EnergieInitiale"].append(c["EnergieInitiale"])
                connexions_data["EnergieRestante"].append(c["EnergieRestante"])
                connexions_data["Antenne_ID"].append(c["Antenne_ID"])
                connexions_data["Fiabilite_Antenne"].append(c["Fiabilite_Antenne"])
                connexions_data["Resultat"].append(c["Resultat"])
                connexions_data["Distance"].append(c["Distance"])
                connexions_data["Temps"].append(c["Temps"])
                connexions_data["Cout"].append(c["Cout"])
                connexions_data["Message_chiffre"].append(c["Message_chiffre"])

                # Mettre à jour les statistiques
                if c["Resultat"] == "Acceptée":
                    total_success += 1
                    connection_durations.append(c["Temps"])
                    temps_connexion_par_vehicule[vehicule.pseudonyme] += c["Temps"]  #
                    if vehicule.is_privacy:
                        privacy_success += 1
                    else:
                        non_privacy_success += 1
                    # Mettre à jour les connexions par antenne
                    antenne_id = c["Antenne_ID"]
                    connexions_par_antenne[antenne_id]["Acceptée"] += 1
                elif "Refus" in c["Resultat"]:
                    total_refused += 1
                    connection_durations.append(c["Temps"])
                    if vehicule.is_privacy:
                        privacy_refused += 1
                    else:
                        non_privacy_refused += 1
                    # Mettre à jour les connexions par antenne
                    antenne_id = c["Antenne_ID"]
                    connexions_par_antenne[antenne_id]["Refusée"] += 1
                elif c["Resultat"] == "Panne":
                    antenne_id = c["Antenne_ID"]
                    connexions_par_antenne[antenne_id]["Panne"] += 1
                elif c["Resultat"] == "Hors de portée":
                    antenne_id = c["Antenne_ID"]
                    connexions_par_antenne[antenne_id]["Hors de portée"] += 1

        # Comptage des espionnages
        for v in vehicules:
            if v.is_privacy:
                privacy_espionnage += len(v.connexions_interceptees)
            else:
                non_privacy_espionnage += len(v.connexions_interceptees)

        #Stocke positions et autres données pour l'animation
        positions_vehicules = [(v.x, v.y, v.is_malicious, v.type_energie, v.energie, v.is_privacy) for v in vehicules]
        positions_antennes = [(a.x, a.y, a.disponible) for a in antennes]
        all_positions.append({
            'vehicules': positions_vehicules,
            'antennes': positions_antennes
        })

    #Création des DataFrames à partir des données collectées
    df_resultats = pd.DataFrame(connexions_data)
    print("\n=== Résultats de la simulation ===")
    print(df_resultats.to_string(index=False))

    # Espionnage
    espionnage_data = []
    for v in vehicules:
        if v.connexions_interceptees:
            for interception in v.connexions_interceptees:
                espionnage_data.append({
                    "Espion": v.pseudonyme,
                    "Espion_Detecte": v.est_detecte,
                    "Victime": interception["Victime"]
                })
    df_espionnage = pd.DataFrame(espionnage_data)
    print("\n=== Interceptions (espionnage) ===")
    print(df_espionnage.to_string(index=False))

    #Création des DataFrames pour les statistiques additionnelles
    df_connexions_par_antenne = pd.DataFrame([
        {"Antenne_ID": antenne_id, **stats} for antenne_id, stats in connexions_par_antenne.items()
    ])

    df_temps_connexion_par_vehicule = pd.DataFrame([
        {"Vehicule": vehicule, "Temps_Total_Connexion": temps}
        for vehicule, temps in temps_connexion_par_vehicule.items()
    ])

    # 5) Animation Matplotlib
    if show_animation:
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.set_xlim(0, ZONE_X)
        ax.set_ylim(0, ZONE_Y)
        ax.set_title("Simulation Réseaux Véhicules (Avec Types de Routes)")

        scat_antennes = ax.scatter([], [], c='red', marker='^', s=80, label="Antennes")
        scat_vehicules = ax.scatter([], [], c=[], marker='o', s=50, label="Véhicules")

        # Dessiner le graphe routier avec les types
        routes_plot = []
        for (n1, n2), info in ROUTES.items():
            x1, y1 = INTERSECTIONS[n1]
            x2, y2 = INTERSECTIONS[n2]
            # Couleur selon type
            t = info["type"]
            if t == "autoroute":
                col = "black"
                style = "-"
            elif t == "principale":
                col = "gray"
                style = "--"
            else:  # secondaire
                col = "lightgray"
                style = ":"
            line, = ax.plot([x1, x2], [y1, y2], color=col, linestyle=style, linewidth=2)
            routes_plot.append(line)

        # 
        # Initialisation des Statistiques pour la Visualisation
        # 
        success_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, fontsize=10,
                               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        refused_text = ax.text(0.02, 0.90, '', transform=ax.transAxes, fontsize=10,
                               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
        congestion_text = ax.text(0.02, 0.85, '', transform=ax.transAxes, fontsize=10,
                                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))

        # Fonction pour colorier les routes en fonction de la congestion
        def color_routes():
            for route, line in zip(ROUTES.keys(), routes_plot):
                #
                # Une route est congestionnée si au moins une antenne proche est congestionnée
                # 
                distance_threshold = 10.0
                congested = False
                for antenne in antennes:
                    # Calculer la distance de l'antenne à la route
                    # Route définie par (n1, n2)
                    n1, n2 = route
                    x1, y1 = INTERSECTIONS[n1]
                    x2, y2 = INTERSECTIONS[n2]
                    # Calculer la distance point à segment
                    px, py = antenne.x, antenne.y
                    seg_len_sq = (x2 - x1)**2 + (y2 - y1)**2
                    if seg_len_sq == 0:
                        distance = math.sqrt((px - x1)**2 + (py - y1)**2)
                    else:
                        t = max(0, min(1, ((px - x1)*(x2 - x1) + (py - y1)*(y2 - y1)) / seg_len_sq))
                        proj_x = x1 + t * (x2 - x1)
                        proj_y = y1 + t * (y2 - y1)
                        distance = math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
                    if distance <= distance_threshold and antenne.congestion >= 3:
                        congested = True
                        break
                # Colors
                if congested:
                    line.set_color('red')
                    line.set_linewidth(3)
                else:
                    # Recolorier en fonction du type de route
                    route_type = ROUTES[route]["type"]
                    if route_type == "autoroute":
                        line.set_color("black")
                        line.set_linewidth(2)
                    elif route_type == "principale":
                        line.set_color("gray")
                        line.set_linewidth(2)
                    else:
                        line.set_color("lightgray")
                        line.set_linewidth(2)

        def init():
            scat_antennes.set_offsets(np.empty((0, 2)))
            scat_vehicules.set_offsets(np.empty((0, 2)))
            scat_vehicules.set_color([])
            success_text.set_text('')
            refused_text.set_text('')
            congestion_text.set_text('')
            return scat_antennes, scat_vehicules, success_text, refused_text, congestion_text

        def update(frame):
            data_frame = all_positions[frame]
            # Antennes
            antennes_xy = [(ant[0], ant[1]) for ant in data_frame['antennes']]
            scat_antennes.set_offsets(antennes_xy)
            colors_a = ['red' if not ant[2] else 'green' for ant in data_frame['antennes']]  # Panne: red, disponible: green
            scat_antennes.set_color(colors_a)

            # Véhicules
            veh_xy = [(v[0], v[1]) for v in data_frame['vehicules']]
            scat_vehicules.set_offsets(veh_xy)
            # Définir les couleurs en fonction du type et si malveillant
            colors_v = []
            for v in data_frame['vehicules']:
                type_energie = v[3]
                is_malicious = v[2]
                energie = v[4]
                is_privacy = v[5]
                if type_energie == "Electrique":
                    base_color = 'green'
                else:
                    base_color = 'blue'
                if is_malicious:  # Malveillant
                    color = 'red'
                elif is_privacy:
                    color = 'cyan'  # Couleur spécifique pour privacy
                else:
                    color = base_color
                colors_v.append(color)
            scat_vehicules.set_color(colors_v)

            # Mise à jour des routes en fonction de la congestion
            color_routes()

            # Mise à jour des textes de légende
            success_text.set_text(f"Connexions Réussies : {total_success}")
            refused_text.set_text(f"Connexions Refusées : {total_refused}")
            current_congestion = sum(antenne_congestions.values())
            congestion_text.set_text(f"Congestion Totale Antennes : {current_congestion}")

            ax.set_title(f"Simulation Step {frame+1}/{NB_ETAPES}")
            return scat_antennes, scat_vehicules, success_text, refused_text, congestion_text

        ani = FuncAnimation(
            fig, update, frames=len(all_positions),
            init_func=init, blit=False,
            interval=500, repeat=False
        )

        ax.legend()
        plt.show()

    # 7) Coloration des routes après mise à jour
    color_routes()

    return df_resultats, total_success, total_refused, connection_durations, vehicles_completed, antenne_pannes, antenne_congestions, \
           privacy_success, privacy_refused, privacy_espionnage, non_privacy_success, non_privacy_refused, non_privacy_espionnage, vehicules, congestion_par_etape, espionnage_par_etape, \
           df_connexions_par_antenne, df_temps_connexion_par_vehicule

def stats_finales(df_resultats, total_success, total_refused, connection_durations, vehicles_completed, antenne_pannes, antenne_congestions,
                 privacy_success, privacy_refused, privacy_espionnage, non_privacy_success, non_privacy_refused, non_privacy_espionnage, vehicules, congestion_par_etape, espionnage_par_etape,
                 df_connexions_par_antenne, df_temps_connexion_par_vehicule):
    """Rapport détaillé en fin de simulation avec comparaison Privacy vs Non-Privacy."""
    #import matplotlib.pyplot as plt
    #import seaborn as sns

    print("\n=== Rapport Final de la Simulation ===\n")

    # Nombre total de connexions réussies/refusées
    print(f"Nombre total de connexions réussies : {total_success}")
    print(f"Nombre total de connexions refusées : {total_refused}\n")

    # Durée moyenne des connexions
    if connection_durations:
        moyenne_duree = sum(connection_durations) / len(connection_durations)
        print(f"Durée moyenne des connexions : {moyenne_duree:.2f} unités de temps\n")
    else:
        print("Aucune connexion enregistrée.\n")

    # Véhicules ayant terminé leur itinéraire
    print(f"Véhicules ayant terminé leur itinéraire ({len(vehicles_completed)}):")
    for veh in vehicles_completed:
        print(f" - {veh}")
    print()

    # État des antennes
    print("État des antennes:")
    for antenne_id, pannes in antenne_pannes.items():
        congestion = antenne_congestions.get(antenne_id, 0)
        print(f" - Antenne {antenne_id}: {pannes} panne(s), Congestion actuelle: {congestion}")
    print()

    # 
    # Visualisation des Statistiques Comparatives
    # 

    # 1. Connexions Réussies vs Refusées
    labels = ['Réussies', 'Refusées']
    privacy_counts = [privacy_success, privacy_refused]
    non_privacy_counts = [non_privacy_success, non_privacy_refused]

    x = np.arange(len(labels))  # l'emplacement des labels
    width = 0.35  # la largeur des barres

    fig, ax = plt.subplots(figsize=(8, 6))
    rects1 = ax.bar(x - width/2, privacy_counts, width, label='Privacy', color='blue')
    rects2 = ax.bar(x + width/2, non_privacy_counts, width, label='Non-Privacy', color='orange')

    # Ajouter quelques labels et titres
    ax.set_ylabel('Nombre de Connexions')
    ax.set_title('Comparaison des Connexions Réussies et Refusées')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    # Ajouter des annotations
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate('{}'.format(height),
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # décalage en y
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)

    plt.tight_layout()
    plt.show()

    # 2. Risque d'Espionnage
    labels = ['Privacy', 'Non-Privacy']
    espionnage = [privacy_espionnage, non_privacy_espionnage]

    plt.figure(figsize=(8, 6))
    bars = plt.bar(labels, espionnage, color=['blue', 'orange'])
    plt.title("Comparaison du Risque d'Espionnage")
    plt.ylabel("Nombre d'Interceptions")

    # Ajouter des annotations
    for bar in bars:
        height = bar.get_height()
        plt.annotate('{}'.format(height),
                     xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3),  # décalage en y
                     textcoords="offset points",
                     ha='center', va='bottom')

    plt.tight_layout()
    plt.show()

    # 3. Comparaison des Types d'Énergie
    plt.figure(figsize=(6, 6))
    type_counts_privacy = df_resultats[df_resultats['Vehicule'].isin([v.pseudonyme for v in vehicules if v.is_privacy])]['Type_Energie'].value_counts()
    type_counts_non_privacy = df_resultats[df_resultats['Vehicule'].isin([v.pseudonyme for v in vehicules if not v.is_privacy])]['Type_Energie'].value_counts()

    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    type_counts_privacy.plot(kind='pie', autopct='%1.1f%%', colors=['green', 'blue'], startangle=90, ax=axs[0], title='Types d\'Énergie (Privacy)')
    type_counts_non_privacy.plot(kind='pie', autopct='%1.1f%%', colors=['green', 'blue'], startangle=90, ax=axs[1], title='Types d\'Énergie (Non-Privacy)')
    for ax in axs:
        ax.set_ylabel('')
    plt.tight_layout()
    plt.show()

    # 
    # Nouveaux Graphiques pour améliorer la Visualisation
    # 

    # 4. Évolution de la Congestion Totale des Antennes au Fil des Étapes de Simulation
    plt.figure(figsize=(10, 6))
    steps = range(1, len(congestion_par_etape) + 1)
    plt.plot(steps, congestion_par_etape, marker='o', linestyle='-', color='purple')
    plt.title("Évolution de la Congestion Totale des Antennes au Fil des Étapes de Simulation")
    plt.xlabel("Étapes de Simulation")
    plt.ylabel("Congestion Totale")
    plt.grid(True)
    plt.xticks(steps)  # Assure que chaque étape est marquée sur l'axe x
    plt.tight_layout()
    plt.show()

    # 5. Évolution du Nombre d'Interceptions (Espionnage) au Fil des Étapes de Simulation
    plt.figure(figsize=(10, 6))
    steps = range(1, len(espionnage_par_etape) + 1)
    plt.plot(steps, espionnage_par_etape, marker='s', linestyle='-', color='red')
    plt.title("Évolution du Nombre d'Interceptions (Espionnage) au Fil des Étapes de Simulation")
    plt.xlabel("Étapes de Simulation")
    plt.ylabel("Nombre d'Interceptions")
    plt.grid(True)
    plt.xticks(steps)  # Assure que chaque étape est marquée sur l'axe x
    plt.tight_layout()
    plt.show()

    # 
    # Graphique 6: Énergie Initiale vs Énergie Restante par Groupe
    # 
    # plt.figure(figsize=(10, 8))
    # privacy_group = df_resultats[df_resultats['Vehicule'].isin([v.pseudonyme for v in vehicules if v.is_privacy])]
    # non_privacy_group = df_resultats[df_resultats['Vehicule'].isin([v.pseudonyme for v in vehicules if not v.is_privacy])]

    # plt.scatter(privacy_group['EnergieInitiale'].astype(float), privacy_group['EnergieRestante'].astype(float), label='Privacy', color='blue', alpha=0.6)
    # plt.scatter(non_privacy_group['EnergieInitiale'].astype(float), non_privacy_group['EnergieRestante'].astype(float), label='Non-Privacy', color='orange', alpha=0.6)
    # plt.title("Énergie Initiale vs Énergie Restante par Groupe")
    # plt.xlabel("Énergie Initiale")
    # plt.ylabel("Énergie Restante")
    # plt.legend()
    # plt.tight_layout()
    # plt.show()

    # 
    
    # Graphique 7: Boxplot de l'Énergie Restante par Groupe
    # 
    # plt.figure(figsize=(8, 6))
    # energy_data = [
    #     privacy_group['EnergieRestante'].astype(float),
    #     non_privacy_group['EnergieRestante'].astype(float)
    # ]
    # plt.boxplot(energy_data, tick_labels=['Privacy', 'Non-Privacy'], patch_artist=True,
    #             boxprops=dict(facecolor='blue', color='blue'),
    #             medianprops=dict(color='yellow'))
    # plt.title("Énergie Restante par Groupe")
    # plt.ylabel("Énergie Restante")
    # plt.tight_layout()
    plt.show()

    # 
    # Statistiques Additionnelles
    # 

    # 6. Connexions par Antenne et par Résultat
    plt.figure(figsize=(10, 6))
    df_connexions_par_antenne_melted = df_connexions_par_antenne.melt(id_vars="Antenne_ID", var_name="Resultat", value_name="Nombre")
    sns.barplot(data=df_connexions_par_antenne_melted, x='Antenne_ID', y='Nombre', hue='Resultat')
    plt.title("Nombre de Connexions par Antenne et par Résultat")
    plt.xlabel("ID de l'Antenne")
    plt.ylabel("Nombre de Connexions")
    plt.legend(title='Résultat')
    plt.tight_layout()
    plt.show()

    # 7. Temps Total de Connexion par Véhicule
    plt.figure(figsize=(12, 6))
    sns.barplot(
        data=df_temps_connexion_par_vehicule, 
        x='Vehicule', 
        y='Temps_Total_Connexion', 
        hue='Vehicule',  
        palette='viridis', 
        legend=False  
    )
    plt.title("Temps Total de Connexion par Véhicule")
    plt.xlabel("Véhicule")
    plt.ylabel("Temps Total de Connexion (unités de temps)")
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.show()

    # 8. Temps Moyen de Connexion par Véhicule
    if not df_temps_connexion_par_vehicule.empty:
        df_temps_connexion_par_vehicule['Temps_Moyen_Connexion'] = df_temps_connexion_par_vehicule['Temps_Total_Connexion']
        plt.figure(figsize=(12, 6))
        sns.barplot(
            data=df_temps_connexion_par_vehicule, 
            x='Vehicule', 
            y='Temps_Moyen_Connexion', 
            hue='Vehicule',  
            palette='magma', 
            legend=False  
        )
        plt.title("Temps Moyen de Connexion par Véhicule")
        plt.xlabel("Véhicule")
        plt.ylabel("Temps Moyen de Connexion (unités de temps)")
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.show()
    else:
        print("Aucune donnée de temps de connexion disponible.")

# 
# main
# 
if __name__ == "__main__":

    df_final, total_success, total_refused, connection_durations, vehicles_completed, antenne_pannes, antenne_congestions, \
    privacy_success, privacy_refused, privacy_espionnage, non_privacy_success, non_privacy_refused, non_privacy_espionnage, vehicules, congestion_par_etape, espionnage_par_etape, \
    df_connexions_par_antenne, df_temps_connexion_par_vehicule = run_simulation(NB_ETAPES=20, show_animation=True)
    
    stats_finales(df_final, total_success, total_refused, connection_durations, vehicles_completed, antenne_pannes, antenne_congestions,
                 privacy_success, privacy_refused, privacy_espionnage, non_privacy_success, non_privacy_refused, non_privacy_espionnage, vehicules, congestion_par_etape, espionnage_par_etape,
                 df_connexions_par_antenne, df_temps_connexion_par_vehicule)
