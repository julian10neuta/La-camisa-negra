# dashboard_service/routers/dashboard_router.py
from typing import Literal

from fastapi import APIRouter, Header, Query

from ..services.composer import compose_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# El período de las recomendaciones lo valida FastAPI contra este Literal, igual
# que en recommendation_service. Se repite el literal en vez de importarlo porque
# este servicio NO depende del paquete del otro: son microservicios distintos y
# solo se hablan por HTTP. El precio es tener el valor en dos sitios; el beneficio
# es que no se acoplan.
PeriodParam = Literal["weekly", "monthly"]


@router.get("")
async def get_dashboard(
    days: int = Query(7, ge=1, le=365),
    top: int = Query(5, ge=1, le=20),
    period: PeriodParam = "weekly",
    limit: int = Query(15, ge=1, le=50),
    x_spotify_id: str = Header(...),
):
    """
    La pantalla del Dashboard entera, en una respuesta.

    Junta lo que piden la tarjeta CRC y el mockup: los tres top-5 de la ventana
    (canciones, artistas, álbumes), el resumen de escucha, y las recomendaciones.

    Parámetros:
      - `days`   : la ventana de las ESTADÍSTICAS. El diseño pide 24h y 7d, o sea
                   days=1 y days=7.
      - `top`    : cuántos en cada ranking (el diseño dice 5).
      - `period` : el de las RECOMENDACIONES (semanal/mensual), que sale de los
                   Ajustes del usuario y NO depende de `days`.
      - `limit`  : cuántas recomendaciones.

    Si un servicio de dentro falla, su parte viene a null y su nombre aparece en
    `failed`, pero el resto de la pantalla se sirve igual.
    """
    return await compose_dashboard(
        spotify_id=x_spotify_id, days=days, top=top, period=period, limit=limit
    )
