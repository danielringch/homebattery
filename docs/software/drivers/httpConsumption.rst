[Power] HTTP power consumption
==============================

Driver name
-----------

httpConsumption

Compatible devices
------------------

All devices or services that

* accept http requests
* send power measurement data as http json payload

Tested systems
--------------

* smart meter inface with Tasmota firmware

Installation steps
------------------

* get the http query for power measurement data from your senders documentation
* find the value in the json payload and note the corresponding keys
* edit the configuration as documented in :ref:`driver configuration <confiuration_http_consumption>`