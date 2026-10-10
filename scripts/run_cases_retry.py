"""Run the kit's run_cases.py unmodified, with bounded retries on idempotent GETs that return 5xx.

    python scripts/run_cases_retry.py <agent_id> --brief A [run_cases.py arguments...]

The kit client has no retry: one 503 while polling a simulation ("API key validation is temporarily
unavailable", 10 Oct 19:53 UTC) ended a 3-rep run after rep 1 and left its simulation running.
Only GETs are retried (POST/PUT are not idempotent); 4xx errors are never retried.
"""

import logging
import re
import runpy
import sys
import time

from _kit import KIT, freya

log = logging.getLogger("run_cases_retry")
DELAYS = (5, 15, 30, 60, 120)
_api = freya.api


def api_with_retry(method, path, body=None, **params):
    for delay in (*DELAYS, None):
        try:
            return _api(method, path, body, **params)
        except RuntimeError as e:
            status = re.search(r"-> (\d{3}):", str(e))
            if method != "GET" or delay is None or not status or not status[1].startswith("5"):
                raise
            log.warning("GET %s -> %s; retry in %d s", path, status[1], delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    freya.api = api_with_retry
    sys.argv = [str(KIT / "tools" / "run_cases.py"), *sys.argv[1:]]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()
