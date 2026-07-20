# rag_service/services/wikipedia_client.py
# Cliente de la API de MediaWiki (Wikipedia). NO requiere key ni cuenta: es una
# API pública de solo lectura. La usamos como FUENTE del RAG: de aquí sale el
# texto con el que el modelo tendrá permitido responder.
#
# Dos detalles que no son capricho:
#
#  1) User-Agent descriptivo. Wikimedia lo EXIGE en su política de uso; con el
#     User-Agent por defecto de las librerías responden 403. Debe identificar a
#     la aplicación y dar un contacto.
#
#  2) Buscamos primero en español y, si no hay nada, en inglés. La Wikipedia en
#     inglés tiene muchísimos más artículos de canciones; la española cubre bien
#     lo latino, que es justo el catálogo del usuario. Probar las dos en ese
#     orden da la mejor cobertura sin duplicar trabajo.
import httpx

USER_AGENT = (
    "LaCamisaNegra/0.1 (proyecto academico Universidad Nacional de Colombia; "
    "contacto: julian.albarracin.555@gmail.com)"
)

# Orden de preferencia de idiomas al buscar un artículo.
LANGS = ("es", "en")

TIMEOUT = 10


class WikipediaClient:
    def _api_url(self, lang: str) -> str:
        return f"https://{lang}.wikipedia.org/w/api.php"

    async def _get(self, lang: str, params: dict) -> dict:
        params = {**params, "format": "json", "formatversion": "2"}
        async with httpx.AsyncClient(
            timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = await client.get(self._api_url(lang), params=params)
        r.raise_for_status()
        return r.json()

    async def search(self, lang: str, query: str, limit: int = 8) -> list[dict]:
        """
        Candidatos para una búsqueda. Devuelve solo título y fragmento; NO baja
        el artículo entero, que eso se hace después y solo del elegido.
        """
        data = await self._get(
            lang,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
            },
        )
        results = (data.get("query") or {}).get("search") or []
        return [
            {
                "title": item["title"],
                # snippet viene con <span class="searchmatch"> dentro; para
                # decidir nos basta el texto, así que lo limpiamos a lo bruto.
                "snippet": _strip_html(item.get("snippet", "")),
            }
            for item in results
        ]

    async def get_extract(self, lang: str, title: str) -> dict | None:
        """
        El texto plano del artículo (sin wikitext ni HTML) más su URL pública,
        que es lo que luego citaremos como fuente.
        """
        data = await self._get(
            lang,
            {
                "action": "query",
                "prop": "extracts|info",
                "explaintext": "1",
                "inprop": "url",
                "titles": title,
                "redirects": "1",
            },
        )
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            return None

        page = pages[0]
        if page.get("missing") or not page.get("extract"):
            return None

        return {
            "title": page["title"],
            "url": page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{title}"),
            "lang": lang,
            "text": page["extract"],
        }


def _strip_html(raw: str) -> str:
    """Quita las etiquetas del snippet de búsqueda. No necesitamos un parser."""
    out = []
    inside = False
    for ch in raw:
        if ch == "<":
            inside = True
        elif ch == ">":
            inside = False
        elif not inside:
            out.append(ch)
    return "".join(out).replace("&quot;", '"').replace("&amp;", "&")
