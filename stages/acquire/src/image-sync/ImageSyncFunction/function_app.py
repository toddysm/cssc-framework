import logging
import azure.functions as func
import json
import os
# from azure.identity import AzureCliCredential
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerregistry.models import OverrideTaskStepProperties, TaskRunRequest, SetValue

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def ImageSyncFunction(event: func.EventGridEvent):
    logging.info('Python EventGrid trigger processed an event')

    # Get the configuration
    acr_name = os.environ['ACRName']
    acr_task_name = os.environ['ACRTaskName']
    subscription_id = os.environ['SubscriptionId']
    resource_group_name = os.environ['ResourceGroupName']

    # Acquire a credential object using CLI-based authentication.
    credential = DefaultAzureCredential()

    # Obtain the management object for resources and the resources
    # arm_client = ResourceManagementClient(credential, subscription_id)
    # acr_task_resource = arm_client.resources.get_by_id(f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.ContainerRegistry/registries/{acr_name}/tasks/{acr_task_name}", 
    #                                                    "2019-06-01-preview")
    
    result = event.get_json()
    logging.info(f"Event type: {type(event)}")
    result = json.loads(result)
    logging.info(f"Event data: {result} \n Result type: {type(result)}")

    # Create a task run request object
    task_values = [
        SetValue(name='SOURCE_REGISTRY', value=result['registry']),
        SetValue(name='SOURCE_REPOSITORY', value=result['repository']),
        SetValue(name='SOURCE_IMAGE_TAG', value=result['tag']),
        SetValue(name='SOURCE_IMAGE_DIGEST', value=result['digest'])
    ]
    task_properties = OverrideTaskStepProperties(values=task_values)
    acr_client = ContainerRegistryManagementClient(credential, subscription_id, api_version="2019-06-01-preview")
    task = acr_client.tasks.get(resource_group_name, acr_name, acr_task_name)

    # acr_client.task_runs..begin_create(resource_group_name, acr_name, acr_task_name, task_properties)
    acr_client.registries.begin_schedule_run(
        resource_group_name, 
        acr_name, 
        TaskRunRequest(
            task_id=task.id,
            override_task_step_properties=task_properties,
        ))

    logging.info('Python EventGrid trigger event processing completed')
