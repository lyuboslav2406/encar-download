import shutil
import time

from .config import GENERATED_DIR


def cleanup_old_jobs(max_age_hours=24, max_jobs=30):
    if not GENERATED_DIR.exists():
        return

    now = time.time()
    max_age_seconds = max_age_hours * 60 * 60

    job_dirs = [item for item in GENERATED_DIR.iterdir() if item.is_dir()]
    for job_dir in job_dirs:
        age_seconds = now - job_dir.stat().st_mtime
        if age_seconds > max_age_seconds:
            shutil.rmtree(job_dir, ignore_errors=True)

    job_dirs = [item for item in GENERATED_DIR.iterdir() if item.is_dir()]
    job_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    for old_job in job_dirs[max_jobs:]:
        shutil.rmtree(old_job, ignore_errors=True)
