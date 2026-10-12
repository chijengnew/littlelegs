from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

import config
from auth import get_current_uid
from data import PLACES
from models import (
    FavoriteCreate,
    FavoriteRecord,
    HistoryCreate,
    HistoryRecord,
    ItineraryRequest,
    ItineraryResponse,
    Place,
    RecommendationResponse,
    SearchConditions,
)
from planner import plan_itinerary
from recommender import recommend
from repository import Repository, get_repository

app = FastAPI(title="LittleLegs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "authMode": config.AUTH_MODE, "dbMode": config.DB_MODE}


@app.get("/api/places")
def list_places() -> list[Place]:
    return PLACES


@app.post("/api/recommendations")
def create_recommendations(conditions: SearchConditions) -> RecommendationResponse:
    return recommend(conditions)


@app.post("/api/itineraries/plan")
def create_plan(request: ItineraryRequest) -> ItineraryResponse:
    return plan_itinerary(request.conditions, request.place_ids)


@app.get("/api/me")
def get_current_user(uid: str = Depends(get_current_uid)) -> dict[str, str]:
    return {"uid": uid}


@app.get("/api/me/history")
def list_history(
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> list[HistoryRecord]:
    return repo.list_history(uid)


@app.post("/api/me/history", status_code=status.HTTP_201_CREATED)
def save_history(
    body: HistoryCreate,
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> HistoryRecord:
    return repo.save_history(uid, body)


@app.delete("/api/me/history/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    record_id: str,
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> Response:
    if not repo.delete_history(uid, record_id):
        raise HTTPException(status_code=404, detail="history record not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/me/favorites")
def list_favorites(
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> list[FavoriteRecord]:
    return repo.list_favorites(uid)


@app.post("/api/me/favorites", status_code=status.HTTP_201_CREATED)
def save_favorite(
    body: FavoriteCreate,
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> FavoriteRecord:
    return repo.save_favorite(uid, body)


@app.delete("/api/me/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(
    favorite_id: str,
    uid: str = Depends(get_current_uid),
    repo: Repository = Depends(get_repository),
) -> Response:
    if not repo.delete_favorite(uid, favorite_id):
        raise HTTPException(status_code=404, detail="favorite not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)