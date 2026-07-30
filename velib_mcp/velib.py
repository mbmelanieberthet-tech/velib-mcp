"""Étape 2 — Appel de l'API Vélib (GBFS).

Ce module va chercher, en temps réel, l'état des stations Vélib et le
renvoie sous une forme simple et propre : une liste d'objets `Station`
ne contenant que les champs dont on a besoin pour choisir une station.

L'API Vélib expose deux flux séparés, reliés par un `station_id` commun :
  - station_information : infos fixes  (nom, position GPS, capacité)
  - station_status      : temps réel   (vélos dispo, places libres...)
On les télécharge tous les deux, puis on les fusionne.
"""

from dataclasses import dataclass

import httpx

# Adresses des deux flux de l'API Vélib (données ouvertes, aucune clé requise).
_BASE = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
STATION_INFORMATION_URL = f"{_BASE}/station_information.json"
STATION_STATUS_URL = f"{_BASE}/station_status.json"


@dataclass
class Station:
    """Une station Vélib, réduite aux informations qui nous servent."""

    station_id: int
    name: str
    lat: float          # latitude (position nord-sud)
    lon: float          # longitude (position est-ouest)
    capacity: int       # nombre total de points d'attache
    ebikes: int         # vélos électriques disponibles
    mechanical: int     # vélos mécaniques disponibles
    free_docks: int     # places libres pour reposer un vélo
    is_renting: bool    # la station prête-t-elle des vélos ?
    is_returning: bool  # la station accepte-t-elle qu'on repose un vélo ?

    @property
    def bikes_total(self) -> int:
        """Total de vélos disponibles (électriques + mécaniques)."""
        return self.ebikes + self.mechanical


def _fetch_json(url: str) -> dict:
    """Télécharge une URL et renvoie son contenu JSON sous forme de dictionnaire."""
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()  # lève une erreur claire si l'API répond mal
    return response.json()


def _count_bikes_by_type(types_list: list | None) -> dict:
    """Transforme la liste [{"mechanical": 2}, {"ebike": 5}] en un dictionnaire
    simple {"mechanical": 2, "ebike": 5}."""
    counts = {"mechanical": 0, "ebike": 0}
    for entry in types_list or []:
        for bike_type, amount in entry.items():
            counts[bike_type] = amount
    return counts


def get_stations() -> list[Station]:
    """Récupère l'état de toutes les stations Vélib et le renvoie sous forme
    d'une liste d'objets `Station` prêts à l'emploi."""
    information = _fetch_json(STATION_INFORMATION_URL)["data"]["stations"]
    status = _fetch_json(STATION_STATUS_URL)["data"]["stations"]

    # On indexe le statut temps réel par station_id pour le retrouver vite.
    status_by_id = {s["station_id"]: s for s in status}

    stations: list[Station] = []
    for info in information:
        live = status_by_id.get(info["station_id"])
        if live is None:
            continue  # station présente dans un flux mais pas l'autre : on l'ignore

        counts = _count_bikes_by_type(live.get("num_bikes_available_types"))
        stations.append(
            Station(
                station_id=info["station_id"],
                name=info["name"],
                lat=info["lat"],
                lon=info["lon"],
                capacity=info.get("capacity", 0),
                ebikes=counts["ebike"],
                mechanical=counts["mechanical"],
                free_docks=live.get("num_docks_available", 0),
                is_renting=bool(live.get("is_renting", 0)),
                is_returning=bool(live.get("is_returning", 0)),
            )
        )
    return stations


# Permet de tester ce module seul : `uv run python -m velib_mcp.velib`
if __name__ == "__main__":
    stations = get_stations()
    print(f"✅ {len(stations)} stations récupérées.\n")
    print("Exemple — 3 premières stations :")
    for station in stations[:3]:
        print(
            f"  • {station.name} "
            f"({station.ebikes} vélos élec., {station.free_docks} places libres)"
        )
