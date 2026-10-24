from celery import Celery

from .config import settings

celery_app = Celery("intellimetrics", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,
    task_serializer="json",
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="ingest_dataset", bind=True, max_retries=0)
def ingest_dataset(self, dataset_id: str, job_id: str):
    from .services.ingest import process_dataset

    process_dataset(dataset_id, job_id, runner="celery")
    return {"dataset_id": dataset_id}
