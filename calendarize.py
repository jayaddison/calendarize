from datetime import timedelta
from dateutil import parser as timeparser

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


class Event(object):
    def __init__(self, title, begin, running_time, venue):
        self.title = title
        self.begin = timeparser.parse(begin)
        self.running_time = timedelta(minutes=running_time)
        self.end = self.begin + self.running_time
        self.venue = venue

    def minutes_from(self, prev: "Event"):
        if self.venue == prev.venue:
            return 5
        return transit_times[prev.venue][self.venue]

    def eta_from(self, prev: "Event"):
        return prev.end + timedelta(minutes=self.minutes_from(prev))


# Screenings, sorted by start time
events = sorted(
    [
        Event(begin="2022-08-20 19:00", running_time=96, venue="VUE", title="After Yang"),

        Event(begin="2022-08-16 16:30", running_time=100, venue="VUE", title="Fogaréu"),
        Event(begin="2022-08-17 19:00", running_time=100, venue="FLH", title="Fogaréu"),

        Event(begin="2022-08-16 20:35", running_time=101, venue="FLH", title="Leonor Will Never Die"),
        Event(begin="2022-08-18 15:30", running_time=101, venue="VUE", title="Leonor Will Never Die"),

        Event(begin="2022-08-15 21:00", running_time=78, venue="EVR", title="LOLA"),
        Event(begin="2022-08-19 16:00", running_time=78, venue="VUE", title="LOLA"),

        Event(begin="2022-08-17 18:15", running_time=87, venue="VUE", title="Full Time"),
        Event(begin="2022-08-18 16:00", running_time=87, venue="FLH", title="Full Time"),

        Event(begin="2022-08-18 21:35", running_time=109, venue="VUE", title="Special Delivery"),
        Event(begin="2022-08-19 16:20", running_time=109, venue="VUE", title="Special Delivery"),

        Event(begin="2022-08-15 19:00", running_time=83, venue="CAM", title="Anonymous Club"),
        Event(begin="2022-08-17 21:30", running_time=83, venue="VUE", title="Anonymous Club"),

        Event(begin="2022-08-17 15:50", running_time=115, venue="VUE", title="Hallelujah"),
        Event(begin="2022-08-20 16:50", running_time=115, venue="FLH", title="Hallelujah"),

        Event(begin="2022-08-13 14:00", running_time=85, venue="VUE", title="The Territory"),
        Event(begin="2022-08-19 18:00", running_time=85, venue="EVR", title="The Territory"),

        Event(begin="2022-08-17 20:35", running_time=117, venue="VUE", title="The Forgiven"),

        Event(begin="2022-08-18 19:00", running_time=114, venue="VUE", title="The Score"),
        Event(begin="2022-08-20 13:30", running_time=114, venue="FLH", title="The Score"),

        Event(begin="2022-08-15 21:10", running_time=104, venue="VUE", title="AEIOU"),
        Event(begin="2022-08-16 14:00", running_time=104, venue="FLH", title="AEIOU"),

        Event(begin="2022-08-14 17:30", running_time=112, venue="VUE", title="Axiom"),
        Event(begin="2022-08-16 11:30", running_time=112, venue="VUE", title="Axiom"),

        Event(begin="2022-08-14 14:15", running_time=97, venue="VUE", title="Phantom Project"),
        Event(begin="2022-08-15 21:20", running_time=97, venue="CAM", title="Phantom Project"),

        Event(begin="2022-08-13 18:30", running_time=180, venue="FLH", title="The Plains"),

        Event(begin="2022-08-16 18:30", running_time=56, venue="VUE", title="Shadow"),

        Event(begin="2022-08-14 15:40", running_time=68, venue="FLH", title="EIFF New Visions"),

        Event(begin="2022-08-13 15:30", running_time=79, venue="FLH", title="Scotland's Voices"),

        Event(begin="2022-08-14 11:30", running_time=60, venue="FLH", title="The Making of A Bear Named Wojtek"),
    ],
    key=lambda f: f.begin,
)
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
            no_overlaps = [
                events[j].begin >= events[j].eta_from(events[i]),
            ]
            no_duplicates = [
                events[i].title != events[j].title,
            ]
            pair_selected = [appearances[i], appearances[j]]
            model.AddBoolAnd(no_overlaps + no_duplicates).OnlyEnforceIf(pair_selected)

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
        print(f"transits: {[self.Value(transits[i]) for i in range(n)]}")
        prev = None
        for i in range(n):
            if self.Value(appearances[i]):
                curr = events[i]
                if prev and prev.begin.date() == curr.begin.date():
                    minutes_between = int((curr.begin - prev.end).total_seconds() / 60)
                    transit_between = curr.minutes_from(prev)
                    break_between = minutes_between - transit_between

                    transit = "none" if prev.venue == curr.venue else f"{transit_between}m to {curr.venue}"
                    downtime = "none" if break_between <= 5 else f"{break_between}m"
                    print(f" ... (transit: {transit}, downtime: {downtime})", end="")
                print()
                print(f'{curr.begin} @ {curr.venue}: "{curr.title}"', end="")
                prev = curr
        print()


solver = CpSolver()
solver.Solve(model, solution_callback=SolutionHandler())


# Goal 2: minimize commute
model.Add(attendance == solver.Value(attendance))
model.Minimize(commute)

solver.Solve(model, solution_callback=SolutionHandler())
