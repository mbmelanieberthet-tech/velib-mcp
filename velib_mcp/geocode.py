"""Étape 3 — Géocodage (adresse texte → coordonnées GPS).

Transforme « Tour Eiffel Paris » en un point précis (latitude, longitude)
grâce à l'API Adresse du gouvernement (api-adresse.data.gouv.fr),
gratuite et sans clé.

⚠️ Piège important : dans la réponse GeoJSON, les coordonnées arrivent
dans l'ordre [longitude, latitude], c'est-à-dire INVERSÉ par rapport à
l'usage courant. On fait donc bien attention en les lisant.
"""

from dataclasses import dataclass

import httpx

GEOCODE_URL = "https://api-adresse.data.gouv.fr/search/"


@dataclass
class Location:
    """Un lieu géocodé : l'adresse reconnue + sa position GPS."""

    label: str    # l'adresse « propre » renvoyée par l'API
    lat: float    # latitude
    lon: float    # longitude
    score: float  # confiance de l'API entre 0 (douteux) et 1 (excellent)


class AdresseIntrouvable(Exception):
    """Erreur levée quand l'API ne trouve aucune adresse correspondante."""


def geocode(adresse: str) -> Location:
    """Convertit une adresse texte en coordonnées GPS.

    Renvoie un objet `Location`. Lève `AdresseIntrouvable` si aucune
    adresse ne correspond.
    """
    response = httpx.get(
        GEOCODE_URL,
        params={"q": adresse, "limit": 1},  # on ne garde que le meilleur résultat
        timeout=10.0,
    )
    response.raise_for_status()

    features = response.json().get("features", [])
    if not features:
        raise AdresseIntrouvable(f"Aucune adresse trouvée pour : {adresse!r}")

    best = features[0]
    # ⚠️ ordre [longitude, latitude] dans le GeoJSON — on décompose dans le bon sens.
    lon, lat = best["geometry"]["coordinates"]
    label = best["properties"]["label"]
    score = best["properties"].get("score", 0.0)

    return Location(label=label, lat=lat, lon=lon, score=score)


# Permet de tester ce module seul : `uv run python -m velib_mcp.geocode`
if __name__ == "__main__":
    for adresse in ["Tour Eiffel Paris", "place Napoleon III 75010 Paris"]:
        lieu = geocode(adresse)
        print(f"{adresse!r}")
        print(f"   → {lieu.label}  (confiance {lieu.score:.2f})")
        print(f"   → latitude {lieu.lat}, longitude {lieu.lon}\n")
