Logging
=======

Homebattery provides a verbose logging output for troubleshooting and optimizations.

The log output can be retrieved in two ways, the content is the same:

* serial console via micro USB
* UDP data stream via network

Serial console
--------------

The Raspberry Pico W provides a serial output via USB, which can be used to retrieve the logging data.

Connection parameters are:

* 115200 baud
* 8 databits
* no parity
* 1 stopbit
* no flow control

You can use any terminal emulation program that supports serial connections, like `PuTTY <https://www.putty.org>`_ or `picocom <https://github.com/npat-efault/picocom>`_.

.. warning::
   If the baseboard is used, it is strongly recommended to disconnect all other power supplies while using USB. Otherwise the Pico might get damaged due to ESD.

UDP data stream
---------------

Logging data can be sent via a UDP port, if a host is set in the logging configuration. For configuration, see the :doc:`software reference <../software/configuration>`.

Log data is then sent as plain text to this host. Homebattery comes with its own small application to receive this log data and store it in one file per day, see https://github.com/danielringch/homebattery/releases.

The logger application takes the following arguments:

* ``--host``: address to receive data from. This is usually set to ``0.0.0.0``.
* ``--port``: port to receive data from. This value must match the value in the homebattery configuration.
* ``--file``: path and name of the file the log will be written to
* ``--backup``: limits the number of files kept. So a value of 10 means that only data log data from the last 10 days will be kept.

Example: ``logger.exe --host 0.0.0.0 --port 12345 --file C:\Users\foo\homebattery.log --backup 7``

.. warning::
    The logs may contain sensitive information and are sent via an unencrypted connection. So do not use logging via UDP data stream over the internet or in networks with untrusted devices.