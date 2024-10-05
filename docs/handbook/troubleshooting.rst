Troubleshooting
===============

Installation
------------

**The Raspberry Pico W keeps resetting itself after a couple of seconds**

* The Raspberry Pico W might fail to connect to the network, check your WLAN and configuration.
* The Raspberry Pico W might fail to connect to the MQTT broker, check your MQTT broker and configuration.

**The Raspberry Pico shows an error about invalid configuration on display or serial console.**

Check the configuration file and upload it again, see :doc:`installation <installation>`.

**The Raspberry Pico W does not start after installing the software.**

Connect your Raspberry Pico W via USB and get access to its serial console, see :doc:`logging <logging>`.

* If the output of the serial console is empty, please install the firmware again.
* If there is an output on the serial console, please check for error messages.

**No mass storage device appears after pressing BOOTSEL and plugging in the Raspberry Pico W.**

Bad news. Your Raspberry Pico W is probably broken. Sorry.

Logging
-------

**The serial connection gets interrupted when the Raspberry Pico resets.**

Unfortunately, this is normal behavior and can not be changed.