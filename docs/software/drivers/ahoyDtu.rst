[Inverter] Hoymiles via AhoyDTU
===============================

Driver name
-----------

ahoyDtu

Compatible devices
------------------

* all inverters compatibel with `AhoyDTU <https://ahoydtu.de>`_

Tested devices
--------------

* Hoymiles HM-300
* Hoymiles HMT-2000-4T

Remarks
-------

If more than one inverter is connected to AhoyDTU, each inverter needs its own instance of this driver.

.. _power_lut:
power LUT
---------

Hoymiles inverters tend to give false power measurement readings, especially at high load. Since the netzero algorithm requires a quite precise control of the inverter power, some mitigation is needed. This is done by providing the relation between relative power (in percent) and real power (in watt) to homebattery as a power LUT file.

A power LUT file has the following format: ::

   [...]
   58;177
   59;179
   60;183
   61;186
   [...]

, the first value is the relative power, the second value is the real power.

The driver will set the inverter power only to values present in the power LUT. This means, by leaving out entries, the minimum and maximum power of the inverter can be set. 

A power LUT can be created with the following steps:

* connect a power measurement device between the AC side of the inverter and the wall socket
* ensure that the battery has an SOC > 60%
* set the inverter power using the AhoyDTU web interface and Active Power control
* start at the desired inverter minimum relative power
* wait until the inverter power has stabilized (takes a couple of seconds after a power change has been triggered)
* add an entry to the power LUT with the relative power set in AhoyDTU and the real power measured at the wall socket
* increment relative power and repeat the previous steps until the desired inverter maximum relativ power has been reached

The power LUT is only valid for a specific inverter and battery voltage. If the inverter is changed or the battery voltage is changed (e.g. switching from a 24 V system to a 48 V system), a new power LUT needs to be created.

Installation steps
------------------

* get the id of the inverter from the AhoyDTU web interface start page
* create a power LUT for the inverter
* upload the power LUT via the homebattery webinterface (see :ref:`installation <handbook_file_upload>`)
* edit the configuration as documented in :ref:`driver configuration <confiuration_ahoy_dtu>`