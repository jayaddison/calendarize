from datetime import timedelta
from dateutil import parser as timeparser
import json

from jinja2 import Environment, FileSystemLoader
from ortools.sat.python.cp_model import CpModel, CpSolver


# Estimated venue transit times (by bicycle and allowing some time for parking)
transit_times = {
    "STA": {
        "CAM": 20,
        "EVR": 15,
        "FLH": 15,
        "VUE": 15,
    },
    "CAM": {
        "EVR": 20,
        "FLH": 10,
        "STA": 20,
        "VUE": 30,
    },
    "EVR": {
        "CAM": 20,
        "FLH": 20,
        "STA": 15,
        "VUE": 10,
    },
    "FLH": {
        "CAM": 10,
        "EVR": 20,
        "STA": 15,
        "VUE": 30,
    },
    "VUE": {
        "CAM": 30,
        "EVR": 10,
        "FLH": 30,
        "STA": 15,
    },
}
for prev, times in transit_times.items():
    for next in times.keys():
        assert transit_times[prev][next] == transit_times[next][prev]


class Venue(object):
    def __init__(self, id, name):
        self.id = id
        self.name = name


venues = {
    "CAM": Venue("CAM", "Cameo Cinema"),
    "EVR": Venue("EVR", "Everyman Cinema"),
    "FLH": Venue("FLH", "Filmhouse Cinema"),
    "STA": Venue("STA", "St. Andrew Square"),
    "VUE": Venue("VUE", "Vue Cinema"),
}


class Event(object):
    def __init__(self, title, begin, running_time, venue_id, url, description):
        self.title = title
        self.begin = timeparser.parse(begin)
        self.running_time = timedelta(minutes=running_time)
        self.end = self.begin + self.running_time
        self.venue = venues[venue_id]
        self.url = url
        self.description = description

    def minutes_from(self, prev: "Event"):
        if self.venue == prev.venue:
            return 5
        return transit_times[prev.venue.id][self.venue.id]

    def eta_from(self, prev: "Event"):
        return prev.end + timedelta(minutes=self.minutes_from(prev))


# Screenings, sorted by start time
events = []
for event_data in json.loads(open("events.json", "r").read()):
    for occurrence_data in event_data["occurrences"]:
        events.append(
            Event(
                title=event_data["title"],
                running_time=event_data["running_time"],
                url=event_data["url"],
                description=event_data["description"],
                begin=occurrence_data["time"],
                venue_id=occurrence_data["venue"],
            )
        )
events = sorted(events, key=lambda f: f.begin)
n = len(events)

model = CpModel()
attendance = model.NewIntVar(0, n, "attendance")
appearances = [model.NewBoolVar(f"appearances[{i}]") for i in range(n)]
commute = model.NewIntVar(0, 3600, "commute")
transits = [model.NewIntVar(0, 60, f"transits[{i}]") for i in range(n)]

model.Add(attendance == sum(appearances))
model.Add(commute == sum(transits))


# Constraints:
#
#  - Events must not overlap
#  - There must be enough time to transit between events
#  - Avoid duplicate events (based on title)
#
for i in range(n):
    for j in range(n):
        if i < j:
            chosen = [appearances[i], appearances[j]]
            prev, next = events[i], events[j]
            model.Add(next.begin >= prev.eta_from(prev)).OnlyEnforceIf(chosen)
            model.Add(next.title != prev.title).OnlyEnforceIf(chosen)

            # Don't add transit-related constraints across date boundaries
            if prev.begin.date() != next.begin.date():
                continue

            # Add transit time constraints
            adjacent = [appearances[b].Not() for b in range(i + 1, j)]
            duration = next.minutes_from(prev)
            model.Add(transits[j] == duration).OnlyEnforceIf(chosen + adjacent)

# Goal 1: maximize attendance
model.Maximize(attendance)

solver = CpSolver()
solver.Solve(model)

# Goal 2: minimize commute
model.Add(attendance == solver.Value(attendance))
model.Minimize(commute)

solver.Solve(model)

dates = {}
for i in range(n):
    if not solver.Value(appearances[i]):
        continue
    event = events[i]
    date = event.begin.date().strftime("%Y-%m-%d")
    if date not in dates:
        dates[date] = {
            "heading": event.begin.strftime("%d %b"),
            "is_weekend": event.begin.weekday() in [5, 6],
            "events": [],
        }
    dates[date]["events"].append(
        {
            "time": event.begin.strftime("%H:%M"),
            "title": event.title,
            "venue": event.venue.name,
            "url": event.url,
            "description": event.description,
        }
    )

# Render the suggested schedule using an HTML template
env = Environment(loader=FileSystemLoader("."))
template = env.get_template("schedule.html")
html = template.render(dates=dates)

print(html)
