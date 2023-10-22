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
def VulnScanFunction(event: func.EventGridEvent):
    logging.info('Python EventGrid trigger processed an event')

    # Get the configuration
    acr_name = os.environ['ACRName']
    acr_task_name = os.environ['ACRTaskName']
    subscription_id = os.environ['SubscriptionId']
    resource_group_name = os.environ['ResourceGroupName']

    # Acquire a credential object using CLI-based authentication.
    credential = DefaultAzureCredential()

    result = event.get_json()
    logging.info(f"Event type: {type(event)}")
    result = json.loads(result)
    logging.info(f"Event data: {result} \n Result type: {type(result)}")

