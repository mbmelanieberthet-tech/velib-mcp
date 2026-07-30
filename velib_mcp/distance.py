"""Étape 4 — Distance et sélection de la meilleure station.

Ce module ne connaît ni internet ni les API : il reçoit des données déjà
prêtes (une liste de `Station` et un point GPS) et fait uniquement des maths.

Il sait :
  1. mesurer la distance à vol d'oiseau entre deux points (formule de Haversine) ;
  2. ne garder que les stations à moins de ~15 min à pied ;
  3. choisir la meilleure station selon un critère (vélos élec. ou places libres).
"""

import math
from dataclasses import dataclass

from .velib import Station

# 15 min à pied ≈ 1,25 km, sur la base d'une vitesse de marche de 5 km/h.
WALK_RADIUS_KM = 1.25
WALK_SPEED_KMH = 5.0

# Seuils « suffisants » : en dessous, la station est jugée trop juste.
# Au-dessus, on considère que c'est assez et on privilégie la PROXIMITÉ.
#
# Règle de DÉPART :
#   - au moins MIN_EBIKES vélos électriques dans tous les cas ;
#   - si on en a moins de EBIKES_NO_BACKUP, on exige en plus au moins
#     MIN_MECHANICAL vélo manuel comme plan B (au cas où un électrique
#     présent serait en mauvais état) ;
#   - à partir de EBIKES_NO_BACKUP électriques, le plan B n'est plus exigé.
MIN_EBIKES = 2       # minimum absolu de vélos électriques
EBIKES_NO_BACKUP = 3  # à partir d'ici, pas besoin de manuel de secours
MIN_MECHANICAL = 1   # nombre de manuels exigés quand les électriques sont justes

# Règle d'ARRIVÉE :
MIN_DOCKS = 2        # au moins ce nombre de places libres pour se garer


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance à vol d'oiseau (en km) entre deux points GPS.

    Utilise la formule de Haversine, qui tient compte de la courbure de la
    Terre. Précision largement suffisante à l'échelle d'une ville.
    """
    rayon_terre_km = 6371.0

    # On convertit les degrés en radians (les fonctions trigo travaillent en radians).
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return rayon_terre_km * c


def walk_minutes(distance_km: float) -> float:
    """Convertit une distance (km) en temps de marche estimé (minutes)."""
    return distance_km / WALK_SPEED_KMH * 60


@dataclass
class StationChoice:
    """Le résultat d'une sélection : une station + sa distance depuis le point visé."""

    station: Station
    distance_km: float

    @property
    def walk_min(self) -> float:
        """Temps de marche estimé jusqu'à cette station (minutes)."""
        return walk_minutes(self.distance_km)


def _stations_within_walk(
    stations: list[Station], lat: float, lon: float
) -> list[StationChoice]:
    """Garde les stations à moins de WALK_RADIUS_KM d'un point, avec leur distance."""
    proches: list[StationChoice] = []
    for station in stations:
        distance = haversine_km(lat, lon, station.lat, station.lon)
        if distance <= WALK_RADIUS_KM:
            proches.append(StationChoice(station=station, distance_km=distance))
    return proches


def _depart_suffisant(station: Station) -> bool:
    """Vrai si la station a de quoi partir sereinement (voir la règle de départ).

    - au moins MIN_EBIKES électriques ;
    - et, tant qu'on n'atteint pas EBIKES_NO_BACKUP électriques, au moins
      MIN_MECHANICAL manuel en secours.
    """
    if station.ebikes < MIN_EBIKES:
        return False
    if station.ebikes >= EBIKES_NO_BACKUP:
        return True  # assez d'électriques : plan B inutile
    return station.mechanical >= MIN_MECHANICAL  # sinon, un manuel de secours


def rank_departure_stations(
    stations: list[Station], lat: float, lon: float
) -> list[StationChoice]:
    """Stations pour PARTIR près de (lat, lon), de la plus proche à la plus
    lointaine, parmi celles qui satisfont la règle de départ.

    Logique « seuil de suffisance » : dès qu'une station a assez de vélos, on
    préfère la plus proche plutôt que celle qui en a le plus (mais plus loin).
    """
    candidats = [
        c
        for c in _stations_within_walk(stations, lat, lon)
        if c.station.is_renting and _depart_suffisant(c.station)
    ]
    candidats.sort(key=lambda c: c.distance_km)  # la plus proche d'abord
    return candidats


def rank_arrival_stations(
    stations: list[Station], lat: float, lon: float, min_docks: int = MIN_DOCKS
) -> list[StationChoice]:
    """Stations pour ARRIVER près de (lat, lon), de la plus proche à la plus
    lointaine, parmi celles qui ont AU MOINS `min_docks` places libres."""
    candidats = [
        c
        for c in _stations_within_walk(stations, lat, lon)
        if c.station.is_returning and c.station.free_docks >= min_docks
    ]
    candidats.sort(key=lambda c: c.distance_km)  # la plus proche d'abord
    return candidats


def best_departure_station(
    stations: list[Station], lat: float, lon: float
) -> StationChoice | None:
    """La meilleure station de départ (la plus proche atteignant le seuil),
    ou `None` si aucune ne convient."""
    ranked = rank_departure_stations(stations, lat, lon)
    return ranked[0] if ranked else None


def best_arrival_station(
    stations: list[Station], lat: float, lon: float, min_docks: int = MIN_DOCKS
) -> StationChoice | None:
    """La meilleure station d'arrivée (la plus proche atteignant le seuil),
    ou `None` si aucune ne convient."""
    ranked = rank_arrival_stations(stations, lat, lon, min_docks)
    return ranked[0] if ranked else None


# Permet de tester ce module seul : `uv run python -m velib_mcp.distance`
if __name__ == "__main__":
    from .geocode import geocode
    from .velib import get_stations

    print("Vérification de la distance Tour Eiffel → Arc de Triomphe :")
    d = haversine_km(48.8584, 2.2945, 48.8738, 2.2950)
    print(f"   {d:.2f} km (≈ 2,1 km attendu)\n")

    print("Récupération des stations…")
    stations = get_stations()

    depart = geocode("Tour Eiffel Paris")
    arrivee = geocode("place Napoleon III 75010 Paris")

    choix_depart = best_departure_station(stations, depart.lat, depart.lon)
    choix_arrivee = best_arrival_station(stations, arrivee.lat, arrivee.lon)

    print(f"\n🔋 DÉPART ({depart.label}) :")
    if choix_depart:
        s = choix_depart.station
        print(
            f"   {s.name} — {s.ebikes} vélos élec., "
            f"à {choix_depart.distance_km:.2f} km ({choix_depart.walk_min:.0f} min à pied)"
        )

    print(f"\n🅿️  ARRIVÉE ({arrivee.label}) :")
    if choix_arrivee:
        s = choix_arrivee.station
        print(
            f"   {s.name} — {s.free_docks} places libres, "
            f"à {choix_arrivee.distance_km:.2f} km ({choix_arrivee.walk_min:.0f} min à pied)"
        )
