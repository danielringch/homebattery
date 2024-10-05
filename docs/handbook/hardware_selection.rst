Hardware selection
==================

Raspberry Pico W only setups
----------------------------

homebattery supports running on a bare Raspberry Pico W. The system is then powered via the micro USB port.

.. image:: ../images/pico_topview.jpg
  :width: 600
  :alt: Raspberry Pico W

This setup comes with some limitations:

* only devices connected via network or Bluetooth can be used
* no display or LEDs

.. _handbook_baseboard:
Raspberry Pico W on baseboard
-----------------------------

homebattery comes with a baseboard featuring

* an OLED display
* status LEDs
* power via wide voltage range input or micro USB
* two extension ports for add-on boards

.. image:: ../images/baseboard_rpi_front.jpg
  :width: 300
  :alt: baseboard front view

.. image:: ../images/baseboard_rpi_back.jpg
  :width: 280
  :alt: baseboard back view

For more information, see the :doc:`hardware reference <../hardware/baseboard>`.

.. _handbook_multi_controller_setups:
Multi controller setups
-----------------------

If one Raspberry Pico W (with or without baseboard) is not sufficient to connect all devices, multiple controllers can be combined to one system.

Example setup:

.. image:: ../images/multi_controller_example.png
  :width: 500
  :alt: multi controller example

In a multi controller setup, all inverters and grid chargers are connected to one main controller. Solar chargers and batteries can either be connected to the main controller or to one or more additional controllers.

For more information, see TODO.

Housing
-------

The homebattery PCBs can be mounted using M3 screws. When using add-on boards, the PCBs are stacked behind the baseboard.

There is no case specifically for home battery, but there are instructions how to use a standard case with transparent front, see the :doc:`hardware reference <../hardware/housing>`.

.. _handbook_addonboards:
Add-on boards
-------------

.. _handbook_ve_direct:
VE.Direct
~~~~~~~~~

Victron SmartSolar and BlueSolar MPPT solar charges can be connected to homebattery using the VE.Direct add-on board.

.. image:: ../images/ve_direct_top.jpg
  :width: 300
  :alt: vedirect front view

.. image:: ../images/ve_direct_bottom.jpg
  :width: 300
  :alt: vedirect back view

For more information, see the :doc:`hardware reference <../hardware/vedirect>`.

.. _handbook_rs_485:
RS-485
~~~~~~

RS-485 or modbus devices can be connected to homebattery using the RS-485 add-on board. Cables can be connected via screw terminal or RJ45 jack with any pin configuration. Failsafe resistors and termination can be enabled via solder jumper.


For more information, see the :doc:`hardware reference <../hardware/rs485>`.
