from datetime import timedelta
from dateutil import parser as timeparser

from ortools.sat.python.cp_model import (
    CpModel,
    CpSolver,
    CpSolverSolutionCallback,
)


transit_times = {
    "CAM": {
        "EVR": 20,
        "FLH": 10,
        "VUE": 30,
    },
    "EVR": {
        "CAM": 20,
        "FLH": 20,
        "VUE": 10,
    },
    "FLH": {
        "CAM": 10,
        "EVR": 20,
        "VUE": 30,
    },
    "VUE": {
        "CAM": 30,
        "EVR": 10,
        "FLH": 30,
    },
}


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
screenings = [
    Film(begin="2022-08-13 14:00", running_time=120, venue="CAM", title="First"),
    Film(begin="2022-08-13 18:00", running_time=60, venue="FLH", title="Second"),
    Film(begin="2022-08-13 19:00", running_time=120, venue="FLH", title="Third"),
]
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
        for i in range(n):
            if self.Value(appearances[i]):
                screening = screenings[i]
                print(f'"{screening.title}": {screening.begin}..{screening.end}')


solver = CpSolver()
solver.Solve(model, solution_callback=SolutionHandler())
