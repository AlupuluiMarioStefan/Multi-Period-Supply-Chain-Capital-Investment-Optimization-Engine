import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = ["F1", "F2", "F3", "F4", "F5"]
        self.service_areas = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

        self.capacity = {
            "F1": 1000,
            "F2": 300,
            "F3": 900,
            "F4": 1500,
            "F5": 250
        }

        self.opening_costs = {
            "F1": 500,
            "F2": 100,
            "F3": 500,
            "F4": 650,
            "F5": 200
        }

        self.demand = {
            "S1": 250,
            "S2": 400,
            "S3": 300,
            "S4": 200,
            "S5": 700,
            "S6": 400,
            "S7": 300,
            "S8": 500,
        }

        self.unit_selling_price = {
            "S1": 15,
            "S2": 10,
            "S3": 12,
            "S4": 11,
            "S5": 8,
            "S6": 15,
            "S7": 18,
            "S8": 17,
        }

        self.unit_shipping_cost = {
            "F1": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F2": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F3": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F4": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F5": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
        }

        self.budget = 10000


    def solve(self):
        # Pattern: PuLP Problem Initialization (Maximize) - slides 16, 17
        # Initialize the linear programming model to maximize total profit.
        self._problem = pulp.LpProblem("MaxProfit", pulp.LpMaximize)  
        # .dicts didn't worked so we needed to downgrade our pulp form 4.0 to 3.3.2 
        # Pattern: Compact PuLP: define decision variables - slides 17, 20
        # Define non-negative integer decision variables X[(f, s)] for the quantity shipped from facility f to service area s.
        X = pulp.LpVariable.dicts("X", ((f,s) for f in self.facilities for s in self.service_areas), 0, cat = pulp.LpInteger)
        # Pattern: Compact PuLP: define decision variables (Binary 0/1) - slides 18, 20
        # Define binary decision variables Y[f] in {0, 1} indicating whether facility f is opened (1) or not (0).
        Y = pulp.LpVariable.dicts("Y", ((f) for f in self.facilities), 0, 1, cat = pulp.LpInteger)
        # Pattern: Compact PuLP: define objective - slides 16, 17, 21
        # Maximize total profit: total selling revenue from fulfilled demand minus total shipping costs and fixed facility opening costs.
        revenue = pulp.lpSum([X[(f,s)] * self.unit_selling_price[s] for f in self.facilities for s in self.service_areas])
        shipping_cost = pulp.lpSum([X[(f,s)] * self.unit_shipping_cost[f][s] for f in self.facilities for s in self.service_areas])
        opening_cost = pulp.lpSum([Y[f] * self.opening_costs[f] for f in self.facilities])
        self._problem += revenue - shipping_cost - opening_cost, "Total_Profit"
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Resource Capacity) - slides 22, 30
        # For each facility f, total demand shipped across all service areas cannot exceed its capacity if opened (capacity[f] * Y[f]).
        for f in self.facilities:
            self._problem += pulp.lpSum([X[(f,s)] for s in self.service_areas]) <= self.capacity[f] * Y[f], f"Capacity_{f}"
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Maximum Demand) - slides 22, 30
        # For each service area s, total quantity shipped from all facilities cannot exceed the demand of service area s.
        for s in self.service_areas:
            self._problem += pulp.lpSum([X[(f,s)] for f in self.facilities]) <= self.demand[s], f"Demand_{s}"
        # Pattern: Compact PuLP: define constraints + Adding Linear Constraints (Budget Limit) - slides 21, 22, 30
        # Total shipping costs plus total fixed facility opening costs must stay within the company budget.
        self._problem += shipping_cost + opening_cost <= self.budget, "Budget"
        # Pattern: PuLP Solve and Extract Variable Values - slides 16, 17, 18
        # Solve the optimization problem and collect (facility, service_area, allocated_amount) tuples with positive allocation (> 0).
        self._problem.solve()

        solution = [(f, s, X[(f,s)].varValue) for f in self.facilities for s in self.service_areas if X[(f,s)].varValue is not None and X[(f,s)].varValue > 0] 

        
        self.status = pulp.LpStatus[self._problem.status]
        self.total_revenue = pulp.value(revenue)
        self.total_opening_cost = pulp.value(opening_cost)
        self.total_shipping_cost = pulp.value(shipping_cost)
        self.total_profit = self.total_revenue - self.total_opening_cost - self.total_shipping_cost
        self.budget_used = self.total_opening_cost + self.total_shipping_cost
        self.facilities_opened = [f for f in self.facilities if Y[f].varValue == 1]
        
        self.demand_met = {s: sum(X[(f,s)].varValue for f in self.facilities if X[(f,s)].varValue is not None) for s in self.service_areas}
        self.demand_unmet = {s: self.demand[s] - self.demand_met[s] for s in self.service_areas}

        return solution


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
solution = problem.solve()
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
    "- The solution is a list of 3-tuples:",
    (
        type(solution) == list
        and all([type(sol) == tuple and len(sol) == 3 for sol in solution])
        if len(solution) > 0
        else False
    ),
)
print("- Allocation plan:")
print(solution)

print("- Facilities opened:", problem.facilities_opened)

print(f"- Total demand met: {sum(problem.demand_met.values())} / {sum(problem.demand.values())}")

print("- Demand fulfillment:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = problem.demand[s]
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("DONE\n")


