Prerequisites
=============

There are a few things that you need when using homebattery:

* a Raspberry Pico W
* a 2.4 GHz WLAN network with DHCP server
* an MQTT 5.0 broker

Depending on the hardware you want to connect, you might also need:

* a :ref:`baseboard <handbook_baseboard>` (necessary for using add-on boards)
* :ref:`add-on boards <handbook_addonboards>` (see drivers in the :doc:`software reference <../software/drivers>` for more information)

If the inverter power shall be regulated depending on power consumption, you also need:

* a supported power measurement device

Highly recommended, but not necessary are:

* an NTP server (e.g. ``time.google.com``)

.. note::
   homebattery does not require an internet connection, everything can be hosted on your local network.

For the initial setup and adaption of the configuration, you will also need a computer with:

* USB
* WLAN
* file browser
* text editor
* web browser
