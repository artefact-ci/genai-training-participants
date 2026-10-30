"""Démo : un serveur MCP en quelques lignes avec FastMCP."""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p / "socle" for p in Path(__file__).resolve().parents if (p / "socle" / "outils.py").exists())))

from fastmcp import FastMCP
from outils import _get_schedule

mcp = FastMCP("lagune-demo")


@mcp.tool
def get_schedule(client_id: str) -> dict:
    """Échéancier des prêts en cours ou impayés du client."""
    return _get_schedule(client_id)


if __name__ == "__main__":
    mcp.run(show_banner=False)
