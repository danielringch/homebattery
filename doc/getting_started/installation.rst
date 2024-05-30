Installation
============

Install or update the homebattery firmware
------------------------------------------

* Download the latest homebattery .uf2 file from https://github.com/danielringch/homebattery/releases
* Press the BOOTSEL button and connect to your computer while holding the button
   * a mass storage device should appear on your computer
* Copy the .uf2 file to the mass storage device

Upload configuration and files
------------------------------

The configuration of homebattery is stored in a configuration file ``config.json``. A template configuration file is part of every release (https://github.com/danielringch/homebattery/releases).

See TODO for a detailed description of all configuration parameters.

* Modify the template configuration file according to your needs, see TODO
* turn off the Raspberry Pico W
* enable homebattery access point
    * without baseboard, connect ``GP9`` (Pin 12) with ``GND`` (Pin 13)
    * with baseboard, connect a jumper to ``SW1``
* turn on the Raspberry Pico W
* connect to the WLAN ``homebattery_cfg``
    * passphrase is ``webinterface``
* open ``http://192.168.0.1`` in your browser
* upload your ``config.json`` file
* turn off the Raspberry Pico W
* remove the jumper

Additional files (e.g. TLS certificates for MQTT) and also be uploaded or removed via the web interface.
