Prerequisites
=============

There are a few things that you need when using homebattery:

* a Raspberry Pico W
* a 2.4 GHz WLAN network with DHCP server
* an MQTT broker (might be available as plugin in your home automation solution)

Depending on your hardware, you might also need:

* a baseboard (necessary for using add-on boards)
* add-on boards (see drivers TODO section whether your devices need one)

Recommended, but not necessary are:

* an NTP server (you can just use one from the internet like ``time.google.com``)

.. note::
   homebattery does not require an internet connection, everything can be hosted on your local network.
