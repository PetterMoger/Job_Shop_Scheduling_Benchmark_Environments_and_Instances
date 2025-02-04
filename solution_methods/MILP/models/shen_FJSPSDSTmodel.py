# Code based on the paper:
# "Solving the flexible job shop scheduling problem with sequence-dependent setup times"
# by Liji Shen, Stéphane Dauzère-Pérès, Janis S. Neufeld
# Presented in European Journal of Operational Research, 2018.
# Paper URL: https://www.sciencedirect.com/science/article/pii/S037722171730752X
import re
import pyomo.environ as pyo
# solver.options['LogFile'] = 'gurobi.log'

def update_env(jobShopEnv, results):
    schedule = {machine: {} for machine in jobShopEnv.machines}
    for var, value in results['variables'].items():
        if 'Y_' in var and value == 1.0:
            numbers = [int(number) for number in re.findall(r'\d+', var)]
            operation = jobShopEnv.get_operation(numbers[1])
            machine = jobShopEnv.get_machine(numbers[2])
            start_time = results['variables']['S_' + str(numbers[0]) + '_' + str(numbers[1])]
            schedule[machine][operation] = start_time

    for machine, operations in schedule.items():
        sorted_operations = sorted(operations, key=lambda k: operations[k])
        for value, operation in enumerate(sorted_operations):
            start_time = operations[operation]
            processing_time = operation.processing_times[machine.machine_id]
            if value == 0:
                setup_time = 0
            else:
                # Need to rework this setup_time
                setup_time = jobShopEnv._sequence_dependent_setup_times[machine.machine_id][sorted_operations[value-1].operation_id][operation.operation_id]
            machine.add_operation_to_schedule_at_time(operation, start_time, processing_time, setup_time)
    return jobShopEnv

def shen_fjsp_sdst_milp(jobShopEnv, time_limit = 10):
    # Extracting the instance info from the environment
    jobs = [job.job_id for job in jobShopEnv.jobs]
    machines = [machine.machine_id for machine in jobShopEnv.machines]
    operations_per_job = {
        job.job_id: [operation.operation_id for operation in job.operations]
        for job in jobShopEnv.jobs
    }
    machine_allocations = {
        (operation.job_id, operation.operation_id): operation.optional_machines_id
        for operation in jobShopEnv.operations
    }
    operations_times = {
        (
            operation.job_id,
            operation.operation_id,
            operation.optional_machines_id[i],
        ): operation.processing_times[operation.optional_machines_id[i]]
        for operation in jobShopEnv.operations
        for i in range(len(operation.optional_machines_id))
    }    
    sdst = {
        jobShopEnv.sequence_dependent_setup_times
    }
    
    solver = pyo.SolverFactory('gurobi')
    solver.options['TimeLimit'] = time_limit
    solver = pyo.SolverFactory('gurobi')
    model = pyo.ConcreteModel()
    
    largeM = 10000
    model = model("Shen_FJSP_SDST_MILP")

    # Sets
    model.jobs = pyo.Set(initialize=jobs)  # Set of jobs
    model.machines = pyo.Set(initialize=machines)  # Set of machines
    model.operations = pyo.Set(initialize=[
        (job, op) for job in jobs for op in range(1, operations_per_job[job] + 1)
    ])  # Set of operations (job, operation_id)

    
    # Decision Variables
    # ALPHA: αijk: 1 if Oij is assigned to machine k, 0 otherwise
    model.alpha = pyo.Var(
        model.operations * model.machines,
        domain=pyo.Binary,
        doc="1 if operation(i,j) is assigned to machine k, 0 otherwise"
    )

    # BETA: βiji'j': 1 if Oij is scheduled before Oi'j', 0 otherwise
    model.beta = pyo.Var(
        model.operations * model.operations,
        domain=pyo.Binary,
        doc="1 if operation(i,j) is scheduled before operation(i',j'), 0 otherwise"
    )

    # START TIME: Sij for start time of operation Oij
    model.start_time = pyo.Var(
        model.operations,
        domain=pyo.NonNegativeReals,
        doc="Start time of operation(i,j)"
    )
    
    # Objective Function: Minimize Cmax
    model.Cmax = pyo.Var(within=pyo.NonNegativeReals) 
    model.obj = pyo.Objective(expr=model.Cmax, sense=pyo.minimize) #(2)

    # Constraint (3): Each operation is assigned to one and only one eligible machine
    def assignment_rule(model, i, j):
        return sum(model.alpha[i, j, k] for k in machine_allocations[(i, j)]) == 1
    model.assignment_constraint = pyo.Constraint(model.operations, rule=assignment_rule)

    # Constraint (4): Precedence relations between consecutive operations of the same job
    def precedence_rule(model, i, j, i_prime, j_prime):
        if j >= 1: # The first operation of the job have no precedence constraint
            return model.start_time[i,j] >= model.start_time[i,j-1] + sum(
                operations_times[(i, j-1, k)] * model.alpha[i, j-1, k] for k in machine_allocations[(i, j-1)])
        # else:
        #     return model.start_time[i,j] >= sum(
        #         sdst[(i,0,k)] * model.alpha[i,j,k] for k in machine_allocations[(i,j)]
        #     ) - (model.beta[i_prime, j_prime, i, j] * BigM) # if any other operation is preceeding -> disregard
        else:
            return pyo.Constraint.Skip
    model.precedence_constraint = pyo.Constraint(model.operations, model.operations, rule=precedence_rule)

    # Constraint (5) & (6): No overlapping of operations on the same machine k
    def non_overlap_rule1(model, i, j, i_prime, j_prime, k): #(5)
        common_machines = set(machine_allocations[(i,j)]).intersection(
            set(machine_allocations[(i_prime, j_prime)])
        )
        
        if not (i == i_prime and j == j_prime) and k in common_machines:
            return model.start_time[i,j] >= (
                model.start_time[i_prime,j_prime] 
                + operations_times[i_prime, j_prime, k]
                + sdst[(i_prime, i, k)]
                - (2 - model.alpha[i, j, k]
                    - model.alpha[i_prime, j_prime, k]
                    + model.beta[i,j,i_prime,j_prime]
                ) * largeM
            )
        else:
            return pyo.Constraint.Skip
    model.non_overlap_constraint1 = pyo.Constraint(model.operations, model.operations, model.machines, rule=non_overlap_rule1)

    def non_overlap_rule2(model, i, j, i_prime, j_prime, k): #(6)
        common_machines = set(machine_allocations[(i,j)]).intersection(
            set(machine_allocations[(i_prime, j_prime)])
        )
        
        if not (i == i_prime and j == j_prime) and k in common_machines:
            return model.start_time[i_prime, j_prime] >= (
                model.start_time[i, j]
                + operations_times[(i, j, k)]
                + sdst[(i, i_prime, k)]
                - (3 - model.alpha[i, j, k]
                - model.alpha[i_prime, j_prime, k]
                - model.beta[i, j, i_prime, j_prime]
                ) * largeM
            )
        else:
            return pyo.Constraint.Skip
    model.non_overlap_constraint2 = pyo.Constraint(model.operations, model.operations, model.machines, rule=non_overlap_rule2)

    # Constraint (7): Determine makespan
    def makespan_rule(model, i):
        last_op = operations_per_job[i]
        return model.Cmax >= model.start_time[i, last_op] + sum(
            operations_times[(i, last_op, k)] * model.alpha[i, last_op, k] for k in machine_allocations[(i, last_op)]
            )
    model.makespan_constraint = pyo.Constraint(model.jobs, rule=makespan_rule)

    model.params.TimeLimit = time_limit

    return model
