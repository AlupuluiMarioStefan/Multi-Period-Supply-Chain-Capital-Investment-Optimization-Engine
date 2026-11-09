import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = ["F1", "F2", "F3", "F4", "F5"]
        self.service_areas = ["S1", "S2", "S3", "S4", "S5", "S6"]
        self.periods = [t for t in range(0, 10, 1)]
        self.crews = ["K1", "K2"]
        self.budget = 7500

        # capacity that a facility can ship in a single period
        self.capacity = {
            "F1": 120,
            "F2": 60,
            "F3": 150,
            "F4": 90,
            "F5": 50,
        }

        self.opening_costs = {
            "F1": 400,
            "F2": 150,
            "F3": 600,
            "F4": 300,
            "F5": 120,
        }

        # number of periods it takes to construct a facility
        self.build_time = {
            "F1": 3,
            "F2": 1,
            "F3": 4,
            "F4": 2,
            "F5": 1,
        }

        # demand of a service area in a single period
        self.demand = {
            "S1": 60,
            "S2": 80,
            "S3": 50,
            "S4": 70,
            "S5": 90,
            "S6": 40,
        }

        self.unit_selling_price = {
            "S1": 15,
            "S2": 10,
            "S3": 12,
            "S4": 18,
            "S5": 8,
            "S6": 20,
        }

        self.unit_shipping_cost = {
            "F1": {"S1": 3, "S2": 4, "S3": 2, "S4": 7, "S5": 5, "S6": 9},
            "F2": {"S1": 6, "S2": 3, "S3": 5, "S4": 4, "S5": 7, "S6": 6},
            "F3": {"S1": 8, "S2": 6, "S3": 7, "S4": 5, "S5": 3, "S6": 4},
            "F4": {"S1": 2, "S2": 7, "S3": 4, "S4": 9, "S5": 6, "S6": 8},
            "F5": {"S1": 7, "S2": 5, "S3": 6, "S4": 3, "S5": 8, "S6": 5},
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
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Period Demand Limit) - slides 22, 30
        # In each period t, total quantity shipped from all facilities to service area s cannot exceed its per-period demand[s].
        for s in self.service_areas:
            for t in self.periods:
                self._problem += pulp.lpSum([X[(f, s, t)] for f in self.facilities]) <= self.demand[s], f"Demand_{s}_{t}"      
        # Pattern: PuLP Solve and Extract Variable Values - slides 16, 17, 18
        # Solve the problem and build the positive allocation plan tuples (f, s, t, amount) and opened construction schedule tuples (f, c, start, end).
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
    
        self.demand_unmet = {s: (self.demand[s] * len(self.periods)) - self.demand_met[s] for s in self.service_areas}

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
for f, crew, start, end in schedule:
    print(f"*  {f}: built by {crew}, starts in period {start}, completed in period {end}")
print("- Facilities not opened:", [
    f for f in problem.facilities if f not in problem.facilities_opened
])

print("- Crew occupancy per period (each crew builds at most one facility at a time):")
for k in problem.crews:
    timeline = "".join(
        str(problem.crew_usage[(k, t)]) for t in problem.periods
    )
    busy = max(problem.crew_usage[(k, t)] for t in problem.periods)
    print(f"*  {k}: {timeline}  (max {busy} of 1)")

print(f"- Total demand met: {sum(problem.demand_met.values())} / "
    f"{sum(problem.demand.values()) * len(problem.periods)}")

print("- Demand fulfillment over the planning horizon:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = problem.demand[s] * len(problem.periods)
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("- Allocation plan:")
print(solution)

print("DONE\n")
