# Velib MCP

Un serveur **MCP** (Model Context Protocol) local qui aide à planifier un trajet à vélo à Paris.

À partir d'une **adresse de départ** et d'une **adresse d'arrivée**, il renvoie :
- 🔋 la station Vélib la plus proche du départ (≤ 15 min à pied) avec le **plus de vélos électriques** disponibles ;
- 🅿️ la station Vélib la plus proche de l'arrivée (≤ 15 min à pied) avec le **plus de places libres**.

## Comment ça marche

| Brique | Rôle | Source |
|---|---|---|
| `velib_mcp/velib.py` | État en temps réel des stations | API Vélib GBFS (sans clé) |
| `velib_mcp/geocode.py` | Adresse → coordonnées GPS | api-adresse.data.gouv.fr (sans clé) |
| `velib_mcp/distance.py` | Distance à vol d'oiseau + sélection | formule de Haversine |
| `velib_mcp/server.py` | Serveur MCP exposé à Claude | transport stdio |

## Usage prévu

Utilisé en local via **Claude Desktop**. Exemple de question :
> « Je pars de la Tour Eiffel et je vais Gare du Nord, quelles stations Vélib ? »

## Développement

Projet géré avec [uv](https://docs.astral.sh/uv/). Python ≥ 3.12.

```bash
uv run python -m velib_mcp.server   # lancer le serveur (à partir de l'étape 5)
```
