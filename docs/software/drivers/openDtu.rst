[Inverter] Hoymiles via OpenDTU
===============================

Driver name
-----------

openDtu

Compatible devices
------------------

* all inverters compatibel with `OpenDTU <https://www.opendtu.solar>`_

Tested devices
--------------

* Hoymiles HM-300
* Hoymiles HMT-2000-4T

Remarks
-------

If more than one inverter is connected to OpenDTU, each inverter needs its own instance of this driver.

power LUT
---------

See :ref:`AhoyDTU driver <power_lut>`.

Installation steps
------------------

* create a power LUT for the inverter
* upload the power LUT via the homebattery webinterface (see :ref:`installation <handbook_file_upload>`)
* edit the configuration as documented in :ref:`driver configuration <confiuration_open_dtu>`