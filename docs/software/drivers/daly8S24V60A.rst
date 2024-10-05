[Battery] Daly BMS
==================

Driver name
-----------

daly8S24V60A

Compatible devices
------------------

* Daly H-Series Smart BMS with Bluetooth module

Tested devices
--------------

* Daly H-Series Smart BMS 8S 60A variant

Remarks
-------

Unfortunately, there is no specification about the Daly Bluetooth protocol available. So it is hard to tell which exact models are supported besides the ones actually tested. Feedback is appreciated.

Installation steps
------------------

* edit the configuration as documented in :ref:`driver configuration <confiuration_daly_8s_24v_60a>`
* if the Bluetooth communication gets lost after some time, set the BT timeout to 65535 in the battery cell settings using the Daly app
