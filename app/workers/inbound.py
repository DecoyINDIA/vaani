"""Inbound worker — Redis Streams consumer (TRD §1, Week 3 task 3.3).

Consumer group; dead-letter after 3 retries. Kill mid-message -> reprocessed, not
lost. Pulls normalized inbound events, runs the agent graph, sends the reply
through app.channels + app.audit. Entrypoint: `python -m app.workers.inbound`.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("inbound worker — 06-engineering-plan task 3.3")


if __name__ == "__main__":
    main()
