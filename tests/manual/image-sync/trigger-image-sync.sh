curl --header "Content-Type: application/json" \
  --header "aeg-event-type: Notification" \
  --request POST \
  --data @image-sync-payload.json \
  -v \
  "http://localhost:7071/runtime/webhooks/eventgrid?functionName=ImageSyncFunction"
