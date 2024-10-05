System overview
===============

A typical home battery storage system
-------------------------------------

.. image:: ../images/system_overview.png
  :width: 400
  :alt: system overview

A home battery storage system usually consists of the following components:

* batteries
* chargers (powered by solar or grid)
* inverters
* a controller

Some devices are a combination of components (e.g. a hybrid inverter is usually a solar charger, grid charger and inverter).

Homebattery as controller of the system has two main tasks:

* control the chargers and inverters to charge and discharge the batteries depending on the mode of operation
* monitor the system and prevent unsafe operation states

There is total flexibility regarding the connected devices. You can also use homebattery e.g. to control your solar inverter (a system without batteries or chargers), to charge your EV (a system with only chargers) or to get your battery data published via MQTT (a system with only batteries).

.. note::
   Homebattery contains no logic *when* to switch its mode of operation (with the exception of changes to protection modes). It is designed to receive commands for switching its mode of operation via MQTT.

Modes of operation
------------------

The modes of operation define which devices are active and which are not, which influences the energy flow in the system.

The trigger for changing the mode of operation is received via MQTT.

+-----------+-------------------------------------+--------------------------------------------------+
| mode      | grid tie systems                    | hybrid inverter systems                          |
+===========+=====================================+==================================================+
| idle      | charge battery from solar           | feed output from solar + grid                    |
+-----------+-------------------------------------+--------------------------------------------------+
| grid      | charge battery from surplus grid    | feed output from grid,                           |
|           | energy (for EV chargers only)       |                                                  |
|           |                                     | charge battery from solar                        |
+-----------+-------------------------------------+--------------------------------------------------+
| charge    | charge battery from solar + grid    | feed output from grid,                           |
|           |                                     |                                                  |
|           |                                     | charge battery from solar + grid                 |
+-----------+-------------------------------------+--------------------------------------------------+
| discharge | charge battery from solar, activate | feed output from solar + battery                 |
|           | inverter                            |                                                  |
+-----------+-------------------------------------+--------------------------------------------------+
| protect   | everything is off                   | feed output from grid                            |
+-----------+-------------------------------------+--------------------------------------------------+

.. note::
   Mode ``grid`` is not implemented yet.

For more information about modes of operation, see the :doc:`software reference <../software/modes_of_operation>`.

Connecting devices
------------------

There are five device classes:

* battery
* solar
* charger
* inverter
* power measurement

Homebattery offers high flexibility regarding its connected devices:

* all device classes are optional (e.g. you can have a system without a grid charger)
* there is no device limit per class
* batteries and solar devices can be distributed across several controllers (see :ref:`multi controller setups <handbook_multi_controller_setups>`)
* devices can be a combination of device classes (e.g. a hybrid inverter is usally solar, charger and inverter)

There are several ways to connect devices:

* network via WLAN
* Bluetooth (only for batteries)
* add-on boards

The used interface depends on the device, see the driver documentation in the :doc:`software reference <../software/drivers>`.

Device class locks
------------------

A configured set of checks is constantly applied on device parameters. If a check fails, the affected device classes are locked (which means that they are turned off) until the check passes again.

Example: the battery cells are checked for their voltage. While a cell voltage too high locks the device classes solar and charger, a cell voltage too low locks the device class inverter.

The checks and locks are described in the :doc:`software reference <../software/locks>`.

System monitoring
-----------------

There are several ways to monitor the operation of homebattery.

The system status and a collection of operating data are sent over MQTT and can be visualized in the home automation system of your choice.

Depending on your :doc:`hardware selection <hardware_selection>`, system status and some operating data are visualized using display and LEDs.

Detailed information can also be retrieved by the system log, see :doc:`logging <logging>`.


