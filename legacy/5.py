import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = [
            "F1", "F2", "F3", "F4", "F5", "F6",
            "F7", "F8", "F9", "F10", "F11", "F12",
        ]
        self.service_areas = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        self.crews = ["K1", "K2", "K3"]
        self.periods = [t for t in range(0, 15, 1)]
        self.budget = 17000

        # capacity that a facility can ship in a single period
        self.capacity = {
            "F1": 70, "F2": 100, "F3": 160, "F4": 80, "F5": 150, "F6": 60,
            "F7": 110, "F8": 170, "F9": 90, "F10": 120, "F11": 130, "F12": 100,
        }

        self.opening_costs = {
            "F1": 300, "F2": 260, "F3": 220, "F4": 340, "F5": 240, "F6": 280,
            "F7": 300, "F8": 200, "F9": 250, "F10": 320, "F11": 360, "F12": 280,
        }

        # number of periods it takes to construct a facility
        self.build_time = {
            "F1": 3, "F2": 2, "F3": 1, "F4": 4, "F5": 2, "F6": 2,
            "F7": 3, "F8": 1, "F9": 2, "F10": 1, "F11": 3, "F12": 2,
        }

        # (first, second): the construction of 'second' can only start once the
        # construction of 'first' has been completed, and 'second' can only be
        # opened if 'first' is opened as well
        self.dependencies = [
            ("F1", "F2"),
            ("F2", "F3"),
            ("F4", "F5"),
            ("F6", "F7"),
            ("F7", "F8"),
        ]

        # demand of a service area in a period of average season
        self.base_demand = {
            "S1": 90, "S2": 130, "S3": 70, "S4": 110,
            "S5": 150, "S6": 80, "S7": 120, "S8": 100,
        }

        # seasonal multiplier applied to the base demand in each period
        self.seasonal_factor = {
            0: 0.6, 1: 0.8, 2: 1.3, 3: 1.5, 4: 0.6,
            5: 0.8, 6: 1.3, 7: 1.5, 8: 0.6, 9: 0.8,
            10: 1.3, 11: 1.5, 12: 0.6, 13: 0.8, 14: 1.3,
        }

        # demand of a service area in a single period
        self.demand = {
            s: {
                t: int(self.base_demand[s] * self.seasonal_factor[t])
                for t in self.periods
            }
            for s in self.service_areas
        }

        self.unit_selling_price = {
            "S1": 15, "S2": 11, "S3": 19, "S4": 13,
            "S5": 9, "S6": 21, "S7": 17, "S8": 12,
        }

        self.unit_shipping_cost = {
            "F1": {"S1": 6, "S2": 3, "S3": 2, "S4": 6, "S5": 8, "S6": 8, "S7": 7, "S8": 4},
            "F2": {"S1": 5, "S2": 6, "S3": 9, "S4": 2, "S5": 5, "S6": 9, "S7": 2, "S8": 3},
            "F3": {"S1": 2, "S2": 6, "S3": 5, "S4": 2, "S5": 5, "S6": 4, "S7": 2, "S8": 2},
            "F4": {"S1": 2, "S2": 7, "S3": 4, "S4": 5, "S5": 7, "S6": 7, "S7": 6, "S8": 7},
            "F5": {"S1": 2, "S2": 6, "S3": 2, "S4": 6, "S5": 6, "S6": 2, "S7": 2, "S8": 2},
            "F6": {"S1": 7, "S2": 5, "S3": 3, "S4": 3, "S5": 3, "S6": 8, "S7": 2, "S8": 6},
            "F7": {"S1": 6, "S2": 7, "S3": 3, "S4": 7, "S5": 6, "S6": 6, "S7": 9, "S8": 5},
            "F8": {"S1": 3, "S2": 2, "S3": 2, "S4": 2, "S5": 6, "S6": 2, "S7": 4, "S8": 2},
            "F9": {"S1": 3, "S2": 8, "S3": 4, "S4": 9, "S5": 2, "S6": 2, "S7": 8, "S8": 8},
            "F10": {"S1": 2, "S2": 4, "S3": 5, "S4": 2, "S5": 5, "S6": 2, "S7": 9, "S8": 3},
            "F11": {"S1": 7, "S2": 2, "S3": 8, "S4": 9, "S5": 5, "S6": 2, "S7": 3, "S8": 6},
            "F12": {"S1": 9, "S2": 5, "S3": 9, "S4": 6, "S5": 5, "S6": 3, "S7": 3, "S8": 4},
        }

    def solve(self):
        # Pattern: PuLP Problem Initialization (Maximize) - slides 16, 17
        # Initialize the linear programming model to maximize total profit over the 10-period planning horizon.
        self._problem = pulp.LpProblem("MaxProfit", pulp.LpMaximize)  
        # .dicts didn't worked so we needed to downgrade our pulp form 4.0 to 3.3.2 
        # Pattern: Compact PuLP: define decision variables (Time-Indexed Allocation) - slides 17, 20, 34
        # Define non-negative integer decision variables X[(f, s, t)] for the amount shipped from facility f to service area s in period t.
        X = pulp.LpVariable.dicts("X", ((f, s, t) for f in self.facilities for s in self.service_areas for t in self.periods), 0, cat = pulp.LpInteger)
        # Pattern: Compact PuLP: define decision variables (Binary 0/1) - slides 18, 20
        # Define binary decision variables Y[f] in {0, 1} indicating whether facility f is opened at all during the planning horizon.
        Y = pulp.LpVariable.dicts("Y", ((f) for f in self.facilities), 0, 1, cat = pulp.LpInteger)
        # Pattern: Compact PuLP: define decision variables + Adding Time Constraints (Start Variable) - slides 18, 20, 34
        # Define binary decision variables Z[(f, c, t)] in {0, 1} indicating whether crew c starts building facility f in period t.
        Z = pulp.LpVariable.dicts("Z", ((f, c, t) for f in self.facilities for c in self.crews for t in self.periods), 0, 1, cat = pulp.LpInteger)
        # Pattern: Compact PuLP: define objective - slides 16, 17, 21
        # Maximize total profit across all periods: total revenue minus total multi-period shipping costs and one-time facility opening costs.
        revenue = pulp.lpSum([X[(f, s, t)] * self.unit_selling_price[s] for f in self.facilities for s in self.service_areas for t in self.periods])
        shipping_cost = pulp.lpSum([X[(f, s, t)] * self.unit_shipping_cost[f][s] for f in self.facilities for s in self.service_areas for t in self.periods])
        opening_cost = pulp.lpSum([Y[f] * self.opening_costs[f] for f in self.facilities])
        self._problem += revenue - shipping_cost - opening_cost, "Total_Profit"
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Horizon Budget) - slides 21, 22, 30
        # Total shipping costs across all periods plus total facility opening costs cannot exceed the overall horizon budget.
        self._problem += shipping_cost + opening_cost <= self.budget, "Budget"
        for f in self.facilities:
            # Pattern: Compact PuLP: define constraints + Adding Time Constraints (Single Start Assignment) - slides 22, 36
            # Each facility f starts construction at most once (by one crew in one start period) if and only if Y[f] == 1.
            self._problem += pulp.lpSum([Z[(f, c, t)] for c in self.crews for t in self.periods]) == Y[f]
            # Pattern: Adding Time Constraints (Completion Before Maximum Horizon Time) - slides 22, 36
            # Ensure that if facility f is built, its construction start period t plus build_time[f] does not exceed the planning horizon length.
            self._problem += pulp.lpSum([Z[(f, c, t)] * (t + self.build_time[f]) for c in self.crews for t in self.periods]) <= len(self.periods), f"Finish_In_Time_{f}"
        # Pattern: Adding Time Constraints (Resource Busy / At Most One Activity at a Time) - slides 22, 34, 35
        # For each crew c and period current_time, at most one facility can be under active construction (started in [current_time - P + 1, current_time]).
        for c in self.crews:
            for curent_time in self.periods:
                self._problem += pulp.lpSum([Z[(f, c, t)] for f in self.facilities for t in self.periods if t <= curent_time < t + self.build_time[f]]) <= 1, f"Crew_Busy_{c}_{curent_time}"
        # Pattern: Adding Linear Constraints + Adding Time Constraints (Operational Capacity After Completion) - slides 22, 30, 34, 35
        # Facility f can only ship up to capacity[f] in period t if its construction started in or before period (t - build_time[f]) and is now completed.
        for f in self.facilities:
            for t in self.periods:
                is_active = pulp.lpSum([Z[(f, c, start_t)] for c in self.crews for start_t in self.periods if start_t <= t - self.build_time[f]]) 
                self._problem += pulp.lpSum([X[(f, s, t)] for s in self.service_areas]) <= self.capacity[f] * is_active, f"Capacity_{f}_{t}"
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Seasonal Period Demand) - slides 22, 30
        # For each service area s and period t, total quantity shipped from all facilities cannot exceed the seasonal demand[s][t].
        for s in self.service_areas:
            for t in self.periods:
                self._problem += pulp.lpSum([X[(f, s, t)] for f in self.facilities]) <= self.demand[s][t], f"Demand_{s}_{t}"      
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Prerequisite Facility Opening) - slides 22, 28
        # For each dependency (f, f2), dependent facility f2 can only be opened if its prerequisite facility f is also opened (Y[f2] <= Y[f]).
        for f, f2 in self.dependencies:
            self._problem += Y[f2] <= Y[f], f"Dependency_{f2}_needs_{f}"
            # Pattern: Adding Task Dependencies (Start Time Sa, Completion Time Ca, and Precedence Ca1 <= Sa2) - slides 22, 40, 41
            # Enforce that the completion period of prerequisite f is at or before the start period of dependent f2 whenever f2 is opened (switched off via 1 - Y[f2] if unopened).
            self._problem += pulp.lpSum([Z[(f, c, t)] * (t + self.build_time[f]) for t in self.periods for c in self.crews]) <= pulp.lpSum([Z[(f2, c, t)] * t for t in self.periods for c in self.crews]) + len(self.periods) * (1 - Y[f2])
        # Pattern: PuLP Solve and Extract Variable Values - slides 16, 17, 18
        # Solve the problem and extract the allocation plan (f, s, t, amount) and construction schedule (f, c, start, end) for opened facilities.
        self._problem.solve()
        solution = [(f, s, t, X[(f, s, t)].varValue) for f in self.facilities for s in self.service_areas for t in self.periods if X[(f, s, t)].varValue is not None and X[(f, s, t)].varValue > 0] 

        schedule = [(f, c, t, t + self.build_time[f]) for f in self.facilities for c in self.crews for t in self.periods if Z[(f, c, t)].varValue is not None and Z[(f, c, t)].varValue > 0]

        self.status = pulp.LpStatus[self._problem.status]
        self.total_revenue = pulp.value(revenue)
        self.total_opening_cost = pulp.value(opening_cost)
        self.total_shipping_cost = pulp.value(shipping_cost)
        self.total_profit = self.total_revenue - self.total_opening_cost - self.total_shipping_cost
        self.budget_used = self.total_opening_cost + self.total_shipping_cost
        self.facilities_opened = [f for f in self.facilities if Y[f].varValue == 1]

        self.demand_met = {s: sum(X[(f, s, t)].varValue for f in self.facilities for t in self.periods if X[(f, s, t)].varValue is not None) for s in self.service_areas}
    
        self.demand_unmet = {s: sum(self.demand[s].values()) - self.demand_met[s] for s in self.service_areas}

        self.construction_start = {}
        self.construction_crew = {}
        for f in self.facilities_opened:
            for c in self.crews:
                for t in self.periods:
                    if Z[(f, c, t)].varValue is not None and Z[(f, c, t)].varValue > 0.5:
                        self.construction_start[f] = t
                        self.construction_crew[f] = c

        self.crew_usage = {}
        for c in self.crews:
            for current_time in self.periods:
                self.crew_usage[(c, current_time)] = int(sum(1 for f in self.facilities for t in self.periods if t <= current_time < t + self.build_time[f] and Z[(f, c, t)].varValue is not None and Z[(f, c, t)].varValue > 0))
                
        return solution ,   schedule


