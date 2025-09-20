from strands import Agent
from strands_tools import workflow
from llms import * 
from strands import Agent, tool
from prompts import *
from toolkit import * 

# Create an agent with workflow capability
#wf_agent = Agent(tools=[workflow])

data_modeler_agent = Agent(
    model=sonnet37_model,
    system_prompt=DATA_MODELER_PROMPT,
    #callback_handler=None, 
    tools=[extract_csv_schemas, pipe_delimited_string_to_csv],
    name="data_modeler"
)

data_engineer_agent = Agent(
    model=opus4_model,
    system_prompt=DATA_ENGINEER_PROMPT,
    tools=[save_generated_code],
    name="data_engineer"
)

code_runner_agent = Agent(
    model=nova_pro_model,
    system_prompt=CODE_RUNNER_PROMPT,
    tools=[check_and_execute_python_file],
    name="code_runner"
)

def run_data_workflow(user_input):
    # Step 1: Create data models
    modeling_response = data_modeler_agent(
        f"Generate data model based on the business requirement: '{user_input}' ",
    )
    data_models = str(modeling_response)

    # Step 2: Write data engineering code based on the data models
    engineer_response = data_engineer_agent(
        f"Generate code based on the business requirements:'{user_input}' and  and data model:\n\n{data_models}",
    )
    code = str(engineer_response)
    
    return code