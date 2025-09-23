from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime
import logging

@dataclass
class Schedule:
    priority: int
    daysofweek: List[int]   # 1–7 for Mon–Sun, 0 = Any   (note: we pass weekday+1)
    dates: List[int]        # 1–31, 0 = Any
    months: List[int]       # 1–12, 0 = Any
    starthour: int          # 0–23
    startminute: int        # 0–59
    endhour: int            # 0–23
    endminute: int          # 0–59
    shows: List[str]
    ads: List[str]
    bumpers: List[str]
    bumper_chance: float = 0.5  # default 50% chance

    @classmethod
    def from_dict(cls, data: Dict) -> "Schedule":
        return cls(
            priority=int(data["priority"]),
            daysofweek=[int(x) for x in data["daysofweek"]],
            dates=[int(x) for x in data["dates"]],
            months=[int(x) for x in data["months"]],
            starthour=int(data["starthour"]),
            startminute=int(data["startminute"]),
            endhour=int(data["endhour"]),
            endminute=int(data["endminute"]),
            shows=list(data["shows"]),
            ads=list(data["ads"]),
            bumpers=list(data["bumpers"]),
            bumper_chance=data["bumper_chance"],
        )

    def is_active(self, hour: int, weekday: int, day: int, month: int) -> bool:
        # hour window (supports wrap past midnight)
        start = self.starthour
        end = self.endhour
        if start == end:
            logging.debug(f"Schedule runs for 24 hours")
            within_hour = True  # This schedule runs for 24 hours
            logging.debug(f"24 hour window active, start={start}, end={end} ")
        elif start < end:
            logging.debug(f"Schedule runs between {start} and {end} on same day")
            within_hour = start <= hour < end
            logging.debug(f"within_hour {within_hour}, start={start}, hour={hour} end={end} ")
        else:
            logging.debug(f"Schedule runs between {start} and {end} and crosses midnight")
            within_hour = (hour >= start) or (hour < end)

        logging.debug(f"within_hour {within_hour}")
        within_days_of_week = (0 in self.daysofweek) or (weekday in self.daysofweek)
        logging.debug(f"within_days_of_week {within_days_of_week}")
        within_month = (0 in self.months) or (month in self.months)
        logging.debug(f"within_month {within_month}")
        within_date = (0 in self.dates) or (day in self.dates)
        logging.debug(f"within_date {within_date}")
        return within_hour and within_days_of_week and within_month and within_date

@dataclass
class System:
    action: str   # "restart" or "shutdown"
    hour: int
    minute: int
    bumper_chance: float
    create_debug_file: bool = False  # default = off

    @staticmethod
    def from_dict(data: dict) -> "System":
        return System(
            action=data.get("action", "restart"),  # default to restart if missing
            hour=data.get("hour", 2),              # default 02:00 if missing
            minute=data.get("minute", 0),           # default to 0 if missing
            bumper_chance = float(data.get("bumper_chance", 0.5)), # default to 50% chance
            create_debug_file = bool(data.get("create_debug_file", False)) # determines if debug log will be used
        )

# Class representing the config file
@dataclass
class Config:

    schedules: Dict[str, Schedule]  # holds KVP of schedule objects str is the name and Schedule is the object
    system: System                  # holds the system object representing the config file

    def get_active_schedule_at(self, when: datetime) -> Schedule | None:
        logging.debug(f"Begin get_active_schedule_at")
        active = [
            s for s in self.schedules.values()
            if s.is_active(
                hour=when.hour,
                weekday=(when.weekday() + 1),  # datetime: 0=Mon..6=Sun, we use 1-7 as 0 is any day
                day=when.day,
                month=when.month
            )
        ]
        if not active:
            logging.debug(f"No active schedule")
            return None

        # priority 1 is highest
        return sorted(active, key=lambda s: s.priority)[0]
