Configuration
=============

Configuration is done using a json file, which is uploaded onto the Raspberry Pi Pico.

Location
--------

This file must be named ``config.json`` and be located in the folder ``config`` on the Pico.

Example
-------

A configuration template can be found in the repostiory in the `config folder <https://github.com/danielringch/homebattery/blob/main/config>`_.

Description
-----------

Network
~~~~~~~

Parent key: ``network``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``ssid``               | string, -      | The SSID of your WLAN network.                                                   | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``password``           | string, -      | The password of your WLAN network.                                               | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``timeout``            | integer, s     | | The timeout for connecting to the network.                                     | 15                |
|                        |                | | If the system is not connected to the network after the timeout, the system    |                   |
|                        |                |   restarts.                                                                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``ntp_server``         | string, -      | The host address of the ntp server.                                              | time.google.com   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``timezone``           | integer, -     | | The UTC offset of your timezone.                                               | 1 for Berlin      |
|                        |                | | The UTC offsets can be found here:                                             |                   |
|                        |                |   https://en.wikipedia.org/wiki/List_of_UTC_offsets .                            |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``ntp_timeout``        | integer, s     | | The timeout for retriving time from the ntp server.                            | 10                |
|                        |                | | If no time was retrived from the ntp server after the timeout, the system      |                   |
|                        |                |   restarts.                                                                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

MQTT
~~~~

Parent key: ``mqtt``

+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                        | Datatype | Description                                                                      | Recommended Value |
+============================+==========+==================================================================================+===================+
| ``host``                   | string   | Host address of the MQTT broker. Expected format is ``1.2.3.4:1883``.            | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``ca``                     | string   | Optional. Absolute path of the TLS CA certificate.                               | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``tls_insecure``           | boolean  | Optional. Turns on acception self-signed TLS certificates.                       | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``user``                   | string   | Optional. Username for authentification at the MQTT broker.                      | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``password``               | string   | Optional. Password for authentification at the MQTT broker.                      | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``root``                   | string   | | MQTT root topic.                                                               | homebattery       | 
|                            |          | | All MQTT topics the system is using will be sub-topics of this root topic      |                   |
|                            |          |   (except for live energy consumption).                                          |                   |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``live_consumption_topic`` | string   | | MQTT topic where live energy consumption data is published.                    | n.a.              |
|                            |          | | The system will subscribe to this topic and will expect a 16 bit unsigned      |                   |
|                            |          |   integer value representing the current energy consumtion in watts.             |                   |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+

Logging
~~~~~~~

Parent key: ``logging``

+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                       | Recommended Value |
+========================+==========+===================================================================================+===================+
| ``host``               | string   | Host and port of the logger.py instance.                                          | n.a.              |
|                        |          | Expected format is ``1.2.3.4:1883.``                                              |                   |
+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+
| ``ignore``             | list of  | | Logging sender that shall be ignored.                                           | mqtt, bluetooth   |
|                        | strings  | | Some parts of the system have a very verbose logging output for debug purposes. |                   |
|                        |          |   It can make sense to disable them in order to get a more readable log.          |                   |
+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+

Netzero
~~~~~~~

Parent key: ``netzero``

+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                        | Datatype, Unit | Description                                                                      | Recommended Value |
+============================+================+==================================================================================+===================+
| ``evaluated_time_span``    | integer, s     | | Time span that will be evaluated, older data will be ignored.                  | 60                |
|                            |                | | Larger values lead to slow adaption to higher energy consumption, smaller      |                   |
|                            |                |   values lead to more frequent changes of the inverter output power.             |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``maturity_time_span``     | integer, s     | | Time span after an inverter power change during which netzero will not trigger | 10                |
|                            |                |   another inverter power change.                                                 |                   |
|                            |                | | Larger values lead to prolonged periods without power control, smaller values  |                   |
|                            |                |   can lead to swinging of the power control.                                     |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_offset``           | integer, W     | | Expected remaining energy consumption.                                         | 5 - 10            |
|                            |                | | Larger values increase the average remaining energy consumption, smaller       |                   |
|                            |                |   can lead to swinging of the power control.                                     |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_hysteresis``       | integer, W     | | Hysteresis of the remaing energy consumption.                                  | 5 - 10            |
|                            |                | | Larger values increase the average remaining energy consumption, smaller       |                   |
|                            |                |   values lead to prolonged periods without power control or swinging of the      |                   |
|                            |                |   power control.                                                                 |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_change_upwards``   | integer, W     | | Maximum increase of the inverter power in a single inverter power change.      | 100 - 200         |
|                            |                | | Larger values can lead to swinging of the power control, smaller values        |                   |
|                            |                |   increase the average remaining energy consumption.                             |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_change_downwards`` | integer, W     | | Decrease of the inverter power in case of a backfeeding event.                 | 25 - 50           |
|                            |                | | Larger values increase the average remaining energy consumption, smaller       |                   |
|                            |                |   values increate losses due to backfeeding.                                     |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Supervisor
~~~~~~~~~~~

