import logging
import azure.functions as func
import json
import os
# from azure.identity import AzureCliCredential
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerregistry.models import OverrideTaskStepProperties, TaskRunRequest, SetValue
from azure.eventgrid import EventGridPublisherClient, EventGridEvent

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def ImagePushDispatchFunction(event: func.EventGridEvent):
    logging.info('Python EventGrid trigger processed an event')

    # Acquire a credential object using CLI-based authentication.
    credential = DefaultAzureCredential()

    result = event.get_json()
    logging.info(f"Event data: {result} \n Result type: {type(result)}")

    # Handle only events with `docker` in the user agent
    if result['request']['useragent'].find('docker') != -1:
        registry = result['request']['host']
        repository = result['target']['repository']
        tag = result['target']['tag']
        digest = result['target']['digest']

        logging.info(f"Triggering events for: {registry}/{repository}:{tag} with digest {digest}")
        # TODO: Trigger SBOM generation task
        publish_eventgrid_event("SBOMGeneration", f"{registry}/{repository}", create_event(registry, repository, tag, digest))
        # TODO: Trigger vulnerability scan and patch task
        # TODO: Trigger lifecycle generation task
        # TODO: Trigger provenance generation task - note, this may be something that we cannot do at this point of the workflow
        return

def publish_eventgrid_event(event_type, subject, data):
    # Connect to EventGrid for publishing events for image sync
    eg_topic_endpoint = os.environ["EG_SYNC_TOPIC_ENDPOINT"]
    eg_topic_key = os.environ["EG_SYNC_TOPIC_KEY"]
    eg_credentials = AzureKeyCredential(eg_topic_key)

    eg_client = EventGridPublisherClient(eg_topic_endpoint, credential=eg_credentials)
    eg_client.send(
        events=[
            EventGridEvent(
                event_type=event_type,
                subject=subject,
                data=data,
                data_version="1.0"
            )
        ]
    )

def create_event(registry, repository, tag, digest):
    event = {
        "registry": registry,
        "repository": repository,
        "tag": tag,
        "digest": digest
    }
    return event