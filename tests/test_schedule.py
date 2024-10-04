import unittest
from datetime import date, datetime, time

from schedulebot.schedule import (
    DateRangeRequest,
    ScheduleBook,
    ScheduleTemplateItem,
    WeekParity,
    get_date_range,
)


class TestScheduleBook(unittest.TestCase):
    def setUp(self):
        self.book = ScheduleBook()
        # Creating a template to use in tests
        self.template = [
            ScheduleTemplateItem(
                slot=1,
                name='Math',
                weekday=0,  # Monday
                start=time(9, 0),
                groups=['GroupA', 'GroupB'],
                week_parity=WeekParity.ODD,
            ),
            ScheduleTemplateItem(
                slot=2,
                name='Physics',
                weekday=2,  # Wednesday
                start=time(11, 0),
                groups=['GroupA'],
                week_parity=WeekParity.EVEN,
            ),
            ScheduleTemplateItem(
                slot=3,
                name='Chemistry',
                weekday=4,  # Friday
                start=time(14, 0),
                groups=['GroupB'],
                week_parity=None,  # Happens every week
            ),
        ]
        self.book.add_template(self.template)

    def test_find_groups(self):
        # Case insensitive matching for group names
        self.assertIn('GroupA', list(self.book.find_groups('groupa')))
        self.assertIn('GroupB', list(self.book.find_groups('group')))
        self.assertNotIn('GroupC', list(self.book.find_groups('group')))

    def test_calculate_schedule_for_group_odd_week(self):
        start = date(2024, 10, 7)  # Monday, odd week (week 41)
        end = date(2024, 10, 11)  # Friday, same week
        schedule = self.book.calculate_schedule('GroupA', start, end)

        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0].name, 'Math')
        self.assertEqual(schedule[0].start, datetime(2024, 10, 7, 9, 0))
        self.assertEqual(schedule[0].end, datetime(2024, 10, 7, 10, 30))

    def test_calculate_schedule_for_group_even_week(self):
        start = date(2024, 10, 14)  # Monday, even week (week 42)
        end = date(2024, 10, 18)  # Friday, same week
        schedule = self.book.calculate_schedule('GroupA', start, end)

        # Expected events: No Math on Monday, Physics on Wednesday
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0].name, 'Physics')
        self.assertEqual(schedule[0].start, datetime(2024, 10, 16, 11, 0))
        self.assertEqual(schedule[0].end, datetime(2024, 10, 16, 12, 30))

    def test_calculate_schedule_for_group_b_every_week(self):
        start = date(2024, 10, 7)  # Monday, odd week (week 41)
        end = date(2024, 10, 11)  # Friday, same week
        schedule = self.book.calculate_schedule('GroupB', start, end)

        # Expected events: Math on Monday (odd week), Chemistry on Friday
        self.assertEqual(len(schedule), 2)
        self.assertEqual(schedule[0].name, 'Math')
        self.assertEqual(schedule[0].start, datetime(2024, 10, 7, 9, 0))
        self.assertEqual(schedule[0].end, datetime(2024, 10, 7, 10, 30))
        self.assertEqual(schedule[1].name, 'Chemistry')
        self.assertEqual(schedule[1].start, datetime(2024, 10, 11, 14, 0))
        self.assertEqual(schedule[1].end, datetime(2024, 10, 11, 15, 30))

    def test_empty_schedule_for_nonexistent_group(self):
        start = date(2024, 10, 7)
        end = date(2024, 10, 11)
        schedule = self.book.calculate_schedule('NonexistentGroup', start, end)

        # Expect no events
        self.assertEqual(len(schedule), 0)


class TestGetDateRange(unittest.TestCase):
    def test_today(self):
        result = get_date_range(DateRangeRequest.TODAY, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 10, 3), date(2024, 10, 3)))

    def test_yesterday(self):
        result = get_date_range(DateRangeRequest.YESTERDAY, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 10, 2), date(2024, 10, 2)))

    def test_tomorrow(self):
        result = get_date_range(DateRangeRequest.TOMORROW, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 10, 4), date(2024, 10, 4)))

    def test_current_week(self):
        result = get_date_range(DateRangeRequest.CURRENT_WEEK, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 9, 30), date(2024, 10, 6)))

    def test_last_week(self):
        result = get_date_range(DateRangeRequest.LAST_WEEK, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 9, 23), date(2024, 9, 29)))

    def test_next_week(self):
        result = get_date_range(DateRangeRequest.NEXT_WEEK, today=date(2024, 10, 3))
        self.assertEqual(result, (date(2024, 10, 7), date(2024, 10, 13)))
