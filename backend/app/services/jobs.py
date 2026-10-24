"""Background job dispatch. Celery when USE_CELERY=true (Docker/prod); otherwise a daemon thread so the stack
also runs on a laptop without Redis. HTTP requests only ever enqueue, never process."""
import threading

from ..config import settings


def enqueue_ingestion(dataset_id: str, job_id: str) -> str:
    if settings.USE_CELERY:
        from ..worker import ingest_dataset

        res = ingest_dataset.delay(dataset_id, job_id)
        return f"celery:{res.id}"
    from .ingest import process_dataset

    t = threading.Thread(target=process_dataset, args=(dataset_id, job_id, "thread"), daemon=True, name=f"ingest-{dataset_id[:6]}")
    t.start()
    return "thread"
