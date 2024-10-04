import os

from schedulebot.bot import run_bot
from schedulebot.schedule import read_schedule


def main() -> None:
    token = os.getenv('TELE_TOKEN')
    if not token:
        raise RuntimeError('TELE_TOKEN environment variable is required')

    schedule = read_schedule('schedulebot/data')

    # Run the bot until the user presses Ctrl-C
    run_bot(token, schedule)


if __name__ == '__main__':
    main()
