import logging
import azure.functions as func
import json

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def ImageSyncFunction(event: func.EventGridEvent):

     result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })
     
    logging.info('Python EventGrid trigger processed an event')
