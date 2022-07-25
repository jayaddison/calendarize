from datetime import timedelta
from dateutil import parser as timeparser
import json

from ortools.sat.python.cp_model import (
    CpModel,
    CpSolver,
    CpSolverSolutionCallback,
)


# Transit times, assuming travel by bicycle and with a bit of faff time to find parking
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
    def __init__(self, title, begin, running_time, venue_id):
        self.title = title
        self.begin = timeparser.parse(begin)
        self.running_time = timedelta(minutes=running_time)
        self.end = self.begin + self.running_time
        self.venue = venues[venue_id]

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
        events.append(Event(
            title=event_data["title"],
            running_time=event_data["running_time"],
            begin=occurrence_data["time"],
            venue_id=occurrence_data["venue"],
        ))
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
            pair_selected = [appearances[i], appearances[j]]
            model.Add(events[j].begin >= events[j].eta_from(events[i])).OnlyEnforceIf(pair_selected)
            model.Add(events[i].title != events[j].title).OnlyEnforceIf(pair_selected)

            # For same-day events, accumulate transit times
            if events[i].begin.date() == events[j].begin.date():
                no_events_between = [appearances[b].Not() for b in range(i+1, j)]
                transit_time = events[j].minutes_from(events[i])
                model.Add(transits[j] == transit_time).OnlyEnforceIf(pair_selected + no_events_between)

# Goal 1: maximize attendance
model.Maximize(attendance)


class SolutionHandler(CpSolverSolutionCallback):
    def on_solution_callback(self):
        print(f"attendance: {self.Value(attendance)}")
        print(f"appearances: {[self.Value(appearances[i]) for i in range(n)]}")
        print(f"commute: {self.Value(commute)}")
        print(f"transits: {[self.Value(transits[i]) for i in range(n)]}", end="")
        prev = None
        for i in range(n):
            if self.Value(appearances[i]):
                curr = events[i]
                if prev and prev.begin.date() == curr.begin.date():
                    minutes_between = int((curr.begin - prev.end).total_seconds() / 60)
                    transit = self.Value(transits[i])
                    downtime = minutes_between - transit

                    downtime = "none" if downtime <= 5 else f"{downtime}m"
                    print(f" ... (transit: {transit}m, downtime: {downtime})", end="")
                else:
                    print()
                print()
                print(f'{curr.begin} @ {curr.venue.id}: "{curr.title}"', end="")
                prev = curr
        print()


solver = CpSolver()
solver.Solve(model, solution_callback=SolutionHandler())


# Goal 2: minimize commute
model.Add(attendance == solver.Value(attendance))
model.Minimize(commute)

solver.Solve(model, solution_callback=SolutionHandler())
