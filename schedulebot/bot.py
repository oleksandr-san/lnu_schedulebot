import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from babel.dates import format_date
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    DictPersistence,
    MessageHandler,
    filters,
)

from schedulebot.schedule import (
    DateRangeRequest,
    ScheduleBook,
    ScheduleItem,
    get_date_range,
)

if TYPE_CHECKING:
    from datetime import date

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class UserCatalog:
    def __init__(self):
        self._info = {}

    def find_user_info(self, user_id: int) -> dict | None:
        return self._info.get(user_id)

    def add_user_info(self, user_id: int, info: dict):
        if user_id in self._info:
            self._info[user_id].update(info)
        else:
            self._info[user_id] = info


BOT_BIO = """Тут можеш спитати щодо розкладу своєї групи.
Надсилай /start, щоб почати спілкування.
Надсилай зворотній зв'язок @lavander_ale.
"""


(
    SELECT_GROUP,
    SHOW_SCHEDULE,
) = range(2)


def parse_date_range(text: str) -> Optional[DateRangeRequest]:
    text = text.lower()
    for key, value in {
        'сьогодні': DateRangeRequest.TODAY,
        'завтра': DateRangeRequest.TOMORROW,
        'вчора': DateRangeRequest.YESTERDAY,
        'поточний тиждень': DateRangeRequest.CURRENT_WEEK,
        'наступний тиждень': DateRangeRequest.NEXT_WEEK,
        'минулий тиждень': DateRangeRequest.LAST_WEEK,
    }.items():
        if key in text:
            return value


def format_schedule_for_telegram(schedule_items: List[ScheduleItem]) -> Iterable[str]:
    # Group schedule items by day (date)
    schedule_by_day: Dict[date, List[ScheduleItem]] = defaultdict(list)
    for item in schedule_items:
        schedule_by_day[item.start.date()].append(item)

    # Sort schedule items by slot within each day
    for day, items in schedule_by_day.items():
        schedule_by_day[day] = sorted(items, key=lambda x: x.slot)

    # Prepare the message
    for day, items in sorted(schedule_by_day.items()):
        message_lines = []
        day_str = format_date(day, locale='uk_UA')  # Format the date
        message_lines.append(f'*{day_str}*\n')  # Bold day header (for Telegram)

        for item in items:
            start_time_str = item.start.strftime('%H:%M')
            end_time_str = item.end.strftime('%H:%M')
            message_lines.extend(
                [
                    f'{item.slot} ({start_time_str} - {end_time_str}): {item.name} ',
                    '\n',
                ]
            )

        message_lines.append('')  # Add an empty line between days
        yield '\n'.join(message_lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        raise RuntimeError('update.message is None')

    user = update.message and update.message.from_user
    if user and user.first_name:
        greeting = f'Вітаю, {user.first_name}!'
    else:
        greeting = 'Вітаю!'

    await update.message.reply_text(
        f'{greeting} Я покажу тобі поточний розклад. Будь ласка вкажи свою групу.\n\n'
        'Надсилай /cancel, щоб припинити спілкування.',
        reply_markup=ReplyKeyboardRemove(),
    )

    reply_markup = None
    if user and (user_info := context.user_data):
        if user_group := user_info.get('group'):
            reply_markup = ReplyKeyboardMarkup(
                [[user_group]],
                input_field_placeholder='Вкажи свою групу.',
                one_time_keyboard=True,
            )

    await update.message.reply_text(
        'Твоя група:',
        reply_markup=reply_markup,
    )
    return SELECT_GROUP


async def select_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        raise RuntimeError('update.message is None')

    schedule = context.bot_data.get('schedule')
    group = (update.message.text or '').upper()
    group_options = list(schedule.find_groups(group)) if schedule else []

    if not group_options:
        await update.message.reply_text(
            'На жаль, я не знаю про таку групу, спробуй іншу:'
        )
        return SELECT_GROUP

    elif len(group_options) > 1:
        reply_markup = ReplyKeyboardMarkup(
            [group_options],
            input_field_placeholder='Обери групу',
        )
        await update.message.reply_text(
            f"Я знайшов декілька груп: {', '.join(group_options)}. Обери одну.",
            reply_markup=reply_markup,
        )
        return SELECT_GROUP

    group = group_options[0]
    if context.user_data is not None:
        context.user_data['group'] = group

    start, end = get_date_range(DateRangeRequest.TODAY)
    items = schedule.calculate_schedule(group, start, end) if schedule else None

    today_summary = None
    today_schedule_text = None
    if items:
        today_summary = f'Сьогодні стіки пар: {len(items)}.'
        for schedule_text in format_schedule_for_telegram(items):
            today_schedule_text = schedule_text
    else:
        today_summary = 'Сьогодні вихідний!'

    await update.message.reply_text(
        f'Так, я знаю про таку групу - {group}.\n' f'{today_summary}'
    )
    if today_schedule_text:
        await update.message.reply_text(today_schedule_text)

    await update.message.reply_text(
        'Який розклад тобі потрібен?',
        reply_markup=ReplyKeyboardMarkup(
            [
                ['Вчора', 'Сьогодні', 'Завтра'],
                ['Минулий тиждень', 'Поточний тиждень', 'Наступний тиждень'],
            ],
            input_field_placeholder='Вкажи час',
        ),
    )
    return SHOW_SCHEDULE


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        raise RuntimeError('update.message is None')
    user = update.message.from_user
    if not user:
        raise RuntimeError('update.message.from_user is None')

    user_info = context.user_data
    group = user_info.get('group') if user_info else None
    if not user_info or not group:
        await update.message.reply_text(
            'Йой, схоже я забув яка в тебе група, нагадай будь ласка.',
        )
        return SELECT_GROUP

    date_range = parse_date_range(update.message.text or '')
    if not date_range:
        await update.message.reply_text(
            'Не розумію тебе, за який період ти хочеш побачити розклад?',
        )
        return SHOW_SCHEDULE

    start, end = get_date_range(date_range)

    schedule = context.bot_data.get('schedule')
    items = schedule.calculate_schedule(group, start, end) if schedule else None

    if not items:
        await update.message.reply_text(f'Вітаю, в {group} вихідні!')
    else:
        await update.message.reply_text(f'Осьо розклад для {group}:')
        for schedule_text in format_schedule_for_telegram(items):
            await update.message.reply_text(schedule_text)

    await update.message.reply_text(
        'Хочеш дізнатися розклад за інший період?\n'
        'Надсилай /cancel, щоб змінити групу або припинити спілкування.',
    )
    return SHOW_SCHEDULE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        raise RuntimeError('update.message is None')

    user = update.message.from_user
    logger.info('User %s canceled the conversation.', user and user.first_name)
    await update.message.reply_text(
        'Прощавай! Сподіваюсь почути тебе знову.\n'
        'Надсилай /start, щоб почати спілкування.',
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


def build_bot(
    token: str,
    schedule: ScheduleBook,
) -> Application:
    builder = Application.builder()
    builder = builder.token(token)

    persistence = DictPersistence()
    persistence._bot_data = {
        'schedule': schedule,
    }

    builder = builder.persistence(persistence)
    application = builder.build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_group)
            ],
            SHOW_SCHEDULE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, show_schedule)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    return application


def run_bot(
    token: str,
    schedule: ScheduleBook,
):
    bot = build_bot(token, schedule)
    bot.run_polling(allowed_updates=Update.ALL_TYPES)