Parent key: ``supervisor```

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``check_interval``     | integer, s     | | Execution interval of the supervisor checks.                                   | 10                |
|                        |                | | Larger values lead to slower detection and release of errors, smaller values   |                   |
|                        |                |   increase CPU load.                                                             |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery offline check
'''''''''''''''''''''

Parent key: ``supervisor``, ``battery_offline``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | integer, s     | | Maximum time span with no successful communication to any battery.             | 120               |
|                        |                | | Larger values lead to slower detection of malfunctioning battery BMS,          |                   |
|                        |                |   smaller values can lead to transient system locks.                             |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell voltage high check
'''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``cell_high``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, V       | | Maximum voltage of a battery cell.                                             | 3.65              |
|                        |                | | Larger values can lead to faster aging of battery cells, smaller values lead   |                   |
|                        |                |   to smaller usable battery capacity and can prevent cell balancing.             |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, V       | | Hysteresis of the threshold value.                                             | 0.25              |
|                        |                | | Larger values can prevent charing a partially discharged battery, smaller      |                   |
|                        |                |   values can lead to toggling between charging and non-charging state.           |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell voltage low check
''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``cell_low``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, V       | | Minimum voltage of a battery cell.                                             | 3.1               |
|                        |                | | Larger values lead to smaller usable battery capacity, smaller values can lead |                   |
|                        |                |   to faster aging of battery cells.                                              |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, V       | | Hysteresis of the threshold value.                                             | 0.1               |
|                        |                | | Larger values can prevent discharing a partially charged battery, smaller      |                   |
|                        |                |   values can lead to toggling between discharging and non-discharging state.     |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Live consumption data lost while charging check
'''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``live_data_lost_charge``

+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                     | Datatype, Unit | Description                                                                      | Recommended Value |
+=========================+================+==================================================================================+===================+
| ``enabled``             | boolean, -     | Enables the check.                                                               | true              |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``           | integer, s     | | Maximum time span without live consumption data in charge state.               | 300               |
|                         |                | | Larger values can lead to incorrect billing of the electricity consumption     |                   |
|                         |                |   used for charging, smaller values can lead to toggling between charging and    |                   |
|                         |                |   non-charging state.                                                            |                   |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Live consumption data lost while discharging check
''''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``live_data_lost_discharge``

+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                     | Datatype, Unit | Description                                                                      | Recommended Value |
+=========================+================+==================================================================================+===================+
| ``enabled``             | boolean, -     | Enables the check.                                                               | true              |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``           | integer, s     | | Maximum time span without live consumption data in discharge state.            | 60                |
|                         |                | | Larger values can lead to incorrect billing of the electricity consumption     |                   |
|                         |                |   reduced by the inverter and to inverter over- or underproduction, smaller      |                   |
|                         |                |   values can lead to toggling between discharging and non-discharging state.     |                   |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

MQTT offline check
''''''''''''''''''

Parent key: ``supervisor``, ``mqtt_offline``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | integer, s     | | Maximum time span without connection to the MQTT broker.                       | 60                |
|                        |                | | Larger values delay a system reset in case the connection can not be restored, |                   |
|                        |                |   smaller values may lead to unnecessary system resets.                          |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Device drivers
~~~~~~~~~~~~~~

Parent key: ``devices``, ``<device name>``

``<device name>`` is used as display name and in MQTT topics. It must be unique.

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``driver``             | string   | Device driver. Values are given in the sub-sections below.                       | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

LLT Power BMS with Bluetooth
''''''''''''''''''''''''''''

Driver name: ``lltPowerBmsV4Ble``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``mac``                | string   | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

Daly H-Series Smart BMS with Bluetooth
''''''''''''''''''''''''''''''''''''''

Driver name: ``daly8S24V60A``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``mac``                | string   | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

JK BMS BD4-Series
'''''''''''''''''

Driver name: ``jkBmsBd4``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``mac``                | string   | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

Shelly smart switch
'''''''''''''''''''

Driver name: ``shelly``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``host``               | string   | Host address of the device. Expected format is ``1.2.3.4:80``                    | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``relay_id``           | integer  | Relay id of the used output. Value is 0 for single switch models, 0 and 1 for    | n.a.              |
|                        |          | dual switch models.                                                              |                   |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

AhoyDTU
'''''''

Driver name: ``ahoydtu``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``host``               | string   | Host address of the device. Expected format is ``1.2.3.4:80``                    | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``id``                 | integer  | Id of the used inverter. Value can be taken from the AhoyDTU web interface start | n.a.              |
|                        |          | page.                                                                            |                   |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``power_lut``          | string   | Absolute path to the inverter power lookup table.                                | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
