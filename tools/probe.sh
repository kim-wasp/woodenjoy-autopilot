#!/bin/bash
A="gracelyun28:$WP_FORSMARTLIFE_PASS"
curl -s -u "$A" -X POST -H "Content-Type: application/json" -d '{"module":"redirections","state":"on"}' https://forsmartlife.com/wp-json/rankmath/v1/saveModule; echo
python3 tools/fsl_merge.py redirect-test
