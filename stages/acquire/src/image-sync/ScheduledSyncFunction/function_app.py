import azure.functions as func
import json
import logging
import os
import requests
from azure.core.credentials import AzureKeyCredential
from azure.eventgrid import EventGridPublisherClient
from azure.eventgrid import EventGridEvent
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

app = func.FunctionApp()

@app.schedule(schedule="0 1 * * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def ScheduledImageSyncFunction(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python ScheduledImageSyncFunction function started.')

    # Connect to the storage account
    config_storage_conn_string = os.environ["CONFIG_STORAGE_CONN_STRING"]
    blob_service_client = BlobServiceClient.from_connection_string(config_storage_conn_string)

    # Get a reference to the blob
    container_name = os.environ["CONFIG_STORAGE_CONTAINER_NAME"]
    blob_name = "image-sync/sync-config.json"
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Download the blob contents as a string
    blob_contents = blob_client.download_blob().content_as_text()

    # Parse the JSON string into a Python object
    configs = json.loads(blob_contents)

    for config in configs:
        # Get the current tags for the image
        tags = get_current_tags(config["registry"], config["repository"])

        for sync_tag in config["tags"]:
            tag = [t for t in tags if t[0] == sync_tag['name']][0]
            if tag:
                digest = tag[1]
                logging.info(f"Digest for tag {sync_tag['name']}: {digest}")
                if digest not in sync_tag['digests']:
                    sync_tag['digests'].append(digest)
                    # TODO: Maybe convert the tag to JSON
                    publish_eventgrid_event("ImageSync", f"{config['registry']}/{config['repository']}", create_event(config["registry"], config["repository"], tag))
            else:
                logging.info(f"Tag {sync_tag['name']} not found.")

    blob_contents = json.dumps(configs)
    blob_client.upload_blob(blob_contents, overwrite=True)

# Compare the image tag and digest to decide if to sync
def get_current_tags(registry, repository):
    # Define the URL for the tag list API
    url = f"https://{registry}/v2/repositories/{repository}/tags"

    # Send a GET request to the registry to retrieve the tags
    response = requests.get(url)
    tags = response.json()["results"]

    # Extract the tag names and digests from the response
    tag_names = [[tag["name"],tag["digest"]] for tag in tags]

    return tag_names

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

def create_event(registry, repository, tag):
    event = {
        "registry": registry,
        "repository": repository,
        "name": tag[0],
        "digest": tag[1]
    }
    return json.dumps(event)