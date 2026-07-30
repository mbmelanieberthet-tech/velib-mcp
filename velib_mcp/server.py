"""Étape 5 — Le serveur MCP.

Assemble les trois briques précédentes (velib, geocode, distance) et expose
à Claude UN outil : à partir d'une adresse de départ et d'une adresse
d'arrivée, il renvoie la meilleure station Vélib de chaque côté.

Lancement (via Claude Desktop, en transport stdio) :
    uv run python -m velib_mcp.server
"""

import os

from mcp.server.fastmcp import FastMCP

from .distance import (
    MIN_DOCKS,
    MIN_EBIKES,
    StationChoice,
    rank_arrival_stations,
    rank_departure_stations,
)
from .geocode import AdresseIntrouvable, geocode
from .velib import get_stations

# On crée le serveur et on lui donne un nom (celui qui apparaîtra dans Claude).
# host="0.0.0.0" + port : nécessaires pour le mode web (un hébergeur fournit le
# numéro de port via la variable d'environnement PORT ; 8000 par défaut en local).
mcp = FastMCP(
    "velib",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)


def _ligne_depart(choix: StationChoice) -> str:
    """Décrit une station de départ en une ligne (nom, vélos élec., distance)."""
    s = choix.station
    return (
        f"{s.name} — {s.ebikes} vélos élec. "
        f"(+{s.mechanical} méca.), ~{choix.walk_min:.0f} min à pied "
        f"({choix.distance_km:.2f} km)"
    )


def _ligne_arrivee(choix: StationChoice) -> str:
    """Décrit une station d'arrivée en une ligne (nom, places libres, distance)."""
    s = choix.station
    return (
        f"{s.name} — {s.free_docks} places libres, "
        f"~{choix.walk_min:.0f} min à pied ({choix.distance_km:.2f} km)"
    )


def _bloc(titre: str, choix_list: list[StationChoice], decrire, message_vide: str) -> list[str]:
    """Construit un bloc de texte : la recommandation + jusqu'à 2 alternatives."""
    if not choix_list:
        return [message_vide]
    lignes = [f"{titre}", f"   ✅ Recommandée : {decrire(choix_list[0])}"]
    alternatives = choix_list[1:3]  # les 2 suivantes, si elles existent
    if alternatives:
        lignes.append("   Alternatives proches :")
        lignes.extend(f"     • {decrire(c)}" for c in alternatives)
    return lignes


@mcp.tool()
def trouver_stations_velib(adresse_depart: str, adresse_arrivee: str) -> str:
    """Trouve les meilleures stations Vélib pour un trajet à Paris.

    À utiliser dès que l'utilisateur veut faire un trajet en Vélib et donne
    une adresse (ou un lieu) de départ et d'arrivée. Pour de bons résultats,
    privilégier des adresses précises (rue + arrondissement).

    Renvoie, de chaque côté, la station la PLUS PROCHE (≤ 15 min à pied) qui a
    assez de disponibilité, plus 2 alternatives proches :
      - au DÉPART : au moins 2 vélos électriques (et si seulement 2, au moins
        1 vélo manuel en secours ; à partir de 3 électriques, pas de secours) ;
      - à l'ARRIVÉE : au moins 2 places libres pour se garer.

    Args:
        adresse_depart: adresse ou lieu de départ, ex. « Tour Eiffel Paris ».
        adresse_arrivee: adresse ou lieu d'arrivée, ex. « 18 rue de Dunkerque 75010 Paris ».
    """
    # 1. Adresses -> coordonnées GPS. On capture le cas « adresse introuvable ».
    try:
        depart = geocode(adresse_depart)
    except AdresseIntrouvable:
        return f"❌ Je n'ai pas trouvé l'adresse de départ : « {adresse_depart} »."
    try:
        arrivee = geocode(adresse_arrivee)
    except AdresseIntrouvable:
        return f"❌ Je n'ai pas trouvé l'adresse d'arrivée : « {adresse_arrivee} »."

    # 2. État en temps réel de toutes les stations Vélib.
    stations = get_stations()

    # 3. Classement des stations (la plus proche atteignant le seuil d'abord).
    departs = rank_departure_stations(stations, depart.lat, depart.lon)
    arrivees = rank_arrival_stations(stations, arrivee.lat, arrivee.lon)

    # 4. Construction de la réponse, en confirmant les adresses reconnues
    #    (garde-fou : l'utilisatrice peut repérer un éventuel contresens).
    lignes = [
        "Trajet analysé :",
        f"  • Départ reconnu  : {depart.label}",
        f"  • Arrivée reconnue : {arrivee.label}",
        "",
    ]
    lignes += _bloc(
        f"🔋 DÉPART (≥ {MIN_EBIKES} élec., +1 manuel si seulement {MIN_EBIKES}) :",
        departs,
        _ligne_depart,
        "🔋 Aucune station ne remplit le critère de départ à moins de 15 min à "
        "pied.",
    )
    lignes.append("")
    lignes += _bloc(
        f"🅿️ ARRIVÉE (≥ {MIN_DOCKS} places libres) :",
        arrivees,
        _ligne_arrivee,
        f"🅿️ Aucune station avec au moins {MIN_DOCKS} places libres à moins de "
        "15 min à pied de l'arrivée.",
    )
    return "\n".join(lignes)


# Point d'entrée : deux modes possibles, choisis par la variable MCP_TRANSPORT.
#   - "stdio" (défaut) : le « tuyau interne », pour Claude Desktop en local.
#   - "http"           : l'« adresse web », pour un usage en ligne / mobile.
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
