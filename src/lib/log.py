import time
from datetime import datetime

from lib.config import TIMEZONE, MAX_RETRIES


def log(message):
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} Cairo] {message}", flush=True)


def retry_call(operation, label):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            return operation()

        except Exception as error:

            last_error = error

            if attempt >= MAX_RETRIES:
                break

            delay = 2 ** (attempt - 1)

            log(f"{label} failed ({attempt}/{MAX_RETRIES}): {error}")
            log(f"Retrying in {delay}s...")

            time.sleep(delay)

    raise RuntimeError(
        f"{label} failed after {MAX_RETRIES} attempts: {last_error}"
    )
