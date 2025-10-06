from __future__ import annotations

import argparse

from lifespan_bot.api_client import BinjieClient
from lifespan_bot.conversation import LifespanConversation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive Persian CLI for adaptive lifespan estimation"
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        help="Stable userId for server-side conversation context",
        default=None,
    )
    parser.add_argument(
        "--timeout",
        dest="timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds",
    )
    args = parser.parse_args()

    client = BinjieClient(timeout_seconds=args.timeout)
    conv = LifespanConversation(client, user_id=args.user_id)
    conv.run_cli()


if __name__ == "__main__":
    main()
