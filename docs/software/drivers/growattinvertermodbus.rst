[Inverter] Growatt via modbus
=============================

Driver name
-----------

growattinvertermodbus

Compatible devices
------------------

* Growatt xx00-S series inverters
* Growatt MIC xxTL-X series inverters

Tested devices
--------------

* Growatt 1000-S
* Growatt MIC 1500TL-X

Remarks
-------

These Growatt inverters have a too high startup voltagen for usage with a low voltage battery system, so this driver is intented for usage in a solar plant without battery.

The :ref:`RS-485 add-on board <handbook_rs_485>` is necessary to connect the inverter.

When the slave IDs are set correctly, multiple inverters can be connected to one add-on board channel. But since the inverters are not fully compatible to the modbus RTU specification, mixing them with other devices might not work.

Installation steps
------------------

* configure the slave ID of the inverter, see your device manual for more information
* connect the inverter to the RS-485 add-on board
* edit the configuration as documented in :ref:`driver configuration <confiuration_growatt>`