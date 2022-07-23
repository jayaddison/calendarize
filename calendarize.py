from datetime import timedelta
from dateutil import parser as timeparser

from ortools.sat.python.cp_model import (
    CpModel,
    CpSolver,
    CpSolverSolutionCallback,
)


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


class Film(object):
    def __init__(self, title, begin, running_time, venue):
        self.title = title
        self.begin = timeparser.parse(begin)
        self.running_time = timedelta(minutes=running_time)
        self.end = self.begin + self.running_time
        self.venue = venue

    def minutes_from(self, prev: "Film"):
        if self.venue == prev.venue:
            return 5
        return transit_times[prev.venue][self.venue]

    def eta_from(self, prev: "Film"):
        return prev.end + timedelta(minutes=self.minutes_from(prev))


# Screenings, sorted by start time
screenings = sorted(
    [
        Film(begin="2022-08-20 19:00", running_time=96, venue="VUE", title="After Yang"),

        Film(begin="2022-08-16 16:30", running_time=100, venue="VUE", title="Fogaréu"),
        Film(begin="2022-08-17 19:00", running_time=100, venue="FLH", title="Fogaréu"),

        Film(begin="2022-08-16 20:35", running_time=101, venue="FLH", title="Leonor Will Never Die"),
        Film(begin="2022-08-18 15:30", running_time=101, venue="VUE", title="Leonor Will Never Die"),

        Film(begin="2022-08-15 21:00", running_time=78, venue="EVR", title="LOLA"),
        Film(begin="2022-08-19 16:00", running_time=78, venue="VUE", title="LOLA"),

        Film(begin="2022-08-17 18:15", running_time=87, venue="VUE", title="Full Time"),
        Film(begin="2022-08-18 16:00", running_time=87, venue="FLH", title="Full Time"),

        Film(begin="2022-08-18 21:35", running_time=109, venue="VUE", title="Special Delivery"),
        Film(begin="2022-08-19 16:20", running_time=109, venue="VUE", title="Special Delivery"),

        Film(begin="2022-08-15 19:00", running_time=83, venue="CAM", title="Anonymous Club"),
        Film(begin="2022-08-17 21:30", running_time=83, venue="VUE", title="Anonymous Club"),

        Film(begin="2022-08-17 15:50", running_time=115, venue="VUE", title="Hallelujah"),
        Film(begin="2022-08-20 16:50", running_time=115, venue="FLH", title="Hallelujah"),

        Film(begin="2022-08-13 14:00", running_time=85, venue="VUE", title="The Territory"),
        Film(begin="2022-08-19 18:00", running_time=85, venue="EVR", title="The Territory"),

        Film(begin="2022-08-17 20:35", running_time=117, venue="VUE", title="The Forgiven"),

        Film(begin="2022-08-18 19:00", running_time=114, venue="VUE", title="The Score"),
        Film(begin="2022-08-20 13:30", running_time=114, venue="FLH", title="The Score"),

        Film(begin="2022-08-15 21:10", running_time=104, venue="VUE", title="AEIOU"),
        Film(begin="2022-08-16 14:00", running_time=104, venue="FLH", title="AEIOU"),

        Film(begin="2022-08-14 17:30", running_time=112, venue="VUE", title="Axiom"),
        Film(begin="2022-08-16 11:30", running_time=112, venue="VUE", title="Axiom"),

        Film(begin="2022-08-14 14:15", running_time=97, venue="VUE", title="Phantom Project"),
        Film(begin="2022-08-15 21:20", running_time=97, venue="CAM", title="Phantom Project"),

        Film(begin="2022-08-13 18:30", running_time=180, venue="FLH", title="The Plains"),

        Film(begin="2022-08-16 18:30", running_time=56, venue="VUE", title="Shadow"),

        Film(begin="2022-08-14 15:40", running_time=68, venue="FLH", title="EIFF New Visions"),

        Film(begin="2022-08-13 15:30", running_time=79, venue="FLH", title="Scotland's Voices"),

        Film(begin="2022-08-14 11:30", running_time=60, venue="FLH", title="The Making of A Bear Named Wojtek"),
    ],
    key=lambda f: f.begin,
)
n = len(screenings)

model = CpModel()
attendance = model.NewIntVar(0, n, "attendance")
appearances = [model.NewBoolVar(f"appearances[{i}]") for i in range(n)]

# Constraints:
#
#  - Screenings must not overlap
#  - There must be enough time to transit between screenings
#  - Only watch each film once during the event
#
for i in range(n):
    for j in range(n):
        if i < j:
            no_overlaps = [
                screenings[j].begin >= screenings[j].eta_from(screenings[i]),
            ]
            no_duplicates = [
                screenings[i].title != screenings[j].title,
            ]
            pair_selected = [appearances[i], appearances[j]]
            model.AddBoolAnd(no_overlaps + no_duplicates).OnlyEnforceIf(pair_selected)

# Goal: maximize attendance
model.Add(attendance == sum(appearances))
model.Maximize(attendance)


class SolutionHandler(CpSolverSolutionCallback):
    def on_solution_callback(self):
        print(f"attendance: {self.Value(attendance)}")
        print(f"appearances: {[self.Value(appearances[i]) for i in range(n)]}")
        prev = None
        for i in range(n):
            if self.Value(appearances[i]):
                curr = screenings[i]
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