##########################
##### SOLUTION CHECK #####
##########################

print(
    "\n\nDISCLAIMER\nNote that if you pass the solution check that does not mean that you will get full points. "
    + "We will test more and different things. Also note that you should see DONE at the end of the tests. "
    + "If you do not see DONE, this means that the program got stuck somewhere and consequently does not work properly. "
    + "Finally, note that you must use all attributes and functions that are defined in the template and give them correct values according to the assignment description. "
    + "You must not change names or signatures of predefined classes, attributes or functions. Doing so may lead to severe deduction of points. "
    + "\n\nSOLUTION CHECK\n"
    + "All of the following should be True:"
)

problem = DistributionNetwork()
solution, schedule = problem.solve()
print("- Solver status:", problem.status)
print("- An optimal solution was found:", problem._problem.status == 1)
print(f"- The total profit found is: {problem.total_profit}.")
print(
    f"*  revenue {problem.total_revenue}"
    f" - opening {problem.total_opening_cost}"
    f" - shipping {problem.total_shipping_cost}"
)
print("- The solution contains an assignment:", len(solution) > 0)
print(f"- Budget used: {problem.budget_used} / {problem.budget}")
print(
    "- The allocation plan is a list of 4-tuples:",
    (
        type(solution) == list
        and all([type(sol) == tuple and len(sol) == 4 for sol in solution])
        if len(solution) > 0
        else False
    ),
)
print(
    "- The construction schedule is a list of 4-tuples:",
    (
        type(schedule) == list
        and all([type(sch) == tuple and len(sch) == 4 for sch in schedule])
        if len(schedule) > 0
        else False
    ),
)
print("- Construction schedule:")
for f, crew, start, end in sorted(schedule, key=lambda x: (x[2], x[0])):
    print(f"*  {f}: built by {crew}, starts in period {start}, completed in period {end}")
