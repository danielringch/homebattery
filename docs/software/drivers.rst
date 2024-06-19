Drivers
=======

Drivers are used to connect to the devices of the system. For every device, add a driver entry to the :doc:`configuration <configuration>`.

|
|
|

Battery
-------

LLT Power BMS / lltPowerBmsV4Ble
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* batteries with `LLT Power Electronics <https://www.lithiumbatterypcb.com>`_ BMS with Bluetooth 

Tested batteries
''''''''''''''''

* Accurat Traction T60 LFP BT 24V

Remarks
'''''''

LLT is a big OEM manufacturer for BMS and it seems like many prebuilt batteries contain one of their BMS. However, the BMS manufacturer is usually not listed in the data sheets, so you never know beforehand.

Installation steps
''''''''''''''''''

* set in the :ref:`driver configuration <confiuration_llt_power_bms_v4_ble>`

   * the Bluetooth MAC adress of the battery

|
|
|

Daly BMS / daly8S24V60A
~~~~~~~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* Daly H-Series Smart BMS with Bluetooth module

Tested devices
''''''''''''''

* Daly H-Series Smart BMS 8S 60A variant

Remarks
'''''''

Unfortunately, there is no specification about the Daly Bluetooth protocol available. So it is hard to tell which exact models are supported besides the ones actually tested. Feedback is appreciated.

Installation steps
''''''''''''''''''

* set in the :ref:`driver configuration <confiuration_daly_8s_24v_60a>`

   * the Bluetooth MAC adress of the battery

* if the Bluetooth communication gets lost after some time, set the BT timeout to 65535 in the battery cell settings using the Daly app

|
|
|

JK BMS / jkBmsBd4
~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* JK BMS BD4-Series

Tested devices
''''''''''''''

* BD4A17S4P

Remarks
'''''''

This driver is basically a port of https://github.com/syssi/esphome-jk-bms, but only the BD4-Series models are supported yet. More will come in the future.

Installation steps
''''''''''''''''''

* set in the :ref:`driver configuration <confiuration_jk_bms_bd4>`

   * the Bluetooth MAC adress of the battery

|
|
|

MQTT Battery / mqttBattery
~~~~~~~~~~~~~~~~~~~~~~~~~~

This driver is used in :ref:`multi controller setups <handbook_multi_controller_setups>`. The data from a battery connected to another homebattery controller can be received via MQTT.

Installation steps
''''''''''''''''''

* set in the :ref:`driver configuration <confiuration_mqtt_battery>`

   * the MQTT root topic of the battery
   * the number of cells
   * the number of temperature sensors

|
|
|

Solar Charger
-------------

Victron Smart-/ BlueSolar MPPT / victronMppt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* Victron BlueSolar MPPT Series
* Victron SmartSolar MPPT Series

Tested devices
''''''''''''''

* Smartsolar MPPT 75/15

Remarks
'''''''

The :ref:`VE.Direct add-on board <handbook_ve_direct>` is necessary to connect the solar charger, communcation via Bluetooth is not supported.

The protocol is published by Victron, so there is high confidence that every model of the product family is working, despite not all have been tested yet.

Installation steps
''''''''''''''''''

* configure the TX pin of your charger to switch its charger output, see your device manual for more information
* connect the VE.Direct add-on board to the baseboard
* connect the solar charger to the VE.Direct add-on board using an original VE.Direct cable
* set in the :ref:`driver configuration <confiuration_victron_mppt>`

   * the used expansion slot

|
|
|

Grid Charger
------------

Shelly smart switch / shellyCharger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* Shelly Plug S
* Shelly Plus 1PM
* Shelly Plus 2PM

Tested devices
''''''''''''''

* Shelly Plug S
* Shelly Plus 2PM

Remarks
'''''''

The the Shelly switch is used to switch an arbitrary battery charger. Other models may work, too. Feedback is appreciated.

If a Shelly device with more than one switch is used, each switch needs its own instance of this driver.

Installation steps
''''''''''''''''''

* connect your Shelly device to the same network as homebattery 
* set in the :ref:`driver configuration <confiuration_shelly_charger>`

   * the host address of the Shelly device
   * the relay id (always 1 for single switch models)

|
|
|

Inverter
--------

Hoymiles inverters via AhoyDTU / ahoyDtu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compatible devices
''''''''''''''''''

* all inverters compatibel with `AhoyDTU <https://ahoydtu.de>`_

Tested devices
''''''''''''''

* Hoymiles HM-300

Remarks
'''''''

If more than one inverter is connected to AhoyDTU, each inverter needs its own instance of this driver.

power LUT
'''''''''

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

* connect a power measurement device between the AC side of the inverter an the wall socket
* connect the battery with a SOC > 60%
* set the inverter power using AhoyDTU Active Power control
* start at the desired inverter minimum relative power
* wait until the inverter power has stabilized (takes a couple of seconds after a power change has been triggered)
* add an entry to the power LUT with the relative power set in AhoyDTU and the real power measured at the wall socket
* increment relative power and repeat the previous steps until the desired inverter maximum relativ power has been reached

The power LUT is only valid for a specific inverter and battery voltage. If the inverter is changed or the battery voltage is changed (e.g. switching from a 24 V system to a 48 V system), a new power LUT needs to be created.

Installation steps
''''''''''''''''''

* connect your AhoyDTU device to the same network as homebattery
* get the id of the inverter from the AhoyDTU web interface start page
* create a power LUT for the inverter
* upload the power LUT via the homebattery webinterface (see :ref:`installation <handbook_file_upload>`)
* set in the :ref:`driver configuration <confiuration_ahoy_dtu>`

   * the host address of the AhoyDTU device
   * the id of the inverter
   * the file name of the power LUT

|
|
|

Live power consumption measurement
----------------------------------

MQTT power consumption / mqttConsumption
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This driver is used in to receive live consumption data from any device or program publishing power consumption data via MQTT.

The power consumption must be published as 16 bit or 32 bit integer value in watt.

Tested systems
''''''''''''''

* `tibber Pulse <https://tibber.com/de/pulse>`_ + `tibber2mqtt <https://github.com/danielringch/tibber2mqtt>`_ 

Installation steps
''''''''''''''''''

* set in the :ref:`driver configuration <confiuration_mqtt_consumption>`

   * the topic where the live consumption data is published
