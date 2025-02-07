Installation
============

Install or update the homebattery firmware
------------------------------------------

* download the latest homebattery ``.uf2`` file from https://github.com/danielringch/homebattery/releases
* press and hold the BOOTSEL button and connect the Pico to your computer
* a mass storage device should appear on your computer
* copy the .uf2 file to the mass storage device
* disconnect the Pico from your computer

.. warning::
   If the baseboard is used, it is strongly recommended to disconnect all other power supplies and ground connections while using USB. Otherwise, the Pico might get damaged due to ESD.

Create the configuration file
-----------------------------

* copy the template from the release or https://github.com/danielringch/homebattery/tree/main/config
* adapt the file to your needs (see :doc:`software reference <../software/configuration>`)

.. _handbook_file_upload:
Upload configuration and files
------------------------------

* turn off the Raspberry Pico W / baseboard
* connect a jumper to ``SW1`` (baseboard) or between ``GP9``/ Pin 12 and ``GND`` / Pin 13 (no baseboard)
* turn on the Raspberry Pico W / baseboard
* connect to the WLAN ``homebattery_cfg``, passphrase is ``webinterface``
* open ``http://192.168.4.1`` in your browser
* delete any existing ``config.json`` file
* upload your ``config.json`` file (select the file *and* click 'Upload file')
* remove the jumper
* turn off the Raspberry Pico W / baseboard

.. note::
   Additional files (e.g. TLS certificates for MQTT) can also be uploaded or removed via the web interface.

.. warning::
   Files can not be downloaded, so keep copies of the files you have uploaded.

.. warning::
   If Safari is used, the list of files may not refresh automatically. Please reload the page manually a couple seconds after deleting/ uploading a file.
