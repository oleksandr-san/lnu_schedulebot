import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class WeekParity(str, Enum):
    ODD = 'odd'
    EVEN = 'even'


@dataclass
class ScheduleTemplateItem:
    slot: int
    name: str
    weekday: int
    start: time
    groups: List[str]
    week_parity: Optional[WeekParity] = None
    dates: Optional[List[date]] = None


@dataclass
class ScheduleTemplate:
    name: str
    title: str
    items: List[ScheduleTemplateItem]


@dataclass
class ScheduleItem:
    slot: int
    name: str
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


class ScheduleBook:
    def __init__(self):
        self._templates: List[ScheduleTemplateItem] = []
        self._group_index: Dict[str, List[ScheduleTemplateItem]] = {}

    def add_template(self, template: List[ScheduleTemplateItem]):
        """Adds a template and builds a group index for faster search."""
        self._templates.extend(template)
        for item in template:
            for group in item.groups:
                if group not in self._group_index:
                    self._group_index[group] = []
                self._group_index[group].append(item)

    def find_groups(self, pattern: str) -> Iterable[str]:
        """Find groups with schedule by pattern"""
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
        return (group for group in self._group_index if regex.search(group))

    def calculate_schedule(
        self,
        group: str,
        start: date,
        end: date,
    ) -> List[ScheduleItem]:
        if group not in self._group_index:
            return []

        current_date = start
        schedule = []
        while current_date <= end:
            weekday = current_date.weekday()
            week_parity = (
                WeekParity.ODD
                if current_date.isocalendar()[1] % 2 != 0
                else WeekParity.EVEN
            )

            for item in self._group_index[group]:
                if item.weekday == weekday and (
                    item.week_parity is None or item.week_parity == week_parity
                ):
                    if item.dates and current_date not in item.dates:
                        continue
                    start_datetime = datetime.combine(current_date, item.start)
                    # TODO: Make duration configurable
                    end_datetime = start_datetime + timedelta(minutes=90)
                    schedule_item = ScheduleItem(
                        slot=item.slot,
                        name=item.name,
                        start=start_datetime,
                        end=end_datetime,
                    )
                    schedule.append(schedule_item)

            current_date += timedelta(days=1)

        return schedule


class DateRangeRequest(Enum):
    TODAY = 'today'
    YESTERDAY = 'yesterday'
    TOMORROW = 'tomorrow'
    CURRENT_WEEK = 'current_week'
    LAST_WEEK = 'last_week'
    NEXT_WEEK = 'next_week'


def get_date_range(
    request: DateRangeRequest,
    today: Optional[date] = None,
) -> tuple[date, date]:
    today = today or date.today()

    if request == DateRangeRequest.TODAY:
        return today, today

    elif request == DateRangeRequest.YESTERDAY:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    elif request == DateRangeRequest.TOMORROW:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow

    elif request == DateRangeRequest.CURRENT_WEEK:
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week, end_of_week

    elif request == DateRangeRequest.LAST_WEEK:
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        return start_of_last_week, end_of_last_week

    elif request == DateRangeRequest.NEXT_WEEK:
        start_of_next_week = today - timedelta(days=today.weekday() - 7)
        end_of_next_week = start_of_next_week + timedelta(days=6)
        return start_of_next_week, end_of_next_week

    raise ValueError(f'Unknown schedule request: {request}')


def structure_template_item(data: dict) -> ScheduleTemplateItem:
    return ScheduleTemplateItem(
        slot=int(data['slot']),
        name=str(data['name']),
        weekday=int(data['weekday']),
        groups=list(data['groups']),
        start=time.fromisoformat(data['start']),
        week_parity=WeekParity(parity) if (parity := data.get('week_parity')) else None,
        dates=[date.fromisoformat(raw_date) for raw_date in dates]
        if (dates := data.get('dates'))
        else None,
    )


def structure_template(data: dict) -> ScheduleTemplate:
    items = [structure_template_item(item) for item in data.get('items', ())]
    return ScheduleTemplate(
        name=data['name'],
        title=data['title'],
        items=items,
    )


def unstructure_template(template: ScheduleTemplate) -> dict:
    return asdict(template)


def read_schedule(path: str) -> ScheduleBook:
    template = []

    if os.path.isdir(path):
        paths = [
            os.path.join(dirpath, file)
            for (dirpath, _, filenames) in os.walk(path)
            for file in filenames
        ]
    else:
        paths = [path]

    for filepath in paths:
        logger.info('Reading file %s', filepath)
        with open(filepath, encoding='utf-8') as fp:
            data = json.load(fp)
            template.extend(
                [structure_template_item(item) for item in data.get('items', ())]
            )

    book = ScheduleBook()
    book.add_template(template)
    return book


if __name__ == '__main__':
    book = read_schedule('data/schedule.json')
    print(book._templates)
