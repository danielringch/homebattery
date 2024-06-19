System overview
===============

A typical home battery storage system
-------------------------------------

.. image:: ../images/system_overview.png
  :width: 400
  :alt: system overview

A home battery storage system usually consists of at lead four components:

* batteries
* chargers (powered by solar or grid)
* inverters
* a controller

Some devices are multiple components at the same time (e.g. a hybrid inverter is usually solar charger, grid charger and inverter).

The homebattery as controller of the system usually has two main tasks:

* control the chargers and inverters to charge and discharge the batteries
* monitor the system and prevent unsafe operation states

There is total flexibility regarding the connected devices and there are no device that are mandatory to be present. You can also use homebattery e.g. to limit the energy fed into grid by your solar system (a system without batteries or chargers) or to only get your battery data published via MQTT (a system with only batteries).

.. note::
   homebattery has only limited standalone operation capabilities. It is designed to get the commands to switch between its mode of operation via MQTT.

Modes of operation
------------------

The main task of homebattery is to switch between predefined modes of operation. The trigger for changing the mode of operation is usually received via MQTT. It is not a statemachine in the traditional sense, as it is possible to switch into every mode of operation everytime (as long as it would not lead to an unsafe operation state).

+-----------+-------------------------------------+--------------------------------------------------+
| mode      | grid tie systems                    | hybrid inverter systems                          |
+===========+=====================================+==================================================+
| idle      | charge battery from solar           | feed output from solar + grid                    |
+-----------+-------------------------------------+--------------------------------------------------+
| charge    | charge battery from solar + grid    | feed output from grid,                           |
|           |                                     | charge battery from solar + grid                 |
+-----------+-------------------------------------+--------------------------------------------------+
| discharge | activate inverter                   | feed output from solar + battery                 |
+-----------+-------------------------------------+--------------------------------------------------+
| protect   | everything is off                   | feed output from grid                            |
+-----------+-------------------------------------+--------------------------------------------------+

Homebattery will automatically switch off devices if they are not save to operate (e.g. all chargers will be switched off if a battery cell voltage gets too high).

For more information about modes of operatio, see the :doc:`software reference <../software/modes_of_operation>`.

Connecting devices
------------------

There are five device classes:

* battery
* solar
* charger
* inverter
* power consumption measuring device

homebattery offers high flexibility regarding its connected devices:

* all device classes are optional (e.g. you can have a system without a grid charger)
* there can be multiple devices per class
* batteries, solar and charger devices can be distributed across several controllers (see :ref:`multi controller setups <handbook_multi_controller_setups>`)
* devices can be a combination of device classes (e.g. a hybrid inverter is usally solar, charger and inverter)

There are several ways to connect devices:

* network via WLAN
* Bluetooth (only for batteries)
* wired connections via add-on boards

The used interface depends on the device, see the driver documentation in the :doc:`software reference <../software/drivers>`.

System monitoring
-----------------

There are several ways to monitor the operation of homebattery.

The system status and a collection of operating data from the connected devices are sent over MQTT and can be visualized in the home automation system of your choice.

Depending on your :doc:`hardware selection <hardware_selection>`, system status and some operating data is visualized by display and LEDs.

Detailed information can also be retrieved by the system log, see :doc:`logging <logging>`.


