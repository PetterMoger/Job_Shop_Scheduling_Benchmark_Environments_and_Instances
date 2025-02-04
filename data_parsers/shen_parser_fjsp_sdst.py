from pathlib import Path

from scheduling_environment.job import Job
from scheduling_environment.machine import Machine
from scheduling_environment.operation import Operation
from scheduling_environment.jobShop import JobShop


def shen_parse_fjsp_sdst(JobShop, instance, from_absolute_path=False):
    # instance = 'petter_test'
    # JobShop.set_instance_name(instance)
    # if not from_absolute_path:
    #     base_path = Path(__file__).parent.parent.absolute()
    #     data_path = base_path.joinpath('data' + instance)
    # else:
    #     data_path = instance

    JobShop.set_instance_name('petter_test')
    
    data_path = instance

    with open(data_path, "r") as data:
        lines = data.readlines()
        
        # read the number of jobs and machines
        number_total_jobs = int(lines[0].strip())
        number_total_machines = int(lines[1].strip())
        
        JobShop.set_nr_of_jobs(number_total_jobs)
        JobShop.set_nr_of_machines(number_total_machines)
        
        # parse number of operations per job
        operation_counts = list(map(int, lines[2].strip().split()))
        assert len(operation_counts) == number_total_jobs, "Mismatch in job count and operation count."

        precedence_relations = {}
        operation_id = 0
        current_line = 4 # start after reading job/machine counts and operation counts

        for job_id in range(number_total_jobs):
            i = 1
            job = Job(job_id)
        
            for num_operations in range(operation_counts[job_id]):
                operation_options = int(lines[current_line])
                operation = Operation(job, job_id, operation_id)
                
                for operation_options_id in range(operation_options):
                    line_data = lines[current_line + 1].split()
                    operation.add_operation_option(int(line_data[0 + 2 * operation_options_id]),
                                                   int(line_data[1 + 2 * operation_options_id]))
                
                job.add_operation(operation)
                JobShop.add_operation(operation)
                if i != 1:
                    precedence_relations[operation_id] = [
                        JobShop.get_operation(operation_id - 1)
                    ]
                
                i += 1 + 2 * operation_options

                operation_id += 1
                current_line += 2
            
            current_line += 1
            jobShop.add_job(job)
            job_id += 1

        # Parse SDST (Sequence-dependent setup times)
        current_line += 1 # Skip empty line

        # counter_machine_id = 0
        counter_operation_id = 0
        
        sequence_dependent_setup_times = [[[-1 for r in range(len(JobShop.operations))] for t in range (
            len(JobShop.operations))] for m in range(number_total_machines)]
        
        for job in range(len(JobShop.jobs)):
            for op in range(len(JobShop.jobs[job].operations)):
                for machine in range(len(JobShop.machines)):
                    sequence_dependent_setup_times[machine][counter_operation_id] = list(
                        map(int, lines[current_line].split()[3*job+machine:])
                    )
                counter_operation_id += 1
            # counter_machine_id = 0
        
    # add also the operations without precedence operations to the precendence relations dictionary
    for operation in JobShop.operations:
        if operation.operation_id not in precedence_relations.keys():
            precedence_relations[operation.operation_id] = []
        operation.add_predecessors(
            precedence_relations[operation.operation_id])
        
        # Precedence Relations
    JobShop.add_precedence_relations_operations(precedence_relations)
    JobShop.add_sequence_dependent_setup_times(sequence_dependent_setup_times)
    
    # Machines
    for id_machine in range(0, number_total_machines):
        JobShop.add_machine((Machine(id_machine)))
    
    return JobShop

file = 'Shen instances/test_a/short_data'
jobShop = JobShop()
jobShop = shen_parse_fjsp_sdst(jobShop, file, from_absolute_path=True)

print(jobShop.jobs)
print(jobShop.operations)
print(jobShop.machines)
print(jobShop)
print(jobShop._sequence_dependent_setup_times)