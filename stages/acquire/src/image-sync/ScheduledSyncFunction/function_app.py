import json
import logging
import os
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

app = func.FunctionApp()

@app.schedule(schedule="0 1 * * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def ScheduledImageSyncFunction(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')

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
    json_data = json.loads(blob_contents)

    # Do something with the JSON data
    logging.info(json_data)


