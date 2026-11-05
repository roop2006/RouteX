"""
Road Network Service for RouteX.
Manages registered road segments, intersections, and traffic zones in PostgreSQL/PostGIS.
Ensures that key urban arterial corridors are registered with valid PostGIS geometries
so that corridor queries can genuinely resolve roads, intersections, and zones.
"""
import logging
from typing import Any
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.models.intersection import Intersection
from backend.app.models.road_segment import RoadSegment
from backend.app.models.traffic_zone import TrafficZone

logger = logging.getLogger(__name__)

# Key monitored urban intersections in Chennai
CHENNAI_INTERSECTIONS = [
    {
        "intersection_id": "INT_001",
        "name": "RouteX Test Intersection (Periamet)",
        "latitude": 13.0827,
        "longitude": 80.2707,
    },
    {
        "intersection_id": "INT_002",
        "name": "Chennai Central Junction",
        "latitude": 13.0824,
        "longitude": 80.2755,
    },
    {
        "intersection_id": "INT_003",
        "name": "Egmore Station Junction",
        "latitude": 13.0782,
        "longitude": 80.2608,
    },
    {
        "intersection_id": "INT_004",
        "name": "Anna Nagar Roundtana Junction",
        "latitude": 13.0850,
        "longitude": 80.2100,
    },
    {
        "intersection_id": "INT_005",
        "name": "T. Nagar Panagal Park Junction",
        "latitude": 13.0405,
        "longitude": 80.2337,
    },
    {
        "intersection_id": "INT_006",
        "name": "Guindy Kathipara Junction",
        "latitude": 13.0067,
        "longitude": 80.2026,
    },
]

# Key arterial road corridors connecting these hubs with real LineString geometries (lng lat)
CHENNAI_ROADS = [
    {
        "road_id": "ROAD_001",
        "road_name": "RouteX Main Road (Periamet Corridor)",
        "speed_limit": 50.0,
        "lanes": 3,
        "wkt": "LINESTRING(80.2690 13.0815, 80.2700 13.0820, 80.2707 13.0827, 80.2715 13.0835)",
    },
    {
        "road_id": "ROAD_002",
        "road_name": "EVR Periyar Salai (Poonamallee High Road)",
        "speed_limit": 50.0,
        "lanes": 6,
        "wkt": "LINESTRING(80.2755 13.0824, 80.2707 13.0827, 80.2608 13.0795, 80.2450 13.0790, 80.2280 13.0810, 80.2100 13.0850)",
    },
    {
        "road_id": "ROAD_003",
        "road_name": "Anna Salai (Mount Road Arterial)",
        "speed_limit": 60.0,
        "lanes": 6,
        "wkt": "LINESTRING(80.2780 13.0700, 80.2650 13.0600, 80.2520 13.0450, 80.2380 13.0300, 80.2180 13.0150, 80.2026 13.0067)",
    },
    {
        "road_id": "ROAD_004",
        "road_name": "Inner Ring Road (100 Feet Road)",
        "speed_limit": 60.0,
        "lanes": 6,
        "wkt": "LINESTRING(80.2100 13.0850, 80.1980 13.0700, 80.2050 13.0500, 80.2080 13.0300, 80.2026 13.0067)",
    },
    {
        "road_id": "ROAD_005",
        "road_name": "Grand Southern Trunk (GST) Road",
        "speed_limit": 60.0,
        "lanes": 6,
        "wkt": "LINESTRING(80.2026 13.0067, 80.1980 12.9980, 80.1900 12.9850, 80.1800 12.9700)",
    },
]

# Monitored traffic zones
CHENNAI_ZONES = [
    {
        "zone_id": "ZONE_001",
        "name": "RouteX Periamet Congestion Zone",
        "zone_type": "CONGESTION_MONITORING",
        "wkt": "POLYGON((80.268 13.0805, 80.273 13.0805, 80.273 13.085, 80.268 13.085, 80.268 13.0805))",
    },
    {
        "zone_id": "ZONE_002",
        "name": "Central Business & Railway Transit Zone",
        "zone_type": "HIGH_TRANSIT_HUB",
        "wkt": "POLYGON((80.255 13.075, 80.280 13.075, 80.280 13.090, 80.255 13.090, 80.255 13.075))",
    },
    {
        "zone_id": "ZONE_003",
        "name": "South Urban Tech Corridor Zone",
        "zone_type": "COMMERCIAL_CORRIDOR",
        "wkt": "POLYGON((80.195 13.000, 80.245 13.000, 80.245 13.050, 80.195 13.050, 80.195 13.000))",
    },
]


def ensure_arterial_network(db: Session) -> dict[str, int]:
    """
    Registers key Chennai arterial roads, intersections, and zones into PostGIS
    if not already present. Preserves any existing entities.
    """
    added_intersections = 0
    added_roads = 0
    added_zones = 0

    # 1. Intersections
    existing_int_ids = {i.intersection_id for i in db.query(Intersection.intersection_id).all()}
    for item in CHENNAI_INTERSECTIONS:
        if item["intersection_id"] not in existing_int_ids:
            point_wkt = f"POINT({item['longitude']} {item['latitude']})"
            inter = Intersection(
                intersection_id=item["intersection_id"],
                name=item["name"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                location=WKTElement(point_wkt, srid=4326),
            )
            db.add(inter)
            added_intersections += 1

    # 2. Road Segments
    existing_road_ids = {r.road_id for r in db.query(RoadSegment.road_id).all()}
    for item in CHENNAI_ROADS:
        if item["road_id"] not in existing_road_ids:
            road = RoadSegment(
                road_id=item["road_id"],
                road_name=item["road_name"],
                speed_limit=item["speed_limit"],
                lanes=item["lanes"],
                geometry=WKTElement(item["wkt"], srid=4326),
            )
            db.add(road)
            added_roads += 1

    # 3. Traffic Zones
    existing_zone_ids = {z.zone_id for z in db.query(TrafficZone.zone_id).all()}
    for item in CHENNAI_ZONES:
        if item["zone_id"] not in existing_zone_ids:
            zone = TrafficZone(
                zone_id=item["zone_id"],
                name=item["name"],
                zone_type=item["zone_type"],
                geometry=WKTElement(item["wkt"], srid=4326),
            )
            db.add(zone)
            added_zones += 1

    if added_intersections or added_roads or added_zones:
        db.commit()
        logger.info(
            f"Registered arterial infrastructure: +{added_intersections} intersections, "
            f"+{added_roads} roads, +{added_zones} zones."
        )

    return {
        "intersections_added": added_intersections,
        "roads_added": added_roads,
        "zones_added": added_zones,
    }
