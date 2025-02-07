[Battery] Pylontech US series
=============================

Driver name
-----------

pylonLv

Compatible devices
------------------

* Pylontech US series

Tested devices
--------------

* Pylontech US5000

Remarks
-------

The :ref:`RS485 add-on board <handbook_rs_485>` with RJ45 jack is necessary to connect the battery. The following pin assignment must be soldered:

====== ===
Signal Pin
====== ===
A      7
B      8
====== ===

The following jumpers must be soldered:

====== ======
Jumper State
====== ======
SJ1    closed
SJ2    closed
SJ3    closed
SJ4    closed
====== ======

Installation steps
------------------

* set the baudrate of the battery to 115200 baudrate
* connect the ``B/RS485`` port of the battery with the RS485 add-on board using an ethernet patch cable
* edit the configuration as documented in :ref:`driver configuration <confiuration_pylontech_us_series>`