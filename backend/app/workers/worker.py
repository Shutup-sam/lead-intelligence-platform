import asyncio
import logging
from arq.connections import RedisSettings
from arq.worker import run_worker

from app.core.config import settings
from app.workers.jobs import crawl_domain_job, qualify_lead_job, crawl_and_qualify_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("lead_intelligence.worker")


async def startup(ctx):
    logger.info("ARQ Worker starting up. Connected to Redis at %s", settings.REDIS_URL)


async def shutdown(ctx):
    logger.info("ARQ Worker shutting down cleanly.")


class WorkerSettings:
    """ARQ Worker configuration settings."""
    functions = [crawl_domain_job, qualify_lead_job, crawl_and_qualify_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    queue_name = settings.ARQ_QUEUE_NAME
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    on_startup = startup
    on_shutdown = shutdown


def main():
    """CLI entrypoint for running the ARQ worker process."""
    logger.info("Starting ARQ Worker process...")
    asyncio.run(run_worker(WorkerSettings))


if __name__ == "__main__":
    main()
