from fastapi import APIRouter, HTTPException
import redis

from vision.streaming.redis_client import (
    TrafficRedis
)


router = APIRouter(
    prefix="/live-traffic",
    tags=["Live Traffic"]
)

redis_client = TrafficRedis()


@router.get("/")
@router.get("")
def get_live_traffic():

    try:
        data = redis_client.get_latest()
    except (redis.exceptions.RedisError, ConnectionError, TimeoutError, Exception) as err:
        raise HTTPException(
            status_code=503,
            detail=f"Redis service unavailable: {str(err)}"
        )

    if data is None:

        raise HTTPException(
            status_code=404,
            detail="No live traffic data available"
        )

    return data