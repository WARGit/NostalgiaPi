from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime

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
        )

    def is_active(self, hour: int, weekday: int, day: int, month: int) -> bool:
        # hour window (supports wrap past midnight)
        start = self.starthour
        end = self.endhour
        if start == end:
            in_hour = True  # 24h window
        elif start < end:
            in_hour = start <= hour < end
        else:
            in_hour = (hour >= start) or (hour < end)

        in_dow = (0 in self.daysofweek) or (weekday in self.daysofweek)
        in_month = (0 in self.months) or (month in self.months)
        in_date = (0 in self.dates) or (day in self.dates)
        return in_hour and in_dow and in_month and in_date

@dataclass
@dataclass
class System:
    action: str   # "restart" or "shutdown"
    hour: int
    minute: int

    @staticmethod
    def from_dict(data: dict) -> "System":
        return System(
            action=data.get("action", "restart"),  # default to restart if missing
            hour=data.get("hour", 2),              # default 02:00 if missing
            minute=data.get("minute", 0)           # default to 0 if missing
        )

# Class representing the config file
@dataclass
class Config:

    # attribute that
    schedules: Dict[str, Schedule]  # holds KVP of schedule objects str is the name and Schedule is the object
    system: System                  # holds the system object representing the config file

    def get_active_schedule_at(self, when: datetime) -> Schedule | None:
        active = [
            s for s in self.schedules.values()
            if s.is_active(
                hour=when.hour,
                weekday=(when.weekday() + 1),  # datetime: 0=Mon..6=Sun → we use 1..7
                day=when.day,
                month=when.month
            )
        ]
        if not active:
            return None
        # priority 1 is highest
        return sorted(active, key=lambda s: s.priority)[0]
