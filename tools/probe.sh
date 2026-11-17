#!/bin/bash
python3 tools/fsl_merge.py redirect-test
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://forsmartlife.com/fine-dust-cleansing-routine/