print("- Facilities not opened:", [
    f for f in problem.facilities if f not in problem.facilities_opened
])

print("- Dependencies:")
for first, second in problem.dependencies:
    if second in problem.facilities_opened:
        done = problem.construction_start[first] + problem.build_time[first]
        begins = problem.construction_start[second]
        print(f"*  {first} completed in period {done}, {second} starts in period "
              f"{begins}: {'OK' if done <= begins else 'VIOLATED'}")
    elif first in problem.facilities_opened:
        print(f"*  {first} opened, {second} not opened: OK")
    else:
        print(f"*  neither {first} nor {second} opened: OK")

print("- Crew occupancy per period (each crew builds at most one facility at a time):")
for k in problem.crews:
    timeline = "".join(
        "1" if any(
            problem.construction_crew[f] == k
            and problem.construction_start[f] <= t
            <= problem.construction_start[f] + problem.build_time[f] - 1
            for f in problem.facilities_opened
        ) else "0"
        for t in problem.periods
    )
    print(f"*  {k}: {timeline}")

print(f"- Total demand met: {sum(problem.demand_met.values())} / "
      f"{sum(sum(problem.demand[s].values()) for s in problem.service_areas)}")

print("- Demand fulfillment over the planning horizon:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = sum(problem.demand[s].values())
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("DONE\n")
