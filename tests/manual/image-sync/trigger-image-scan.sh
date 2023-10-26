curl --header "Content-Type: application/json" \
  --header "aeg-event-type: Notification" \
  --request POST \
  --data @image-scan-payload.json \
  -v \
  "http://localhost:7071/runtime/webhooks/eventgrid?functionName=VulnScanFunction"
