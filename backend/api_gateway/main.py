from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import httpx
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Gateway - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Hay que cambiar para cuando usemos docker
SERVICES = {
    "auth": "http://localhost:8001", 
    # "music": "http://localhost:8002",  # Lo agregaremos después
}

# 2. Creamos una ruta dinámica que atrape todo lo que empiece con /auth
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(path: str, request: Request):
    """
    Este endpoint intercepta cualquier tráfico hacia /auth/... 
    y lo reenvía al authentication_service.
    """
    # Construimos la URL destino (ej. http://localhost:8001/login)
    target_url = f"{SERVICES['auth']}/auth/{path}"  # agrega /auth/ aquí
    
    # Extraemos los datos de la petición original
    method = request.method
    headers = dict(request.headers)
    # Evitamos problemas con el host original
    headers.pop("host", None) 
    
    # Extraemos los query params (ej. ?code=12345)
    query_params = dict(request.query_params)
    
    # Extraemos el body si existe
    body = await request.body()

    # 3. Hacemos la petición al microservicio interno
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                params=query_params,
                content=body
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"El servicio de autenticación no está disponible: {exc}")

    # 4. Devolvemos la respuesta exacta al Frontend
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers)
    )