[Charger][Heater] Shelly smart switch
=====================================

Driver name
-----------

``shellyCharger`` for charger
``shellyHeater`` for heater


Compatible devices
------------------

* all Shelly devices exposing a ``relay`` endpoint (Gen1)
* all Shelly devices implementing the Switch API (Gen2+)

Tested devices
--------------

* Shelly Plug S
* Shelly Plug S Gen3
* Shelly Plus 2PM

Remarks
-------

The the Shelly switch is used to switch an arbitrary charger or heater. Other shelly devices may work, too. Feedback is appreciated.

If a Shelly device with more than one switch is used, each switch needs its own instance of this driver.

In the configuration, the following settings for ``generation`` have been discovered (for device not in the list, you can just use trial and error):

* Shelly Plug S: ``1``
* Shelly Plug S Gen3: ``2``
* Shelly Plus 2PM: ``2``

Installation steps
------------------

* edit the configuration as documented in :ref:`driver configuration <confiuration_shelly_charger>`