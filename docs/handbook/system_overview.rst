System overview
===============

A typical home battery storage system
-------------------------------------

.. image:: ../images/system_overview.png
  :width: 400
  :alt: system overview

A home battery storage system usually consists of at least four components:

* batteries
* chargers (powered by solar or grid)
* inverters
* a controller

Some devices combine multiple components (e.g. a hybrid inverter is usually solar charger, grid charger and inverter).

The homebattery as controller of the system has two main tasks:

* control the chargers and inverters to charge and discharge the batteries
* monitor the system and prevent unsafe operation states

There is total flexibility regarding the connected devices and there are no mandatory devices. You can also use homebattery e.g. to control your solar inverter (a system without batteries or chargers), to charge your EV (a system with only chargers) or to get your battery data published via MQTT (a system with only batteries).

.. note::
   homebattery has only limited standalone operation capabilities. It is designed to get the commands to switch between its mode of operation via MQTT.

Modes of operation
------------------

The main task of homebattery is to switch between predefined modes of operation. The trigger for changing the mode of operation is received via MQTT. It is not a statemachine in the traditional sense, as it is possible to switch into every mode of operation everytime (as long as it would not lead to an unsafe operation state).

+-----------+-------------------------------------+--------------------------------------------------+
| mode      | grid tie systems                    | hybrid inverter systems                          |
+===========+=====================================+==================================================+
| idle      | charge battery from solar           | feed output from solar + grid                    |
+-----------+-------------------------------------+--------------------------------------------------+
| grid      | charge battery from grid solar      | feed output from grid,                           |
|           |                                     |                                                  |
|           |                                     | charge battery from solar                        |
+-----------+-------------------------------------+--------------------------------------------------+
| charge    | charge battery from solar + grid    | feed output from grid,                           |
|           |                                     |                                                  |
|           |                                     | charge battery from solar + grid                 |
+-----------+-------------------------------------+--------------------------------------------------+
| discharge | activate inverter                   | feed output from solar + battery                 |
+-----------+-------------------------------------+--------------------------------------------------+
| protect   | everything is off                   | feed output from grid                            |
+-----------+-------------------------------------+--------------------------------------------------+

.. note::
   Mode ``grid`` is not implemented yet.

Homebattery will automatically switch off devices if they are not save to operate (e.g. all chargers will be switched off if a battery cell voltage gets too high).

For more information about modes of operation, see the :doc:`software reference <../software/modes_of_operation>`.

Connecting devices
------------------

There are five device classes:

* battery
* solar
* charger
* inverter
* power consumption measurement device

homebattery offers high flexibility regarding its connected devices:

* all device classes are optional (e.g. you can have a system without a grid charger)
* there can be multiple devices per class
* batteries, solar and charger devices can be distributed across several controllers (see :ref:`multi controller setups <handbook_multi_controller_setups>`)
* devices can be a combination of device classes (e.g. a hybrid inverter is usally solar, charger and inverter)

There are several ways to connect devices:

* network via WLAN
* Bluetooth (only for batteries)
* add-on boards

The used interface depends on the device, see the driver documentation in the :doc:`software reference <../software/drivers>`.

System locks
------------

A configured set checks is constantly applied on devive parameters. If a check fails, the affected device classes are locked (which means that they are turned off) until the check passes again.

Example: the battery cells are checked for their voltage. While a cell voltage too high locks the device classes solar and charger, a cell voltage too low locks the device class inverter.

The system locks and checks are described in the :doc:`software reference <../software/system_locks>`.

System monitoring
-----------------

There are several ways to monitor the operation of homebattery.

The system status and a collection of operating data are sent over MQTT and can be visualized in the home automation system of your choice.

Depending on your :doc:`hardware selection <hardware_selection>`, system status and some operating data are visualized using display and LEDs.

Detailed information can also be retrieved by the system log, see :doc:`logging <logging>`.


