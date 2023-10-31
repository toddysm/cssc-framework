cat ./temp/vulnerability-report_27000-10-10.sarif | jq -r 'select(any(.runs.[0].tool.driver.rules.[]; .properties["security-severity"]))'
cat ./temp/vulnerability-report_27000-10-10.sarif | jq -r '.runs.[0].tool.driver.rules.[].properties["security-severity"]' 

jq -r '.runs.[0].tool.driver.rules.[].properties["security-severity"]' \
    ./temp/vulnerability-report_27000-10-10.sarif

jq -r '.runs.[0].tool.driver.rules.[]
    | {id: .id, severity: .properties["security-severity"]}' \
    ./temp/vulnerability-report_27000-10-10.sarif

jq -r '[.runs.[0].results.[] | {cve: .ruleId}] | group_by(.cve)' \
    ./temp/vulnerability-report_27000-10-10.sarif


jq -r '[.runs.[0].results.[] | {cve: .ruleId}] | flatten | group_by(.cve) | map({cve: .[0].cve, count: length})' \
    ./temp/vulnerability-report_27000-10-10.sarif

jq -r '[.runs.[0].results.[] | {cve: .ruleId}] | flatten | group_by(.cve) | map({cve: .[0].cve, count: length})' \
    ./temp/vulnerability-report_27000-10-10.sarif

.runs.[0].tool.driver.rules.[] | {cve: .id, severity: .properties["security-severity"]}, 