"""Standalone CLI script to seed synthetic demo leads into PostgreSQL."""
import asyncio
import logging
import sys

from app.core.database import AsyncSessionLocal
from app.services.lead_service import LeadService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_data")


async def main():
    logger.info("Initializing demo data seed...")
    async with AsyncSessionLocal() as session:
        service = LeadService(db=session)
        lead_ids = await service.seed_demo_leads()
        logger.info("Done! Successfully seeded %d demo leads:", len(lead_ids))
        for lid in lead_ids:
            logger.info("  - Lead ID: %s", lid)


if __name__ == "__main__":
    asyncio.run(main())
