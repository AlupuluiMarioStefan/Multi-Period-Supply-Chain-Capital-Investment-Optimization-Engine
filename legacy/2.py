import pulp
import pandas as pd


class DistributionNetwork:
    def __init__(self):
        self.facilities = list()
        self.service_areas = list()
        self.capacity = dict()
        self.opening_costs = dict()
        self.demand = dict()
        self.unit_selling_price = dict()
        self.unit_shipping_cost = dict()
        self.budget = int()

    def load(self, facility_file, service_area_file, budget_file):
        # Read the budget text file skipping the header line and convert the single budget value to an integer.
        budget = pd.read_csv(budget_file, header = 0)
        self.budget = int(budget.iloc[0,0])
        # Pattern: Loading Semicolon-Separated Data and Dictionary Column - Module 6-1 slides 6, 7, 8, 9; Module 6-4 slide 2
        # Read facility IDs, integer capacities, integer opening costs, and evaluate the shipping cost dictionary for each facility.
        fcocsc = pd.read_csv(facility_file, header = 0, sep = ';',names = ['facility', 'capacity', 'opening_cost', 'shipping_costs'])
        self.facilities = fcocsc.facility.to_list()
        self.capacity = fcocsc.set_index('facility')['capacity'].to_dict()
        self.opening_costs = fcocsc.set_index('facility')['opening_cost'].to_dict()
        fcocsc['shipping_costs'] = fcocsc['shipping_costs'].apply(eval)
        self.unit_shipping_cost = fcocsc.set_index('facility')['shipping_costs'].to_dict()
        # Pattern: Loading Semicolon-Separated Data into Lists and Dictionaries - Module 6-1 slides 6, 7, 8, 9;
        # Read service area IDs, integer demands, and integer unit selling prices into the instance attributes.
        sdus = pd.read_csv(service_area_file, header = 0, sep = ';',names = ['service_area', 'demand', 'unit_selling_price'])
        self.service_areas = sdus.service_area.to_list()
        self.demand = sdus.set_index('service_area')['demand'].to_dict()
        self.unit_selling_price = sdus.set_index('service_area')['unit_selling_price'].to_dict()
        


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
problem.load("2_1_facilities.txt", "2_1_service_areas.txt", "2_1_budget.txt")
# problem.load(
#     "2_2_facilities.txt", "2_2_service_areas.txt", "2_2_budget.txt"
# )  # You can uncomment this line to evaluate another problem instance

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
print(
    "- All variables are loaded:",
    (
        len(problem.facilities) > 0
        and len(problem.service_areas) > 0
        and len(problem.capacity) > 0
        and len(problem.opening_costs) > 0
        and len(problem.demand) > 0
        and len(problem.unit_selling_price) > 0
        and len(problem.unit_shipping_cost) > 0
        and problem.budget > 0
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
